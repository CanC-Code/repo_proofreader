import os
import json
import sys
from llama_cpp import Llama

# Singleton: load the model once and reuse across all batch passes
_llm_instance = None


def _get_llm():
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    model_path = "model.gguf"
    if not os.path.exists(model_path):
        print(f"[CRITICAL] Model file '{model_path}' not found in workspace! "
              f"The runner failed to download it.")
        sys.exit(1)

    print("[INFO] Loading Qwen 7B model into RAM... (one-time load, reused across all passes)")
    try:
        _llm_instance = Llama(
            model_path=model_path,
            n_ctx=24576,       # 24k token context window
            n_gpu_layers=0,    # Pure CPU for GitHub Actions compatibility
            verbose=False
        )
    except Exception as e:
        print(f"[ERROR] Failed to load Llama model: {e}")
        sys.exit(1)

    return _llm_instance


def _load_system_prompt():
    """Locate and load the system prompt template from known paths."""
    candidate_paths = [
        '.proofreader-engine/templates/error_reasoning.txt',
        'templates/error_reasoning.txt',
        os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'error_reasoning.txt'),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
    print("[ERROR] System prompt template not found. Checked paths:")
    for p in candidate_paths:
        print(f"  {p}")
    sys.exit(1)


def query_reasoning_engine(diff_data, context_map, issue_description, pass_num=1, total_passes=1):
    """
    Submit one batch of files to the local LLM for static analysis.

    Args:
        diff_data:          Dict with 'diff', 'modified_files', 'commit_history'.
        context_map:        Dict of {rel_path: file_content} for this batch.
        issue_description:  Human-readable description of what to look for.
        pass_num:           Current pass index (1-based), for logging.
        total_passes:       Total number of passes, for logging.

    Returns:
        Parsed JSON dict matching the error_reasoning.txt output schema.
    """
    llm = _get_llm()
    system_prompt = _load_system_prompt()

    pass_header = f"[ANALYSIS PASS {pass_num} of {total_passes}]\n" if total_passes > 1 else ""

    user_content = (
        f"{pass_header}"
        f"DIFF:\n{diff_data.get('diff', 'None')}\n\n"
        f"COMMIT HISTORY:\n{diff_data.get('commit_history', 'None')}\n\n"
        f"CONTEXT MAP ({len(context_map)} files):\n{json.dumps(context_map)}\n\n"
        f"ISSUE DESCRIPTION:\n{issue_description}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    print(f"[INFO] Dispatching pass {pass_num}/{total_passes} to local Llama instance "
          f"({len(context_map)} files, {len(user_content)} chars).")
    if pass_num == 1:
        print("[WARNING] GitHub Actions CPU inference for 7B models can take 15-30 minutes per pass. "
              "Please wait...")

    try:
        response = llm.create_chat_completion(
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.1,
            top_p=0.9
        )

        result_text = response["choices"][0]["message"]["content"]
        return json.loads(result_text)

    except json.JSONDecodeError as e:
        print(f"[ERROR] LLM returned non-JSON output on pass {pass_num}: {e}")
        return {
            "reasoning_steps": [f"JSON decode failed on pass {pass_num}."],
            "root_cause_analysis": f"JSON parse error: {e}",
            "patch_plan": {"file_path": "N/A", "suggested_fix": "N/A"},
            "risk_assessment": "High"
        }
    except Exception as e:
        print(f"[ERROR] Local model generation failed on pass {pass_num}: {e}")
        return {
            "reasoning_steps": [f"Native inference interrupted on pass {pass_num}."],
            "root_cause_analysis": f"Execution Exception: {e}",
            "patch_plan": {"file_path": "N/A", "suggested_fix": "N/A"},
            "risk_assessment": "High"
        }
