import subprocess
import os

def get_latest_diff(repo_path):
    """
    Extracts the diff of the latest commit to identify exactly what changed.
    In a PR environment, this fetches the diff between the current branch and main.
    """
    try:
        os.chdir(repo_path)
        
        # Get the diff of the last commit
        diff_cmd = ["git", "diff", "HEAD~1", "HEAD"]
        diff_output = subprocess.check_output(diff_cmd, text=True)
        
        # Get the list of modified files
        files_cmd = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
        files_output = subprocess.check_output(files_cmd, text=True).splitlines()
        
        # Get recent logs for context (last 5 commits)
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
    """
    Reads the specific build log file provided by the CI environment.
    """
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            return f.read()
    return "No build logs found."
