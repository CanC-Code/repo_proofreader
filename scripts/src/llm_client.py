import os
import json
from openai import OpenAI

# Retrieve the key, explicitly enforcing the fallback if it returns an empty string
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    api_key = "ollama"

client = OpenAI(
    api_key=api_key,
    base_url=os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1")
)

# Model name is configurable via env so the workflow controls it, not the script.
MODEL_NAME = os.getenv("LLM_MODEL", "qwen2.5-coder-7b-instruct")

# Safe context budget: 32768 token window - 4096 completion - ~1000 overhead = 27672
# At ~4 chars/token that is roughly 110,000 chars. We stay well under in context_retriever.
MAX_COMPLETION_TOKENS = 4096

def query_reasoning_engine(diff_data, context_map, issue_description):
    with open('.proofreader-engine/templates/error_reasoning.txt', 'r') as f:
        system_prompt_template = f.read()

    # Strip unfilled placeholder tokens so the model receives a clean directive-only
    # system prompt. All data arrives via the user message below.
    system_prompt = (
        system_prompt_template
        .replace("{{pr_diff}}", "")
        .replace("{{context_files}}", "")
        .strip()
    )

    user_content = (
        f"DIFF:\n{diff_data.get('diff', '[NO DIFF]')}\n\n"
        f"COMMIT HISTORY:\n{diff_data.get('commit_history', '[NONE]')}\n\n"
        f"CONTEXT MAP:\n{json.dumps(context_map, indent=2)}\n\n"
        f"ISSUE DESCRIPTION:\n{issue_description}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    # Only enable json_object mode when hitting a real OpenAI endpoint.
    # llama-cpp-python's server has unreliable support for this flag.
    use_json_mode = bool(os.getenv("OPENAI_API_KEY"))

    try:
        print(f"[DEBUG] Dispatching to model: {MODEL_NAME}")
        print(f"[DEBUG] Payload size: {sum(len(m['content']) for m in messages)} chars")

        create_kwargs = dict(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
            max_tokens=MAX_COMPLETION_TOKENS,
        )
        if use_json_mode:
            create_kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**create_kwargs)
        raw_content = response.choices[0].message.content

        # Strip markdown fences that a non-compliant model may emit
        clean = raw_content.strip()
        if clean.startswith("```"):
            clean = clean.split("```", 2)[-1]
            clean = clean.rsplit("```", 1)[0].strip()
        if clean.lower().startswith("json"):
            clean = clean[4:].lstrip()

        return json.loads(clean)

    except json.JSONDecodeError as e:
        print(f"[ERROR] LLM returned non-JSON output: {e}")
        print(f"[DEBUG] Raw model output:\n{raw_content}")
        return {
            "reasoning_steps": ["Model returned malformed JSON; see debug output above."],
            "root_cause_analysis": f"JSON parse failure: {e}",
            "patch_plan": {"file_path": "N/A", "suggested_fix": "N/A"},
            "risk_assessment": "High"
        }
    except Exception as e:
        print(f"[ERROR] LLM API execution failed: {e}")
        return {
            "reasoning_steps": ["LLM processing interrupted."],
            "root_cause_analysis": f"Connection/Execution Exception: {e}",
            "patch_plan": {"file_path": "N/A", "suggested_fix": "N/A"},
            "risk_assessment": "High"
        }
