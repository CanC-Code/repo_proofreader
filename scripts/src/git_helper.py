import subprocess
import os

def get_latest_diff(repo_path):
    try:
        os.chdir(repo_path)
        
        # Ensure HEAD exists in the repository
        try:
            subprocess.check_call(["git", "rev-parse", "--verify", "HEAD"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print("[WARNING] HEAD does not exist (empty repository).")
            return None

        # Dynamically locate the deepest available commit ancestor up to HEAD~15
        base_commit = None
        for depth in range(15, 0, -1):
            try:
                subprocess.check_call(["git", "rev-parse", "--verify", f"HEAD~{depth}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                base_commit = f"HEAD~{depth}"
                break
            except subprocess.CalledProcessError:
                continue

        if base_commit:
            diff_cmd = ["git", "diff", base_commit, "HEAD"]
            files_cmd = ["git", "diff", "--name-only", base_commit, "HEAD"]
        else:
            # Fewer than 2 commits available; diff HEAD against the empty tree SHA
            EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            diff_cmd = ["git", "diff", EMPTY_TREE_SHA, "HEAD"]
            files_cmd = ["git", "diff", "--name-only", EMPTY_TREE_SHA, "HEAD"]

        diff_output = subprocess.check_output(diff_cmd, text=True, errors='replace')
        
        MAX_DIFF_CHARS = 12000
        if len(diff_output) > MAX_DIFF_CHARS:
            diff_output = diff_output[:MAX_DIFF_CHARS] + "\n...[DIFF TRUNCATED DUE TO SIZE]..."
        
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
