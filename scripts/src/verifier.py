import subprocess
import os

def run_local_verification(repo_path, patch_plan):
    """
    Applies the patch plan to the local repository and runs the build command.
    """
    os.chdir(repo_path)
    
    # 1. Apply the patch
    # We use 'git apply' to modify the files in the current workspace
    try:
        with open("proposed_fix.patch", "w") as f:
            f.write(patch_plan['suggested_fix'])
            
        # Check if the patch can be applied cleanly
        subprocess.check_call(["git", "apply", "--check", "proposed_fix.patch"])
        subprocess.check_call(["git", "apply", "proposed_fix.patch"])
    except subprocess.CalledProcessError:
        print("[ERROR] Patch could not be applied.")
        return False

    # 2. Run the build command
    # This assumes your project uses a standard build (e.g., make, mvn, gradle)
    try:
        print("[INFO] Building with patch...")
        # Replace 'make' with your actual project build command
        subprocess.check_call(["make", "all"]) 
        print("[SUCCESS] Build passed verification.")
        return True
    except subprocess.CalledProcessError:
        print("[FAILURE] Build failed with patch.")
        # Revert changes if verification fails
        subprocess.call(["git", "checkout", "."])
        return False
