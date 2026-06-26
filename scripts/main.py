import os
import sys
import argparse
import json
from src.git_helper import get_latest_diff
from src.context_retriever import fetch_all_files_batched
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
    parser.add_argument(
        "--issue_description",
        required=False,
        default=(
            "General code quality review: analyze all files for bugs, logic errors, "
            "threading issues, null pointer risks, resource leaks, and architectural flaws. "
            "Identify the highest-severity problem and provide a complete corrected file."
        ),
        help="Description of the known issue or type of analysis to perform."
    )
    args = parser.parse_args()

    workspace_root = os.getenv('GITHUB_WORKSPACE', os.path.abspath(args.repo_path))
    print(f"[DEBUG] Workspace root identified as: {workspace_root}")

    repo_path = workspace_root
    issue_description = args.issue_description

    print(f"[INFO] Issue description: {issue_description}")

    diff_data = get_latest_diff(repo_path)
    if not diff_data:
        print("[WARNING] No git diff detected. Running Full Repo Diagnostic...")
        diff_data = {'modified_files': [], 'diff': '', 'commit_history': ''}

    print("[INFO] Fetching full repository file batches for recursive analysis...")
    all_batches = fetch_all_files_batched(repo_path, diff_data)

    if not all_batches:
        print("[ERROR] No source files found in the repository. Aborting.")
        sys.exit(1)

    total_files = sum(len(b) for b in all_batches)
    print(f"[INFO] Repository fully indexed: {total_files} files across {len(all_batches)} analysis pass(es).")

    all_results = []

    for pass_num, context_map in enumerate(all_batches, start=1):
        print(f"\n[INFO] === PASS {pass_num}/{len(all_batches)}: Analyzing {len(context_map)} files ===")

        try:
            analysis_result = query_reasoning_engine(diff_data, context_map, issue_description)

            print(f"\n--- [LLM DIAGNOSTIC RESULT - PASS {pass_num}] ---")
            print(json.dumps(analysis_result, indent=2))
            print("-------------------------------\n")

            all_results.append({
                "pass": pass_num,
                "files_analyzed": list(context_map.keys()),
                "result": analysis_result
            })

        except Exception as e:
            print(f"[CRITICAL FAILURE] Engine Exception on pass {pass_num}: {e}")
            all_results.append({
                "pass": pass_num,
                "files_analyzed": list(context_map.keys()),
                "result": None,
                "error": str(e)
            })
            continue

    # Select the highest-confidence patch across all passes
    print("\n[INFO] === SELECTING BEST PATCH ACROSS ALL PASSES ===")
    best_result = None
    best_file_path = None
    best_fix = None

    for entry in all_results:
        result = entry.get("result")
        if not result:
            continue
        patch_plan = result.get('patch_plan', {})
        file_path = patch_plan.get('file_path')
        suggested_fix = patch_plan.get('suggested_fix')
        if file_path and suggested_fix and file_path != "N/A" and suggested_fix != "N/A":
            best_result = result
            best_file_path = file_path
            best_fix = suggested_fix
            break  # Prefer earliest (highest-priority) pass with a valid patch

    if not best_file_path or not best_fix:
        print("[FAILURE] No valid patch plan produced across any analysis pass.")
        print("[INFO] Full multi-pass summary:")
        for entry in all_results:
            print(f"  Pass {entry['pass']}: {len(entry['files_analyzed'])} files | "
                  f"error={entry.get('error', 'none')} | "
                  f"patch={'yes' if entry.get('result') and entry['result'].get('patch_plan', {}).get('file_path', 'N/A') != 'N/A' else 'no'}")
        sys.exit(1)

    cleaned_code = clean_markdown_code(best_fix)

    print(f"\n[SUCCESS] AI proposed a logical fix for: {best_file_path}")
    print("======================================================================")
    print(f"vvv FULL REPLACEMENT FILE FOR: {best_file_path} vvv")
    print("======================================================================")
    print(cleaned_code)
    print("======================================================================")
    print(f"^^^ END OF FILE: {best_file_path} ^^^")
    print("======================================================================\n")

    print("[INFO] Analysis complete. Replace your local file with the output above.")


if __name__ == "__main__":
    main()
