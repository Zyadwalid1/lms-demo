"""PreToolUse guard for Bash: blocks the commands this project never allows.
Exit code 2 = block, and the message goes back to Claude so it can change course."""

import json
import re
import sys

try:
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(0)  # never break the session over a malformed payload

RULES = [
    (r"migrate\b.*--fake", "Never use `migrate --fake`. Fix the migration instead."),
    (r"\b(DROP\s+(TABLE|SCHEMA|DATABASE|ROLE|COLUMN)|TRUNCATE\b|ALTER\s+TABLE\s+\S+\s+DROP)", "Destructive SQL is not allowed. Ask the user."),
    (r"\bDELETE\s+FROM\b", "Deleting rows directly is not allowed. Ask the user."),
    (r"(cat|type|Get-Content|more|less|head|tail|grep|findstr|Select-String)\s+[^|;&]*\.env(?!\.example)(\.\w+)?(\s|$|\")", "Do not read .env files: secrets stay out of the conversation."),
    (r"\b(printenv|env)\s*$|\bGet-ChildItem\s+env:", "Do not dump environment variables (they hold secrets)."),
    (r"flush\b.*--database|manage\.py\s+flush", "`manage.py flush` wipes data. Not allowed."),
    (r"rm\s+-rf\s+(/|~|\.\s|\.$|\*)", "Refusing a broad rm -rf."),
    (r"Remove-Item\b.*-Recurse\b.*(\s\.|\s\*|\s[A-Za-z]:\\)", "Refusing a broad recursive delete."),
]
for pattern, message in RULES:
    if re.search(pattern, cmd, re.IGNORECASE):
        print(f"Blocked by project guard: {message}", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
