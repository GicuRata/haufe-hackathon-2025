import subprocess
import requests
import json

LLM_MODEL = "llama3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"


def get_staged_diff():
    """Gets the diff of staged files from git."""
    try:
        command = ["git", "diff", "--cached"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        return "" # Return empty string if not a git repo or no commits

def create_diff_review_prompt(diff_content):
    """Creates a structured prompt for an interactive review."""
    return f"""
    You are an expert code reviewer specializing in analyzing `git diffs`. Your task is to find issues in proposed code changes and classify their severity.

    **Rules for Review:**
    1.  **Focus on Added Code (+):** Primarily analyze lines starting with `+`.
    2.  **Ignore Deleted Code (-):** Do NOT report issues on lines starting with `-`.
    3.  **Use Context (space):** Use lines without a prefix for context only.

    **Severity Levels:**
    *   `CRITICAL`: Issues that MUST be fixed before committing. This includes security vulnerabilities (like command injection), major bugs (like index out of bounds), or logic errors that will likely cause a crash.
    *   `SUGGESTION`: Non-blocking issues. This includes style advice (PEP8), naming conventions, minor performance improvements, or opportunities for refactoring to improve readability.

    **Output Format:**
    You MUST provide your response as a single JSON object. The object should have one key, "findings", which is an array of issue objects. Each issue object must have three keys:
    - `severity`: A string, either "CRITICAL" or "SUGGESTION".
    - `line_number`: The approximate line number of the issue in the new file, if applicable.
    - `message`: A clear, one-sentence explanation of the issue.

    **Example of a valid JSON output:**
    ```json
    {{
      "findings": [
        {{
          "severity": "CRITICAL",
          "line_number": 15,
          "message": "Potential command injection vulnerability using `os.system` with user input."
        }},
        {{
          "severity": "SUGGESTION",
          "line_number": 8,
          "message": "Function name 'proces_data' contains a typo and should be 'process_data'."
        }}
      ]
    }}
    ```


    **Diff to Review:**
    ```diff
    {diff_content}
    ```
    """

def call_ollama(prompt, model_name=LLM_MODEL):
    """Sends a prompt to the local Ollama LLM and returns the parsed JSON response."""
    try:
        data = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        response = requests.post(OLLAMA_URL, json=data)
        response.raise_for_status()
        
        response_json = json.loads(response.json()['response'])
        return response_json
            
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return None # Return None on any error

def get_code_to_review(full_file_mode=False):
    """
    Gets the code to be reviewed.
    Returns a list of dictionaries, each with 'filename' and 'content'.
    In diff mode, returns one entry with the full diff.
    In full file mode, returns one entry per staged file.
    """
    staged_files_command = ["git", "diff", "--cached", "--name-only"]
    staged_files_result = subprocess.run(staged_files_command, capture_output=True, text=True)
    if not staged_files_result.stdout.strip():
        return []

    files_to_review = []
    filenames = staged_files_result.stdout.strip().split('\n')

    if full_file_mode:
        for filename in filenames:
            # The ':' tells git to get the content from the staging area (index)
            file_content_command = ["git", "show", f":{filename}"]
            file_content_result = subprocess.run(file_content_command, capture_output=True, text=True)
            files_to_review.append({"filename": filename, "content": file_content_result.stdout})
    else: # Diff mode
        diff_command = ["git", "diff", "--cached"]
        diff_result = subprocess.run(diff_command, capture_output=True, text=True)
        files_to_review.append({"filename": "Staged Diff", "content": diff_result.stdout})
        
    return files_to_review

def create_full_file_review_prompt(filename, code_content):
    """Creates a prompt for reviewing a full source file."""
    return f"""
    You are an expert code reviewer. Your task is to perform a complete review of the following source file.

    **File Name:** `{filename}`

    **Instructions:**
    Review the code below for potential bugs, security vulnerabilities, style issues (e.g., PEP8), and violations of clean code principles. Provide your feedback as a JSON object with a "findings" array, following the specified format.

    **Output Format:**
    - `severity`: "CRITICAL" or "SUGGESTION".
    - `line_number`: The line number of the issue.
    - `message`: A clear explanation of the issue.
    If no issues are found, return `{{"findings": []}}`.

    **Source Code:**
    ```
    {code_content}
    ```
    """



    
def create_chat_prompt(code_context, conversation_history):
    """Creates a prompt for a follow-up conversation about a finding."""
    
    history_str = ""
    for message in conversation_history:
        role = "AI Assistant" if message['role'] == 'assistant' else 'User'
        history_str += f"{role}: {message['content']}\n"

    return f"""
    You are an AI code review assistant engaged in a conversation with a developer about a git commit or a specific piece of code.

    **Original Code Snippet Under Review:**
    ```
    {code_context}
    ```

    **Conversation So Far:**
    {history_str}

    **Your Task:**
    Continue the conversation by responding to the last user message. Be helpful, concise, and stay on topic. If the user provides context for their code, acknowledge it and re-evaluate your suggestion if necessary.
    """


def call_ollama_chat(prompt, model_name=LLM_MODEL):
    """Sends a chat prompt to the LLM and gets a plain text response."""
    try:
        data = {"model": model_name, "prompt": prompt, "stream": False}
        response = requests.post(OLLAMA_URL, json=data)
        response.raise_for_status()
        
        response_data = response.json()
        return response_data.get('response', "Error: AI response was empty.")
    
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return "Sorry, I encountered an error and could not respond."