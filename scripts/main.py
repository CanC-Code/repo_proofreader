import os
import sys
import argparse
import json
import subprocess
from src.git_helper import get_latest_diff
from src.context_retriever import fetch_relevant_files
from src.llm_client import query_reasoning_engine

def clean_markdown_code(raw_text):
    """Strips markdown code blocks from LLM output."""
    if not raw_text:
        return ""
    
    lines = raw_text.strip().splitlines()
    
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
            
    return "\n".join(lines).strip() + "\n"

def apply_patch_or_replace(repo_path, file_path, new_code):
    """Dynamically applies a unified diff or a full code replacement."""
    full_path = os.path.join(repo_path, file_path)
    cleaned_code = clean_markdown_code(new_code)
    
    if not cleaned_code.strip():
        print("[ERROR] LLM provided empty code block.")
        return False

    if cleaned_code.startswith("--- ") or cleaned_code.startswith("diff --git"):
        print("[INFO] Detected Unified Diff format. Attempting git apply...")
        patch_file = os.path.join(repo_path, "proposed_fix.patch")
        
        with open(patch_file, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)
            
        cwd = os.getcwd()
        try:
            os.chdir(repo_path)
            result = subprocess.run(
                ["git", "apply", "proposed_fix.patch"], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                print(f"[SUCCESS] git apply succeeded on {file_path}")
                return True
            else:
                print(f"[ERROR] git apply failed:\n{result.stderr}")
                return False
        finally:
            os.chdir(cwd)

    else:
        print(f"[INFO] Detected full code replacement block. Overwriting {file_path}...")
        if not os.path.exists(full_path):
             print(f"[ERROR] Target file does not exist: {full_path}")
             return False
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_code)
            print(f"[SUCCESS] Wrote updated code to {file_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to write to {file_path}: {e}")
            return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo_path", required=True)
    args = parser.parse_args()

    print(f"--- [INFO] Initializing Static Analysis Proofreader on {args.repo_path} ---")
    
    diff_data = get_latest_diff(args.repo_path)
    if not diff_data:
        print("[ERROR] Could not get diff data. Exiting.")
        sys.exit(1)
        
    # Inject the specific context of the logical failure
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
        
        # Output the LLM's chain of thought to the GitHub Actions Console for your review
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

        print(f"[INFO] Running local verification of proposed patch for {file_path}...")
        
        success = apply_patch_or_replace(args.repo_path, file_path, suggested_fix)
        
        if success:
            print("[SUCCESS] Logical patch applied successfully.")
            sys.exit(0)
        else:
            print("[FAILURE] Patch failed verification.")
            
    print(" Max retries reached. Unable to resolve the logic failure.")
    sys.exit(1)

if __name__ == "__main__":
    main()