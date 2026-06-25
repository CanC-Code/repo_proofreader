import os
import sys
import argparse
import json
from src.git_helper import get_latest_diff
from src.context_retriever import fetch_relevant_files
from src.llm_client import query_reasoning_engine

def main():
    # Force absolute paths to ensure the engine finds the Android project regardless of CWD
    workspace_root = os.getenv('GITHUB_WORKSPACE', os.getcwd())
    
    print(f"[DEBUG] Workspace root identified as: {workspace_root}")
    
    # Run from the repository root, not the engine's sub-directory
    repo_path = workspace_root
    
    diff_data = get_latest_diff(repo_path)
    
    # HARD DEBUG: If diff is empty, don't exit, force a scan of the whole repo
    if not diff_data:
        print("[WARNING] No git diff detected. Running Full Repo Diagnostic...")
        diff_data = {'modified_files': []}
        
    runtime_issue_description = (
        "White Screen Hang: The app launches, ROM extraction succeeds, but 2 seconds later it "
        "deadlocks on a white screen. The Native C++ engine is likely deadlocking the Android Main Thread. "
        "Analyze NativeBridge.cpp and MainActivity.kt to ensure the game loop is on a background thread."
    )
    
    print("[INFO] Building context map...")
    context_map = fetch_relevant_files(repo_path, diff_data, runtime_issue_description)
    
    # FORCE OUTPUT: If the map is empty, print the file list for debugging
    if not context_map:
        print("[ERROR] Context map empty! Files in workspace:")
        print(os.listdir(repo_path))
        sys.exit(1)

    print(f"[INFO] Dispatching analysis for {len(context_map)} files...")
    
    try:
        analysis_result = query_reasoning_engine(diff_data, context_map, runtime_issue_description)
        print("--- LLM DIAGNOSTIC RESULT ---")
        print(json.dumps(analysis_result, indent=2)) # FORCE JSON DUMP TO LOGS
    except Exception as e:
        print(f"[CRITICAL FAILURE] AI Engine Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()