import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sv_ttk
import sys
import json
import subprocess
import threading
import queue
import traceback
from review_lib import (get_code_to_review, create_diff_review_prompt, 
                          create_full_file_review_prompt, call_ollama, create_chat_prompt,
                          call_ollama_chat)

class App(tk.Tk):
    def __init__(self, initial_findings_data=None):
        super().__init__()
        
        self.initial_findings_data = initial_findings_data
        self.title("AI Code Review Dashboard")
        self.geometry("1200x800")
        sv_ttk.set_theme("dark")

        self.status_var = tk.StringVar(value="Initializing...")
        self.review_queue = queue.Queue()
        self.findings_map = {}
        self.is_chatting = False
        
        self.create_widgets()
        self.load_initial_data()
        self.process_review_queue()
        
    # ... create_widgets is the same ...
    def create_widgets(self):
        # ... (This method has no bugs and does not need to change)
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        control_frame = ttk.LabelFrame(self.main_frame, text="Controls")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        self.review_button = ttk.Button(control_frame, text="Re-run Review", command=self.start_review_thread)
        self.review_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.full_file_mode_var = tk.BooleanVar()
        self.full_file_check = ttk.Checkbutton(control_frame, text="Review Full Files", variable=self.full_file_mode_var)
        self.full_file_check.pack(side=tk.LEFT, padx=10, pady=5)
        self.commit_message_entry = ttk.Entry(control_frame, font=("Segoe UI", 10), width=60)
        self.commit_message_entry.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        self.abort_button = ttk.Button(control_frame, text="Abort Commit", command=self.abort_and_exit)
        self.abort_button.pack(side=tk.RIGHT, padx=5, pady=5)
        self.commit_button = ttk.Button(control_frame, text="Commit Anyway", command=self.commit_and_exit)
        self.commit_button.pack(side=tk.RIGHT, padx=5, pady=5)
        paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        diff_frame = ttk.LabelFrame(paned_window, text="Staged Changes")
        self.diff_text = tk.Text(diff_frame, wrap=tk.WORD, font=("Consolas", 10), background="#2d2d2d", foreground="white", relief="flat", borderwidth=0, highlightthickness=0)
        diff_scrollbar = ttk.Scrollbar(diff_frame, orient="vertical", command=self.diff_text.yview)
        self.diff_text.configure(yscrollcommand=diff_scrollbar.set)
        diff_scrollbar.pack(side="right", fill="y")
        self.diff_text.pack(side="left", fill="both", expand=True)
        paned_window.add(diff_frame, weight=1)
        self.diff_text.tag_configure("addition", foreground="#77dd77")
        self.diff_text.tag_configure("deletion", foreground="#ff6961")
        self.diff_text.tag_configure("header", foreground="#87ceeb", font=("Consolas", 10, "italic"))
        self.diff_text.tag_configure("filename", foreground="#f5a623", font=("Consolas", 12, "bold"))
        right_pane_frame = ttk.Frame(paned_window)
        results_frame = ttk.LabelFrame(right_pane_frame, text="AI Review Findings")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        columns = ("severity", "line", "message")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        self.results_tree.heading("severity", text="Severity")
        self.results_tree.heading("line", text="Line")
        self.results_tree.heading("message", text="Message")
        self.results_tree.column("severity", width=80, anchor='w', stretch=False)
        self.results_tree.column("line", width=50, anchor='center', stretch=False)
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        details_frame = ttk.LabelFrame(right_pane_frame, text="Discussion")
        details_frame.pack(fill=tk.X, expand=False, pady=(5,0))
        self.chat_history_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=8, font=("Segoe UI", 10), background="#2d2d2d", foreground="white", relief="flat")
        self.chat_history_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_history_text.tag_configure("user", foreground="#87ceeb", font=("Segoe UI", 10, "bold"))
        self.chat_history_text.tag_configure("assistant", foreground="#77dd77", font=("Segoe UI", 10, "bold"))
        self.chat_history_text.config(state="disabled")
        chat_input_frame = ttk.Frame(details_frame)
        chat_input_frame.pack(fill=tk.X, expand=True, padx=5, pady=(0,5))
        self.chat_entry = ttk.Entry(chat_input_frame, font=("Segoe UI", 10))
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_entry.bind("<Return>", self.send_chat_message_event)
        self.chat_send_button = ttk.Button(chat_input_frame, text="Send", command=self.send_chat_message)
        self.chat_send_button.pack(side=tk.RIGHT, padx=(5,0))
        paned_window.add(right_pane_frame, weight=1)
        self.results_tree.bind("<Configure>", self.on_resize)
        self.results_tree.bind("<<TreeviewSelect>>", self.on_finding_select)
        status_bar = ttk.Label(self, textvariable=self.status_var, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10)

    def process_review_queue(self):
        try:
            message = self.review_queue.get_nowait()
            status = message.get("status")

            if status == "shutdown":
                if self.review_queue.empty():
                    exit_code = message.get("code", 1)
                    self.destroy()
                    sys.exit(exit_code)
                else:
                    self.review_queue.put(message)
                self.after(100, self.process_review_queue)
                return

            if status == "chat_response":
                finding = message["finding"]
                ai_content = message["content"]
                finding["conversation"].append({"role": "assistant", "content": ai_content})
                self.update_chat_history(finding["conversation"])
                self.is_chatting = False
                self.chat_send_button.config(state="normal")
            
            elif status == "no_changes":
                self.status_var.set("No staged changes found.")
                self.review_button.config(state="normal", text="Re-run Review")
            elif status == "display_code":
                self.display_code(message.get("data"))
            elif status == "update":
                self.status_var.set(message.get("message"))
            elif status == "complete":
                self.display_findings({"findings": message.get("findings")})
                self.review_button.config(state="normal", text="Re-run Review")
        except queue.Empty:
            pass
        self.after(100, self.process_review_queue)

    def commit_and_exit(self):
        commit_message = self.commit_message_entry.get()
        if not commit_message or "Type your commit message" in commit_message:
            messagebox.showerror("Error", "Please enter a valid commit message."); return
        try:
            subprocess.run(["git", "commit", "--no-verify", "-m", commit_message], check=True, capture_output=True, text=True)
            self.review_queue.put({"status": "shutdown", "code": 0})
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Commit Failed", f"Git failed to commit:\n\n{e.stderr}")

    def abort_and_exit(self):
        self.review_queue.put({"status": "shutdown", "code": 1})

    def load_initial_data(self):
        code_chunks = get_code_to_review(full_file_mode=False)
        if code_chunks: self.display_code(code_chunks); code_lines = code_chunks[0]['content'].split('\n')
        else: code_lines = []
        self.commit_message_entry.insert(0, "Type your commit message here...")
        if self.initial_findings_data:
            for finding in self.initial_findings_data.get("findings", []):
                original_message = finding.get("message", "No message provided by AI.")
                finding["conversation"] = [{"role": "assistant", "content": original_message}]
                line_num = finding.get("line_number", 1)
                try:
                    start = max(0, line_num - 3); end = min(len(code_lines), line_num + 2)
                    finding["code_context"] = "\n".join(code_lines[start:end])
                except: finding["code_context"] = "Could not extract code context."
            self.display_findings(self.initial_findings_data)
        else: self.status_var.set("Ready. Click 'Re-run Review' to start.")
    def on_finding_select(self, event):
        if self.is_chatting: return
        selection = self.results_tree.selection()
        if not selection: return
        selected_item_id = selection[0]
        finding = self.findings_map.get(selected_item_id)
        if finding:
            message = finding.get("message", "Details not available.")
            self.status_var.set(f"Discussing: {message}")
            self.update_chat_history(finding.get("conversation", []))
    def send_chat_message(self):
        user_message = self.chat_entry.get()
        if not user_message.strip(): return
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a finding to discuss."); return
        self.chat_entry.delete(0, tk.END)
        self.is_chatting = True; self.chat_send_button.config(state="disabled")
        selected_item_id = selection[0]
        finding = self.findings_map[selected_item_id]
        finding["conversation"].append({"role": "user", "content": user_message})
        self.update_chat_history(finding["conversation"])
        threading.Thread(target=self.run_chat_thread, args=(finding,), daemon=True).start()
    def run_chat_thread(self, finding):
        prompt = create_chat_prompt(finding["code_context"], finding["conversation"])
        ai_response = call_ollama_chat(prompt)
        self.review_queue.put({"status": "chat_response", "content": ai_response, "finding": finding})
    def start_review_thread(self):
        self.review_button.config(state="disabled", text="Reviewing...")
        self.commit_button.config(state="disabled")
        self.status_var.set("Getting code to review...")
        for i in self.results_tree.get_children(): self.results_tree.delete(i)
        self.chat_history_text.config(state="normal"); self.chat_history_text.delete('1.0', tk.END); self.chat_history_text.config(state="disabled")
        threading.Thread(target=self.run_ai_review, daemon=True).start()
    def run_ai_review(self):
        is_full_mode = self.full_file_mode_var.get()
        code_chunks = get_code_to_review(full_file_mode=is_full_mode)
        if not code_chunks: self.review_queue.put({"status": "no_changes"}); return
        self.review_queue.put({"status": "display_code", "data": code_chunks})
        all_findings = []
        for i, chunk in enumerate(code_chunks):
            self.review_queue.put({"status": "update", "message": f"Analyzing chunk {i+1}/{len(code_chunks)}: {chunk['filename']}"})
            prompt_content = chunk["content"]
            prompt = create_full_file_review_prompt(chunk["filename"], prompt_content) if is_full_mode else create_diff_review_prompt(prompt_content)
            review_data = call_ollama(prompt)
            if review_data and "findings" in review_data:
                code_lines = chunk["content"].split('\n')
                for finding in review_data["findings"]:
                    original_message = finding.get("message", "No message provided by AI.")
                    finding["message"] = f'[{chunk["filename"]}] {original_message}'
                    finding["conversation"] = [{"role": "assistant", "content": original_message}]
                    line_num = finding.get("line_number", 1)
                    try:
                        start = max(0, line_num - 3); end = min(len(code_lines), line_num + 2)
                        finding["code_context"] = "\n".join(code_lines[start:end])
                    except: finding["code_context"] = "Could not extract code context."
                all_findings.extend(review_data["findings"])
        self.review_queue.put({"status": "complete", "findings": all_findings})
    def display_code(self, code_chunks):
        self.diff_text.config(state="normal"); self.diff_text.delete('1.0', tk.END)
        for chunk in code_chunks:
            if chunk["filename"] != "Staged Diff": self.diff_text.insert(tk.END, f'--- File: {chunk["filename"]} ---\n\n', "filename")
            if chunk["filename"] == "Staged Diff":
                for line in chunk["content"].split('\n'):
                    if line.startswith('+'): self.diff_text.insert(tk.END, line + '\n', "addition")
                    elif line.startswith('-'): self.diff_text.insert(tk.END, line + '\n', "deletion")
                    elif line.startswith('@@'): self.diff_text.insert(tk.END, line + '\n', "header")
                    else: self.diff_text.insert(tk.END, line + '\n')
            else: self.diff_text.insert(tk.END, chunk["content"] + '\n\n')
        self.diff_text.config(state="disabled")
    def display_findings(self, review_data):
        findings = review_data.get("findings", []); self.findings_map.clear()
        for i in self.results_tree.get_children(): self.results_tree.delete(i)
        if not findings:
            self.status_var.set("Review complete. No issues found!")
            self.commit_button.config(text="Commit", state="normal")
            self.chat_history_text.config(state="normal"); self.chat_history_text.delete('1.0', tk.END)
            self.chat_history_text.insert('1.0', "The AI found no issues in the staged changes.")
            self.chat_history_text.config(state="disabled")
            return
        has_critical = False
        for finding in findings:
            severity = finding.get("severity", "SUGGESTION"); line = finding.get("line_number", "N/A")
            message = finding.get("message", "No message."); tag = "critical" if severity == "CRITICAL" else "suggestion"
            if severity == "CRITICAL": has_critical = True
            item_id = self.results_tree.insert("", tk.END, values=(severity, line, message), tags=(tag,))
            self.findings_map[item_id] = finding
        self.results_tree.tag_configure("critical", background="#5c1b1b"); self.results_tree.tag_configure("suggestion", background="#4a4a28")
        if has_critical:
            # self.status_var.set("CRITICAL issues found. Commit is blocked.")
            # self.commit_button.config(text="Commit Blocked", state="disabled")
            pass
        else:
            self.status_var.set("Suggestions found. Select a finding to discuss.")
            self.commit_button.config(text="Commit with Suggestions", state="normal")
    def on_resize(self, event):
        new_width = event.width - self.results_tree.column("severity", "width") - self.results_tree.column("line", "width")
        if new_width > 200: self.results_tree.column("message", width=new_width - 20)
    def update_chat_history(self, conversation):
        self.chat_history_text.config(state="normal"); self.chat_history_text.delete('1.0', tk.END)
        for message in conversation:
            tag = message['role']
            self.chat_history_text.insert(tk.END, f"{tag.capitalize()}:\n", (tag, "bold"))
            self.chat_history_text.insert(tk.END, f"{message['content']}\n\n")
        self.chat_history_text.config(state="disabled"); self.chat_history_text.yview(tk.END)
    def send_chat_message_event(self, event): self.send_chat_message()
    
if __name__ == "__main__":
    initial_findings = None
    if len(sys.argv) > 1:
        try: initial_findings = json.loads(sys.argv[1])
        except (json.JSONDecodeError, IndexError): pass
    app = App(initial_findings_data=initial_findings)
    app.mainloop()
