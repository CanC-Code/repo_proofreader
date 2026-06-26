import os
import json
import sys
from llama_cpp import Llama

def query_reasoning_engine(diff_data, context_map, issue_description):
    # Locate the model downloaded by the GitHub Action
    model_path = "model.gguf"
    
    if not os.path.exists(model_path):
        print(f"[CRITICAL] Model file {model_path} not found in workspace!")
        sys.exit(1)

    print("[INFO] Loading Qwen 7B model locally into RAM... (This may take a moment)")
    
    try:
        # Load model natively in the same Python process. 
        # n_ctx=16384 ensures the AI can swallow the massive codebase map without truncating.
        llm = Llama(
            model_path=model_path,
            n_ctx=16384,
            n_gpu_layers=0, # Pure CPU execution for GitHub Actions compatibility
            verbose=False
        )
    except Exception as e:
        print(f"[ERROR] Failed to load Llama model natively: {e}")
        sys.exit(1)

    prompt_path = '.proofreader-engine/templates/error_reasoning.txt'
    if not os.path.exists(prompt_path):
        prompt_path = 'templates/error_reasoning.txt' # Fallback

    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    user_content = (
        f"DIFF:\n{diff_data.get('diff', 'None')}\n\n"
        f"CONTEXT MAP:\n{json.dumps(context_map)}\n\n"
        f"ISSUE DESCRIPTION:\n{issue_description}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    print("[INFO] Dispatching payload to native Llama instance. Bypassing all network timeouts.")
    print("[WARNING] GitHub Actions CPU inference for 7B models can take 15-30 minutes. Please wait...")

    try:
        # A synchronous, offline call. It will never timeout on a network socket.
        response = llm.create_chat_completion(
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4096, # Huge token allowance for entire file replacements
            temperature=0.1, # Extremely low temperature strictly prohibits non-English logic hallucinations
            top_p=0.9
        )
        
        result_text = response["choices"][0]["message"]["content"]
        return json.loads(result_text)
        
    except Exception as e:
        print(f"[ERROR] Local model generation failed: {e}")
        return {
            "reasoning_steps": ["Native inference interrupted or failed locally."],
            "root_cause_analysis": f"Execution Exception: {e}",
            "patch_plan": {"file_path": "N/A", "suggested_fix": "N/A"},
            "risk_assessment": "High"
        }