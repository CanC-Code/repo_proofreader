import os
import json
from openai import OpenAI

# Initialize client. If using Ollama, set base_url to 'http://localhost:11434/v1'
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "ollama"), 
    base_url=os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1")
)

def query_reasoning_engine(diff_data, context_map):
    """
    Constructs the prompt and interacts with the reasoning engine.
    """
    # Load the system template from your templates folder
    with open('templates/error_reasoning.txt', 'r') as f:
        system_prompt = f.read()

    # Construct the payload
    # Note: We enforce JSON output to ensure the verifier can read it
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"DIFF: {diff_data['diff']}\n\nCONTEXT: {json.dumps(context_map)}"}
    ]

    response = client.chat.completions.create(
        model="qwen2.5-coder-3b-instruct", # Or your preferred model
        messages=messages,
        response_format={"type": "json_object"} # Crucial for automated parsing
    )

    return json.loads(response.choices[0].message.content)
