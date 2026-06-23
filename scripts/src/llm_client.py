import os
import json
from openai import OpenAI

# Retrieve the key, and explicitly enforce the fallback if it returns an empty string
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    api_key = "ollama"

client = OpenAI(
    api_key=api_key, 
    base_url=os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1")
)

def query_reasoning_engine(diff_data, context_map, error_logs):
    with open('.proofreader-engine/templates/error_reasoning.txt', 'r') as f:
        system_prompt = f.read()

    user_content = (
        f"DIFF:\n{diff_data['diff']}\n\n"
        f"CONTEXT MAP:\n{json.dumps(context_map)}\n\n"
        f"COMPILER ERROR LOGS:\n{error_logs}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    response = client.chat.completions.create(
        model="qwen2.5-coder-3b-instruct",
        messages=messages,
        response_format={"type": "json_object"} 
    )

    return json.loads(response.choices[0].message.content)
