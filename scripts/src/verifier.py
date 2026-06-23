import subprocess
import os
import shlex

def run_local_verification(repo_path, patch_plan):
    os.chdir(repo_path)
    
    try:
        with open("proposed_fix.patch", "w") as f:
            f.write(patch_plan['suggested_fix'])
            
        subprocess.check_call(["git", "apply", "--check", "proposed_fix.patch"])
        subprocess.check_call(["git", "apply", "proposed_fix.patch"])
    except subprocess.CalledProcessError as e:
        print("[ERROR] Patch could not be applied cleanly.")
        return False, "Patch failed to apply to the current Git tree."

    build_cmd_str = os.environ.get("BUILD_COMMAND", "make all")
    build_cmd = shlex.split(build_cmd_str)

    try:
        print(f"[INFO] Building with command: {build_cmd_str}")
        output = subprocess.check_output(build_cmd, stderr=subprocess.STDOUT, text=True)
        print("[SUCCESS] Build passed verification.")
        return True, output
    except subprocess.CalledProcessError as e:
        print("[FAILURE] Build failed with proposed patch.")
        subprocess.call(["git", "checkout", "."])
        return False, e.output
