# review.py
import sys
import subprocess
import json
import os
from review_lib import get_code_to_review, create_diff_review_prompt, call_ollama

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
APP_PY_PATH = os.path.join(SCRIPT_DIR, "app.py")

def main():
    try:
        # Check for changes in diff mode
        code_chunks = get_code_to_review(full_file_mode=False)
        if not code_chunks:
            sys.exit(0) # No changes, success.

        # run the first review without GUI
        diff_content = code_chunks[0]['content']
        prompt = create_diff_review_prompt(diff_content)
        review_data = call_ollama(prompt)

        # Check for AI errors or if there are no findings
        if review_data is None or "findings" not in review_data:
            print("AI Reviewer Error: Could not get valid data from the LLM.")
            sys.exit(1)

        findings = review_data["findings"]
        if not findings:
            sys.exit(0)

        findings_json_string = json.dumps(review_data)
        
        process = subprocess.run(
            [sys.executable, APP_PY_PATH, findings_json_string]
        )

        sys.exit(process.returncode)

    except Exception as e:
        print(f"An unexpected error occurred in the pre-commit hook: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()