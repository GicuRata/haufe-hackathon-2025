#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import argparse


def get_git_root(path=None):
    if path is None:
        path = os.getcwd()
    
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def is_git_repo(path=None):
    return get_git_root(path) is not None


def install_hook(target_repo_path=None, exclude_dirs=None):
    # Figure out where we're installing
    if target_repo_path:
        target_repo_path = os.path.abspath(target_repo_path)
        if not is_git_repo(target_repo_path):
            print(f"Error: {target_repo_path} is not a git repository.")
            return False
        git_root = get_git_root(target_repo_path)
    else:
        git_root = get_git_root()
        if not git_root:
            print("Error: Not in a git repository.")
            print("Run this from a git repo or specify a path.")
            return False
    
    print(f"Installing in: {git_root}")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Warn if installing in the same repo as the reviewer itself
    if os.path.samefile(git_root, os.path.dirname(script_dir)) or os.path.samefile(git_root, script_dir):
        print("Warning: Installing in the same repo as the reviewer code.")
        print("Make sure to configure excluded directories.")
    
    hooks_dir = os.path.join(git_root, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    
    hook_path = os.path.join(hooks_dir, "pre-commit")
    
    # Don't overwrite without asking
    if os.path.exists(hook_path):
        response = input(f"Pre-commit hook already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return False
        backup_path = hook_path + ".backup"
        shutil.copy2(hook_path, backup_path)
        print(f"Backed up to: {backup_path}")
    
    python_cmd = sys.executable
    
    hook_content = f'''#!/bin/sh
# AI Code Reviewer Pre-commit Hook

REVIEWER_PATH="{os.path.join(script_dir, 'review.py')}"

"{python_cmd}" "$REVIEWER_PATH"
exit $?
'''
    
    with open(hook_path, 'w', newline='\n') as f:
        f.write(hook_content)
    
    # chmod +x on unix
    if os.name != 'nt':
        os.chmod(hook_path, 0o755)
    
    print(f"Hook installed: {hook_path}")
    
    # Create .env if it doesn't exist
    env_path = os.path.join(script_dir, ".env")
    if not os.path.exists(env_path):
        print("\nCreating default .env config...")
        default_env = """# AI Code Reviewer Configuration
LLM_MODEL=llama3:8b
OLLAMA_URL=http://localhost:11434/api/generate
"""
        with open(env_path, 'w') as f:
            f.write(default_env)
        print(f"Created: {env_path}")
        print("Edit this file to customize model and URL.")
    
    # Try to install dependencies
    print("\nChecking dependencies...")
    dependencies = ["requests", "python-dotenv"]
    
    try:
        import requests
        import dotenv
        print("Dependencies OK")
    except ImportError:
        print("Installing dependencies...")
        try:
            subprocess.run(
                [python_cmd, "-m", "pip", "install"] + dependencies,
                check=True
            )
            print("Installed successfully")
        except subprocess.CalledProcessError:
            print("Could not install automatically.")
            print(f"Run: pip install {' '.join(dependencies)}")
    
    # Check for optional GUI stuff
    try:
        import sv_ttk
        print("GUI dependencies OK")
    except ImportError:
        print("\nOptional: pip install sv-ttk for GUI support")
    
    print("\n" + "="*60)
    print("Done!")
    print("="*60)
    print("\nHook will run on every commit.")
    print("To skip: git commit --no-verify")
    print("\nMake sure Ollama is running.")
    
    return True


def uninstall_hook(target_repo_path=None):
    if target_repo_path:
        target_repo_path = os.path.abspath(target_repo_path)
        git_root = get_git_root(target_repo_path)
    else:
        git_root = get_git_root()
    
    if not git_root:
        print("Error: Not a git repository.")
        return False
    
    hook_path = os.path.join(git_root, ".git", "hooks", "pre-commit")
    
    if not os.path.exists(hook_path):
        print("No pre-commit hook found.")
        return False
    
    # Make sure we're removing our hook, not someone else's
    with open(hook_path, 'r') as f:
        content = f.read()
    
    if "AI Code Reviewer" not in content:
        print("Warning: This doesn't look like our hook.")
        response = input("Remove it anyway? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return False
    
    os.remove(hook_path)
    print(f"Removed hook from: {git_root}")
    
    backup_path = hook_path + ".backup"
    if os.path.exists(backup_path):
        response = input("Restore previous hook from backup? (y/n): ")
        if response.lower() == 'y':
            shutil.move(backup_path, hook_path)
            print("Restored previous hook.")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Install or uninstall the AI Code Reviewer git hook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Install in current repository:
    python setup.py install
  
  Install in a specific repository:
    python setup.py install /path/to/repo
  
  Uninstall from current repository:
    python setup.py uninstall
        """
    )
    
    parser.add_argument(
        "action",
        choices=["install", "uninstall"],
        help="Action to perform"
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to git repository (defaults to current directory)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("AI Code Reviewer Setup")
    print("="*60 + "\n")
    
    if args.action == "install":
        success = install_hook(args.path)
    else:
        success = uninstall_hook(args.path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
