import os
import sys
import argparse
import json
from src.git_helper import get_latest_diff
from src.context_retriever import fetch_relevant_files
from src.llm_client import query_reasoning_engine

def clean_markdown_code(raw_text):
    if not raw_text:
        return ""
    if isinstance(raw_text, (dict, list)):
        raw_text = json.dumps(raw_text, indent=2)
    elif not isinstance(raw_text, str):
        raw_text = str(raw_text)
    
    lines = raw_text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
    return "\n".join(lines).strip() + "\n"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo_path", required=True)
    args = parser.parse_args()

    workspace_root = os.getenv('GITHUB_WORKSPACE', os.getcwd())
    print(f"[DEBUG] Workspace root identified as: {workspace_root}")
    
    repo_path = workspace_root
    diff_data = get_latest_diff(repo_path)
    
    if not diff_data:
        print("[WARNING] No git diff detected. Running Full Repo Diagnostic...")
        diff_data = {'modified_files': [], 'diff': ''}
        
    runtime_issue_description = (
        "White Screen Hang: The app launches, ROM extraction succeeds, but immediately deadlocks "
        "on a white screen. The C++ game loop is likely deadlocking Android's GLThread. "
        "Analyze GLRenderer.java and NativeBridge.cpp to ensure the C++ emulation loop is executing "
        "on a dedicated background Java thread, freeing onDrawFrame() to swap buffers properly."
    )
    
    print("[INFO] Building context map...")
    context_map = fetch_relevant_files(repo_path, diff_data, runtime_issue_description)
    
    if not context_map:
        print("[ERROR] Context map empty! Missing critical Android source files.")
        sys.exit(1)

    print(f"[INFO] Dispatching analysis for {len(context_map)} files...")
    
    try:
        # Calls the localized Llama-CPP pipeline
        analysis_result = query_reasoning_engine(diff_data, context_map, runtime_issue_description)
        
        print("\n--- [LLM DIAGNOSTIC RESULT] ---")
        print(json.dumps(analysis_result, indent=2))
        print("-------------------------------\n")
        
        patch_plan = analysis_result.get('patch_plan', {})
        file_path = patch_plan.get('file_path')
        suggested_fix = patch_plan.get('suggested_fix')
        
        if not file_path or not suggested_fix or file_path == "N/A":
            print("[FAILURE] LLM did not provide a valid patch plan.")
            sys.exit(1)

        cleaned_code = clean_markdown_code(suggested_fix)
        
        print(f"\n[SUCCESS] AI proposed a logical fix for: {file_path}")
        print("======================================================================")
        print(f"vvv FULL REPLACEMENT FILE FOR: {file_path} vvv")
        print("======================================================================")
        print(cleaned_code)
        print("======================================================================")
        print(f"^^^ END OF FILE: {file_path} ^^^")
        print("======================================================================\n")
        
        print("[INFO] Analysis complete. Review the full file output above and replace your local file.")
        
    except Exception as e:
        print(f"[CRITICAL FAILURE] Engine Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()