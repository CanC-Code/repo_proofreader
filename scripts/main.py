import argparse
import sys
import os
from src.git_helper import get_latest_diff, get_build_logs
from src.context_retriever import fetch_relevant_files
from src.llm_client import query_reasoning_engine
from src.verifier import run_local_verification

def main():
    parser = argparse.ArgumentParser(description="Proofreader Orchestrator")
    parser.add_argument("--repo_path", required=True, help="Path to the target repo")
    parser.add_argument("--log_path", required=False, default="build.log", help="Path to build logs")
    args = parser.parse_args()

    print(f"--- [INFO] Initializing Proofreader on {args.repo_path} ---")

    # 1. [span_1](start_span)Capture the change and build failure logs[span_1](end_span)
    diff_data = get_latest_diff(args.repo_path)
    error_logs = get_build_logs(os.path.join(args.repo_path, args.log_path))
    
    # 2. Context Retrieval: Scan diff for symbols to pull supporting files
    print("[INFO] Building contextual code map...")
    context_map = fetch_relevant_files(args.repo_path, diff_data)

    # 3. [span_2](start_span)Reasoning: Pass logs, diff, and context to the LLM[span_2](end_span)
    print("[INFO] Invoking Reasoning Agent (CoT)...")
    analysis_result = query_reasoning_engine(diff_data, context_map, error_logs)

    # 4. Self-Verification: Apply patch in-memory and test
    print("[INFO] Running local verification of proposed patch...")
    is_valid = run_local_verification(args.repo_path, analysis_result['patch_plan'])

    if is_valid:
        print("[SUCCESS] Patch verified. Committing changes.")
        # Logic to be implemented in patcher.py
    else:
        print("[FAILURE] Patch failed verification. Retrying with refined prompt.")
        sys.exit(1)

if __name__ == "__main__":
    main()
