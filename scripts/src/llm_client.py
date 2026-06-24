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
        print("[DEBUG] Dispatching static analysis payload to LLM endpoint...")
        response = client.chat.completions.create(
            model="qwen2.5-coder-3b-instruct",
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