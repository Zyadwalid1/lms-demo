"""Stop hook: keep Claude Code working until docs/goal.md is complete.

Lets Claude stop when:
  - every checklist box in docs/goal.md is ticked, or
  - docs/NEEDS-USER.md exists (it is waiting for the user's answer), or
  - nothing has changed (goal, status, git HEAD, working tree) across 3 blocked stops in a row:
    a safety valve so a stuck session can't loop forever.
Otherwise it blocks the stop and says what to do next."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
GOAL = ROOT / "docs" / "goal.md"
NEEDS = ROOT / "docs" / "NEEDS-USER.md"
STATE = ROOT / ".claude" / "hooks" / ".goal_state.json"

try:
    json.load(sys.stdin)
except Exception:
    pass

if not GOAL.exists():
    sys.exit(0)
text = GOAL.read_text(encoding="utf-8")
open_items = re.findall(r"^- \[ \] (.+)$", text, re.MULTILINE)
if not open_items:
    sys.exit(0)  # goal reached
if NEEDS.exists() and NEEDS.read_text(encoding="utf-8").strip():
    sys.exit(0)  # waiting for the user


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return ""


status = ROOT / "docs" / "build-status.md"
fingerprint = hashlib.sha256(
    (text + (status.read_text(encoding="utf-8") if status.exists() else "") + git("rev-parse", "HEAD") + git("status", "--porcelain")).encode()
).hexdigest()
try:
    state = json.loads(STATE.read_text())
except Exception:
    state = {}
stuck = state.get("count", 0) + 1 if state.get("fp") == fingerprint else 0
STATE.write_text(json.dumps({"fp": fingerprint, "count": stuck}))
if stuck >= 3:
    print(json.dumps({"systemMessage": "Goal gate: no progress after 3 attempts - letting the session stop. Check docs/build-status.md."}))
    sys.exit(0)

reason = (
    f"The goal in docs/goal.md is not finished. Next item: {open_items[0]}. "
    "Keep going: apply any unapplied docs/milestones/*-review.md first, then continue that milestone "
    "(/milestone <id>), meeting the full Definition of done in CLAUDE.md. Tick the box only when it is met, "
    "then commit and push the branch. If you are truly blocked on the user, write the question with your "
    "recommended answer to docs/NEEDS-USER.md, finish everything that does not depend on it, then stop."
)
print(json.dumps({"decision": "block", "reason": reason}))
sys.exit(0)
