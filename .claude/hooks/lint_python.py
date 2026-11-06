"""PostToolUse: after Claude edits a backend .py file, fix and format it with ruff, and
report anything ruff cannot fix (exit 2 shows it to Claude). Frontend files are checked
by `npx tsc -b` in /verify (too slow to run on every edit)."""

import json
import os
import shutil
import subprocess
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
path = (data.get("tool_input") or {}).get("file_path") or ""
if not path.endswith(".py") or "backend" not in path.replace("\\", "/"):
    sys.exit(0)

# the project root, whatever folder the shell happens to be in
root = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd(), "backend")
venv = [os.path.join(root, d, sub, exe) for d in ("venv", ".venv") for sub, exe in (("Scripts", "ruff.exe"), ("bin", "ruff"))]
ruff = next((p for p in venv if os.path.exists(p)), shutil.which("ruff"))
if not ruff:
    sys.exit(0)

subprocess.run([ruff, "format", path], cwd=root, capture_output=True)
r = subprocess.run([ruff, "check", "--fix", path], cwd=root, capture_output=True, text=True)
if r.returncode != 0:
    print(f"ruff found problems in {path}:\n{r.stdout[-3000:]}", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
