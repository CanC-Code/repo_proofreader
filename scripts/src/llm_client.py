import os
import json
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    api_key = "ollama"

# CRITICAL FIX: Set a massive timeout (or None for infinite) 
# because 7B models on GitHub Actions CPUs take a long time to generate full files.
client = OpenAI(
    api_key=api_key, 
    base_url=os.getenv("LLM_ENDPOINT", "http://localhost:8000/v1"),
    timeout=3600.0 # Wait up to 1 hour for the local model to finish
)

def query_reasoning_engine(diff_data, context_map, issue_description):
    with open('.proofreader-engine/templates/error_reasoning.txt', 'r') as f:
        system_prompt = f.read()

    user_content = (
        f"DIFF:\n{diff_data['diff']}\n\n"
        f"CONTEXT MAP:\n{json.dumps(context_map)}\n\n"
        f"ISSUE DESCRIPTION:\n{issue_description}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    try:
        model_name = os.getenv("LLM_MODEL", "qwen2.5-coder-7b-instruct")
        print(f"[DEBUG] Dispatching payload to {model_name} (this may take 10-20 minutes on CPU)...")
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"} 
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[ERROR] LLM API execution failed: {e}")
        return {
            "reasoning_steps": ["LLM processing interrupted."],
            "root_cause_analysis": f"Connection/Execution Exception: {e}",
            "patch_plan": {"file_path": "N/A", "suggested_fix": "N/A"},
            "risk_assessment": "High"
        }