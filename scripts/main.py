import os
import sys
import argparse
import json
from src.git_helper import get_latest_diff
from src.context_retriever import fetch_relevant_files
from src.llm_client import query_reasoning_engine

def clean_markdown_code(raw_text):
    """Strips markdown code blocks from LLM output and enforces string typing."""
    if not raw_text:
        return ""
    
    # Type safety check to ensure it formats properly if the LLM returns an object
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

    print(f"--- [INFO] Initializing Static Analysis Proofreader on {args.repo_path} ---")
    
    diff_data = get_latest_diff(args.repo_path)
    if not diff_data:
        print("[ERROR] Could not get diff data. Exiting.")
        sys.exit(1)
        
    runtime_issue_description = (
        "The APK compiles successfully without errors. However, at runtime, the application "
        "fails to launch and halts completely before the initial N64 logo and intro sequence are rendered. "
        "There are no ADB logs available. The project architecture was recently modified to generate the "
        "OTR (Open-To-Right) assets dynamically at runtime on the Android device, completely removing "
        "the dependency on loading a pre-built ROM file. Investigate the codebase for logic locks, "
        "JNI initialization sequence mismatches, Android thread-blocking (ANR) during the OTR "
        "generation phase, or native setup failures."
    )
    
    print("[INFO] Building contextual code map...")
    try:
        context_map = fetch_relevant_files(args.repo_path, diff_data)
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