import subprocess
import os

def commit_and_push_patch(repo_path, analysis_result):
    """
    Commits the verified patch to the active branch and pushes to the remote.
    """
    os.chdir(repo_path)
    
    try:
        subprocess.check_call(["git", "add", "-u"])
        
        # Use the LLM's root cause analysis as the commit context
        reason = analysis_result.get('root_cause_analysis', 'Automated architectural fix applied.')
        commit_message = f"fix: AI Proofreader resolution\n\n{reason}"
        
        subprocess.check_call(["git", "commit", "-m", commit_message])
        
        print("[INFO] Pushing fixed code to remote branch...")
        subprocess.check_call(["git", "push"])
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to commit or push the verified patch: {e}")
