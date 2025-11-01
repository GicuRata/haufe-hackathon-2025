import subprocess
import requests
import json
from rich.console import Console
from rich.markdown import Markdown

LLM_MODEL = "llama3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"

def get_staged_diff():
    """Gets the diff of staged files from git."""
    command = ["git", "diff", "--cached"]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result.stdout

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
    If you find NO issues, return an empty array: `{{"findings": []}}`.

    **Diff to Review:**
    ```diff
    {diff_content}
    ```
    """
    
    
def call_ollama(prompt):
    """Sends a prompt to the local Ollama LLM and returns the parsed JSON response."""
    console = Console()
    with console.status("[bold green]The AI is performing a review...[/bold green]"):
        try:
            data = {
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json" 
            }
            response = requests.post(OLLAMA_URL, json=data)
            response.raise_for_status()
            
            response_json = json.loads(response.json()['response'])
            return response_json
            
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error: Could not connect to Ollama.[/bold red]\nDetails: {e}")
            return None
        except json.JSONDecodeError:
            console.print("[bold red]Error: Failed to decode JSON from AI response.[/bold red]")
            console.print("The model may have failed to produce valid JSON. Check the Ollama server logs.")
            return None
        

def main():
    """Main function to run the code reviewer."""
    import sys
    import os
    from rich.table import Table

    console = Console()

    try:
        diff = get_staged_diff()
        if not diff.strip():
            # No changes to review, exit successfully.
            # Pre-commit framework will show "(no files to check)Skipped".
            sys.exit(0)

        prompt = create_diff_review_prompt(diff)
        review_data = call_ollama(prompt)

        if review_data is None or "findings" not in review_data:
            console.print("[bold red]Failed to get a valid review from the AI. Aborting commit.[/bold red]")
            sys.exit(1)

        findings = review_data["findings"]

        if not findings:
            console.print("[bold green]>> LGTM! No issues found by the AI.[/bold green]")
            sys.exit(0)

        # Separate findings into critical and suggestions
        critical_issues = [f for f in findings if f.get('severity') == 'CRITICAL']
        suggestions = [f for f in findings if f.get('severity') == 'SUGGESTION']

        console.print("\n--- [bold magenta]AI Review Feedback[/bold magenta] ---\n")

        # Display findings in a extremely beautiful table
        table = Table(title="Code Review Summary")
        table.add_column("Severity", justify="left", style="cyan", no_wrap=True)
        table.add_column("Line", justify="center", style="magenta")
        table.add_column("Message", justify="left", style="white")

        for issue in critical_issues:
            table.add_row("[bold red]CRITICAL[/bold red]", str(issue.get('line_number', 'N/A')), issue.get('message', ''))
        for issue in suggestions:
            table.add_row("[yellow]Suggestion[/yellow]", str(issue.get('line_number', 'N/A')), issue.get('message', ''))

        console.print(table)

        # --- Decision Logic ---
        if critical_issues:
            console.print("\n[bold red]>> CRITICAL issues found. Commit aborted.[/bold red]")
            sys.exit(1)

        # Check for the SKIP environment variable if there are suggestions
        if suggestions:
            # os.environ.get("SKIP", "") returns the value or an empty string if not set
            skip_variable_value = os.environ.get("SKIP", "")
            
            # Check if our hook ID or 'all' is in the SKIP variable
            if 'ai-code-review' in skip_variable_value or 'all' in skip_variable_value:
                console.print("\n[bold green]>> Suggestions found, but bypassed by user. Proceeding with commit.[/bold green]")
                sys.exit(0)
            else:
                console.print("\n[bold yellow]>> AI has offered suggestions. To bypass, commit with:[/bold yellow]")
                console.print("[bold cyan]   SKIP=ai-code-review git commit ...[/bold cyan]")
                console.print("[bold yellow]>> Aborting commit.[/bold yellow]")
                sys.exit(1)

    except subprocess.CalledProcessError:
        console.print("[red]Error: Not a git repository or no commits yet.[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()