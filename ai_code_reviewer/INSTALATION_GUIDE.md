# AI Code Reviewer - Quick Reference Card

## 🚀 Installation Commands

### First Time Setup (in any git repository)

**All platforms (Windows/Linux/Mac):**
```bash
cd /path/to/your/repo
python /path/to/ai_code_reviewer/setup.py install
```

**Or specify the repo path:**
```bash
python /path/to/ai_code_reviewer/setup.py install /path/to/your/repo
```

---

## ✅ Verify Installation

```bash
python check_installation.py
```

This checks:
- Python version
- Git availability
- Required dependencies
- Ollama connection
- Configuration files
- Hook installation

---

## 🎮 Daily Usage

### Make a commit (with AI review):
```bash
git add .
git commit -m "Your message"
# GUI appears automatically
```

### Skip the AI review (emergency):
```bash
git commit --no-verify -m "Quick fix"
```

### Re-run review manually:
Click "Re-run Review" button in GUI

### Review full files instead of diffs:
Check "Review Full Files" checkbox in GUI

---

## ⚙️ Configuration

Edit `ai_code_reviewer/.env`:

```env
# Change the AI model
LLM_MODEL=llama3:8b

# Change Ollama URL (if not localhost)
OLLAMA_URL=http://localhost:11434/api/generate
```

**Install a model:**
```bash
ollama pull llama3:8b
```

---

## 🗑️ Uninstallation

```bash
cd /path/to/repo/with/hook
python /path/to/ai_code_reviewer/setup.py uninstall
```

---

## 🔧 Troubleshooting

### "Cannot connect to Ollama"
```bash
# Start Ollama server
ollama serve

# Check if running
curl http://localhost:11434/api/tags
```

### "Missing dependencies"
```bash
pip install requests python-dotenv sv-ttk
```

### Hook not executing
```bash
# Check if hook exists
ls -la .git/hooks/pre-commit

# Make executable (Linux/Mac)
chmod +x .git/hooks/pre-commit
```

### GUI doesn't show
```bash
# Install GUI dependency
pip install sv-ttk
```
