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

def query_reasoning_engine(diff_data, context_map, issue_description):
    with open('.proofreader-engine/templates/error_reasoning.txt', 'r') as f:
        system_prompt_template = f.read()

    # Strip the unfilled placeholder tokens from the template so the LLM
    # receives a clean directive-only system prompt. The actual data is
    # injected via the user message below, which is where the model reads it.
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

    # Determine whether we are hitting the local llama-cpp server or a real
    # OpenAI-compatible endpoint. llama-cpp-python's server has partial support
    # for response_format; we only enable it when we can guarantee the endpoint
    # will honour it (i.e. when a real OPENAI_API_KEY is present).
    use_json_mode = bool(os.getenv("OPENAI_API_KEY"))

    try:
        print("[DEBUG] Dispatching static analysis payload to LLM endpoint...")

        create_kwargs = dict(
            model="qwen2.5-coder-3b-instruct",
            messages=messages,
            temperature=0.1,   # Low temperature for deterministic code output
            max_tokens=4096,
        )
        if use_json_mode:
            create_kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**create_kwargs)
        raw_content = response.choices[0].message.content

        # Strip markdown fences that a non-compliant model might emit
        clean = raw_content.strip()
        if clean.startswith("```"):
            clean = clean.split("```", 2)[-1]          # drop opening fence
            clean = clean.rsplit("```", 1)[0].strip()  # drop closing fence
        # Strip a leading language tag e.g. "json\n{"
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
