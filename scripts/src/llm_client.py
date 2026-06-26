import os
import json
import sys
from llama_cpp import Llama

def query_reasoning_engine(diff_data, context_map, issue_description):
    # Use direct Python bindings instead of OpenAI HTTP client to prevent ALL network timeouts
    model_path = "model.gguf"
    
    if not os.path.exists(model_path):
        print(f"[CRITICAL] Model file {model_path} not found in workspace!")
        sys.exit(1)

    print("[INFO] Loading Qwen 7B model locally into RAM... (This may take a moment)")
    
    try:
        # Load model natively in the same Python process
        llm = Llama(
            model_path=model_path,
            n_ctx=16384,
            n_gpu_layers=0, # Pure CPU execution
            verbose=False
        )
    except Exception as e:
        print(f"[ERROR] Failed to load Llama model: {e}")
        sys.exit(1)

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

    print("[INFO] Dispatching payload to native Llama instance. Bypassing all network timeouts.")
    print("[WARNING] GitHub Actions CPU inference for 7B models can take 15-30 minutes. Please wait...")

    try:
        response = llm.create_chat_completion(
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.1 # Low temperature forces strict logical adherence and prevents language leaks
        )
        
        result_text = response["choices"][0]["message"]["content"]
        return json.loads(result_text)
        
    except Exception as e:
        print(f"[ERROR] Local model generation failed: {e}")
        return {
            "reasoning_steps": ["Native inference interrupted."],
            "root_cause_analysis": f"Execution Exception: {e}",
            "patch_plan": {"file_path": "N/A", "suggested_fix": "N/A"},
            "risk_assessment": "High"
        }