---
description: Regenerate the frontend API types from Django's OpenAPI schema and fix the fallout
---
1. Make sure Django is serving `http://localhost:8000/api/openapi.json` (start `python manage.py runserver` in `backend/` if it isn't).
2. In `frontend/`: `npm run gen:api`. This rewrites `src/api/schema.d.ts`. Never edit that file by hand.
3. Run `npx tsc -b` and fix every error in our code. Don't loosen types to silence them.
4. Report the endpoints and schemas that changed (`git diff --stat frontend/src/api/schema.d.ts` plus a one-line summary).
