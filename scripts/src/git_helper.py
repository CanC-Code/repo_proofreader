import subprocess
import os

def get_latest_diff(repo_path):
    try:
        os.chdir(repo_path)
        
        diff_cmd = ["git", "diff", "HEAD~15", "HEAD"]
        diff_output = subprocess.check_output(diff_cmd, text=True, errors='replace')
        
        # --- FIX: Hard cap the diff payload to ~5,000 tokens ---
        MAX_DIFF_CHARS = 20000
        if len(diff_output) > MAX_DIFF_CHARS:
            diff_output = diff_output[:MAX_DIFF_CHARS] + "\n...[DIFF TRUNCATED DUE TO SIZE]..."
        
        files_cmd = ["git", "diff", "--name-only", "HEAD~15", "HEAD"]
        files_output = subprocess.check_output(files_cmd, text=True, errors='replace').splitlines()
    
        logs_cmd = ["git", "log", "-n", "15", "--oneline"]
        logs_output = subprocess.check_output(logs_cmd, text=True, errors='replace')
        
        return {
            "diff": diff_output,
            "modified_files": files_output,
            "commit_history": logs_output
        }
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git operation failed: {e}")
        return None

def get_build_logs(log_file_path):
    print(f"[DEBUG] Attempting to read log at: {log_file_path}")
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r', errors='replace') as f:
            content = f.read()
            print(f"[DEBUG] Log file found. Size: {len(content)} bytes")
            return content
    print("[ERROR] Build log file not found! Continuing with Static Analysis.")
    return "No build logs found."