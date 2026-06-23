import subprocess
import os

def get_latest_diff(repo_path):
    try:
        os.chdir(repo_path)
        
        diff_cmd = ["git", "diff", "HEAD~1", "HEAD"]
        diff_output = subprocess.check_output(diff_cmd, text=True)
        
        files_cmd = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
        files_output = subprocess.check_output(files_cmd, text=True).splitlines()
        
        logs_cmd = ["git", "log", "-n", "5", "--oneline"]
        logs_output = subprocess.check_output(logs_cmd, text=True)
        
        return {
            "diff": diff_output,
            "modified_files": files_output,
            "commit_history": logs_output
        }
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git operation failed: {e}")
        return None

def get_build_logs(log_file_path):
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            return f.read()
    return "No build logs found."
