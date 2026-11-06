---
description: Run every check - backend tests, lint, migrations, types, build, E2E, phone overflow
---
Run the full verification and report a short table (check, result, details of failures).
Run backend commands from `backend/` with the venv's Python, and frontend commands from `frontend/`.

1. Backend:
   - `python manage.py test core apps`
   - `ruff check .`
   - `ruff format --check .`
   - `python manage.py makemigrations --check --dry-run`. List any new migration files and whether they only ADD things.
2. Frontend:
   - `npx tsc -b`
   - `npx vite build`. Report the size of the largest JS chunks; flag the main `index-*.js` if it grew.
3. E2E: follow `tools/harness/README.md` to start the harness. Never use the shared `dev` branch. Run every `tools/harness/e2e_*.js` script in order (oldest first). $ARGUMENTS
4. Phone overflow: run `node tools/harness/phone_check.js` with every route added in this milestone.

Fix failures caused by the current work, then re-run the failed step. If a failure is
pre-existing or out of scope, say so instead of hiding it.
