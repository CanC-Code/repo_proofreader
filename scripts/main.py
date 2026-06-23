import argparse
import sys
import os
from src.git_helper import get_latest_diff, get_build_logs
from src.context_retriever import fetch_relevant_files
from src.llm_client import query_reasoning_engine
from src.verifier import run_local_verification
from src.patcher import commit_and_push_patch

def main():
    parser = argparse.ArgumentParser(description="Proofreader Orchestrator")
    parser.add_argument("--repo_path", required=True, help="Path to the target repo")
    parser.add_argument("--log_path", required=False, default="build.log", help="Path to build logs")
    args = parser.parse_args()

    print(f"--- [INFO] Initializing Proofreader on {args.repo_path} ---")

    diff_data = get_latest_diff(args.repo_path)
    error_logs = get_build_logs(os.path.join(args.repo_path, args.log_path))
    
    print("[INFO] Building contextual code map...")
    context_map = fetch_relevant_files(args.repo_path, diff_data)

    max_retries = 3
    attempt = 1

    while attempt <= max_retries:
        print(f"\n--- [INFO] Reasoning Attempt {attempt}/{max_retries} ---")
        
        analysis_result = query_reasoning_engine(diff_data, context_map, error_logs)

        print("[INFO] Running local verification of proposed patch...")
        is_valid, new_logs = run_local_verification(args.repo_path, analysis_result['patch_plan'])

        if is_valid:
            print("[SUCCESS] Patch verified. Committing changes.")
            commit_and_push_patch(args.repo_path, analysis_result)
            sys.exit(0)
        else:
            print("[FAILURE] Patch failed verification.")
            error_logs = f"PREVIOUS PATCH ATTEMPT FAILED WITH:\n{new_logs}"
            attempt += 1

    print("[ERROR] Max retries reached. Unable to resolve the build failure.")
    sys.exit(1)

if __name__ == "__main__":
    main()
