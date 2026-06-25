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

    print(f"--- [INFO] Initializing Global Static Analysis Proofreader on {args.repo_path} ---")
    
    diff_data = get_latest_diff(args.repo_path)
    if not diff_data:
        print("[ERROR] Could not get diff data. Exiting.")
        sys.exit(1)
        
    # FIX: Updated symptom description to target the new Android UI Hang
    runtime_issue_description = (
        "The APK compiles and installs successfully. The initial UI launches and the 'Select ROM' "
        "extraction phase succeeds. However, exactly 2 seconds after the ROM is accepted, the Android "
        "application crashes with a silent white screen. There are no ADB logs available. Investigate the "
        "Android Kotlin frontend (e.g., MainActivity) and the C++ JNI bridge for deadlocks. Ensure the "
        "native C++ game loop is not being executed synchronously on the main Android UI thread, and check "
        "if the EGL SurfaceView is fully bound before rendering begins."
    )
    
    print("[INFO] Building contextual code map via Global Repo Search...")
    try:
        # Pass the issue description to the global search engine
        context_map = fetch_relevant_files(args.repo_path, diff_data, runtime_issue_description)
    except Exception as e:
        print(f"[ERROR] Failed to build context map: {e}")
        sys.exit(1)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"\n--- [INFO] Static Analysis Attempt {attempt}/{max_retries} ---")
        
        try:
            analysis_result = query_reasoning_engine(diff_data, context_map, runtime_issue_description)
        except Exception as e:
            print(f"[ERROR] LLM Query Failed: {e}")
            continue
        
        print("\n--- [DIAGNOSIS] ---")
        print(f"Root Cause Analysis:\n{analysis_result.get('root_cause_analysis', 'N/A')}")
        print("Reasoning Steps:")
        for step in analysis_result.get('reasoning_steps', []):
            print(f"  - {step}")
        print("-------------------\n")

        patch_plan = analysis_result.get('patch_plan', {})
        file_path = patch_plan.get('file_path')
        suggested_fix = patch_plan.get('suggested_fix')
        
        if not file_path or not suggested_fix or file_path == "N/A":
            print("[FAILURE] LLM did not provide a valid patch plan.")
            continue

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
        sys.exit(0)
            
    print(" Max retries reached. Unable to resolve the logic failure.")
    sys.exit(1)

if __name__ == "__main__":
    main()