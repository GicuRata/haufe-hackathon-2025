#!/usr/bin/env python3
import os
import sys
import subprocess
import importlib.util

def check_mark(passed):
    return "[OK]" if passed else "[FAIL]"

def test_python_version():
    version = sys.version_info
    passed = version.major == 3 and version.minor >= 7
    print(f"{check_mark(passed)} Python {version.major}.{version.minor}.{version.micro}")
    return passed

def test_git_available():
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        print(f"[OK] Git: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[FAIL] Git not found")
        return False

def test_dependencies():
    required = ["requests", "dotenv"]
    optional = ["sv_ttk"]
    
    all_good = True
    for module in required:
        spec = importlib.util.find_spec(module)
        passed = spec is not None
        all_good = all_good and passed
        print(f"{check_mark(passed)} {module}")
    
    for module in optional:
        spec = importlib.util.find_spec(module)
        passed = spec is not None
        status = "installed" if passed else "not installed"
        print(f"[INFO] {module}: {status} (optional, for GUI)")
    
    return all_good

def test_ollama():
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"[OK] Ollama running")
            if models:
                model_names = ', '.join([m['name'] for m in models[:3]])
                print(f"     Models: {model_names}")
            else:
                print("     Warning: No models. Run: ollama pull llama3:8b")
            return True
        else:
            print("[FAIL] Ollama error")
            return False
    except Exception as e:
        print(f"[FAIL] Cannot connect to Ollama")
        print("       Start it with: ollama serve")
        return False

def test_env_file():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    
    if os.path.exists(env_path):
        print(f"[OK] Config: {env_path}")
        with open(env_path, 'r') as f:
            content = f.read()
            if "LLM_MODEL" in content:
                print("     Has LLM_MODEL")
            if "OLLAMA_URL" in content:
                print("     Has OLLAMA_URL")
        return True
    else:
        print(f"[FAIL] Config not found: {env_path}")
        print("       Run: python setup.py install")
        return False

def test_git_repo():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        git_root = result.stdout.strip()
        hook_path = os.path.join(git_root, ".git", "hooks", "pre-commit")
        
        if os.path.exists(hook_path):
            with open(hook_path, 'r') as f:
                content = f.read()
                if "AI Code Reviewer" in content or "review.py" in content:
                    print(f"[OK] Hook installed: {hook_path}")
                    return True
                else:
                    print(f"[INFO] Found hook but not ours")
                    return False
        else:
            print("[INFO] No hook in current repo")
            print("       Run: python setup.py install")
            return False
    except subprocess.CalledProcessError:
        print("[INFO] Not in a git repo (that's ok)")
        return None

def main():
    print("\n" + "="*60)
    print("AI Code Reviewer - System Check")
    print("="*60 + "\n")
    
    results = []
    
    print("System requirements:\n")
    results.append(test_python_version())
    results.append(test_git_available())
    
    print("\nPython packages:\n")
    results.append(test_dependencies())
    
    print("\nOllama:\n")
    results.append(test_ollama())
    
    print("\nConfiguration:\n")
    results.append(test_env_file())
    
    print("\nGit hook:\n")
    hook_result = test_git_repo()
    if hook_result is not None:
        results.append(hook_result)
    
    print("\n" + "="*60)
    
    valid_results = [r for r in results if r is not None]
    passed = sum(valid_results)
    total = len(valid_results)
    
    if passed == total:
        print(f"All {total} checks passed.")
        print("\nTo install in a repo:")
        print("   cd /path/to/repo")
        print("   python setup.py install")
    elif passed >= total * 0.7:
        print(f"{passed}/{total} checks passed. Fix issues above.")
    else:
        print(f"{passed}/{total} checks passed. Address failures above.")
    
    print("="*60 + "\n")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
