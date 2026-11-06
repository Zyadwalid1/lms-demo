# How the two Claude sessions work together

- **Planner** (Claude in the desktop app / Cowork, project "New LMS"): writes the
  milestone briefs, keeps the decisions and the client questions, and reviews finished
  work in this folder.
- **Builder** (Claude Code, run in this folder): builds from the brief, tests, verifies,
  and records the result in `docs/build-status.md`.

## The loop for each milestone
1. The planner writes `docs/milestones/<id>-<name>.md`.
2. In this folder run `claude`, then type `/milestone <id>` (for example `/milestone M3`).
   It reads CLAUDE.md, the brief and the status, then builds, tests and verifies.
3. When it's done, tell the planner "<id> built". The planner checks it here (tests,
   diff, screenshots) and writes `docs/milestones/<id>-review.md` with fixes, if any.
4. In Claude Code: "apply docs/milestones/<id>-review.md", then `/verify`.

## Useful commands inside Claude Code
| Command | What it does |
|---|---|
| `/milestone M3` | Build a milestone end to end |
| `/verify` | All checks: tests, lint, migrations, types, build, E2E, phone |
| `/sync-types` | Regenerate the frontend API types after backend changes |
| `/status` | Update docs/build-status.md |
| "use the reviewer agent" | Security / rules review of the current changes |

## Safety built in
- `.claude/settings.json` blocks reading `.env` files, asks before `migrate`, `pip/npm install` and `git push`.
- `.claude/hooks/guard.py` blocks `migrate --fake`, destructive SQL, `manage.py flush` and broad deletes.
- `.claude/hooks/lint_python.py` runs ruff on every backend file Claude edits.
- Database changes on Neon that alter existing data always come to you first.
