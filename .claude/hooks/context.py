"""SessionStart hook (startup, resume, compact): re-orients Claude Code. Its output is
added to the conversation, so after an auto-compaction the goal and rules are never lost."""

import os
import re
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
goal = ROOT / "docs" / "goal.md"
needs = ROOT / "docs" / "NEEDS-USER.md"
lines = ["Project LearnHub LMS. Work from the repo root. Rules: CLAUDE.md (re-read it now if this is after a compaction)."]
if goal.exists():
    text = goal.read_text(encoding="utf-8")
    done = re.findall(r"^- \[x\] (.+)$", text, re.MULTILINE | re.IGNORECASE)
    todo = re.findall(r"^- \[ \] (.+)$", text, re.MULTILINE)
    if todo:
        lines.append(f"ACTIVE GOAL (docs/goal.md): {len(done)} done, {len(todo)} left. Next: {todo[0]}")
        lines.append("Before continuing: read docs/goal.md, docs/build-status.md and the current milestone brief, check `git status` and the last commits, then carry on from where the work stopped.")
    else:
        lines.append("Goal in docs/goal.md is complete.")
if needs.exists() and needs.read_text(encoding="utf-8").strip():
    lines.append("docs/NEEDS-USER.md has open questions for the user: check whether they were answered (the user deletes the file when done).")
print("\n".join(lines))
