# Build status

Maintained by Claude Code (`/status`) and read by the planner session. Newest milestone first.

## Where things stand (2026-11-07)
| Area | State |
|---|---|
| Backend | Complete for the demo: 103 tests, ruff clean. All learner/business/studio/console APIs exist. |
| M0 foundation | Done: design system (`/design`), layouts, sign-in, workspace switcher, home, course page, My learning, HR compliance overview |
| M1 marketplace | Done |
| M2 learning | Done |
| M3 business | Done |
| M4 studio, M5 console, M6 polish | To do |
| Deployment | To do: production migrate + seed, public webhooks (Stripe, Bunny), Azure CORS |

## Migrations the user must run on Neon
- `python manage.py migrate --database owner`: engagement **0005** (M2): inserts the "work_marked" notification wording. Adds only.

## Settings still needed
- Azure storage account → Resource sharing (CORS) → Blob service: allow the frontend origin, methods PUT/GET/HEAD, headers `*`. Without it, browser file uploads fail (assignment hand-ins, and later studio files).
- Google/Microsoft sign-in: app registrations (`MICROSOFT_LOGIN_*`, `GOOGLE_*`); the buttons appear automatically.

## Live service checks (all PASS; they never print secrets)
| Service | Check |
|---|---|
| Azure Blob (learnhubfilesdemo / lmsdemo-resources) | `python manage.py check_storage` |
| Stripe test sandbox "KBC sandbox" | `python manage.py stripe_setup` |
| Microsoft Graph email (MAIL_MODE console for now) | `python manage.py check_mail <address>` |
| Bunny Stream library 798627 | `python manage.py check_bunny` |

Local Stripe webhooks: `stripe listen --forward-to localhost:8000/api/v1/commerce/webhooks/stripe --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.expired,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,invoice.paid`

---

## M3 business (done)
- **Screens (all `/business/*` placeholders replaced):**
  - training matrix: KPI strip, URL filters (`unit`, `role`, `status`, `req`, `q`), sticky header/column, keyset "Load more", legend; cell → side sheet with the person's requirement: Extend, Exempt / Revoke, Record completion, Void, Send reminder, history timeline; phone = list of people by worst status;
  - requirements: compliance ring, targets as chips, sheet form (Course, Schedule, Reminders, Who it applies to), archive with confirmation; read-only for managers;
  - reports: by requirement, by location, audit trail (admins), CSV export with unit filter;
  - people (KPIs, filters, keyset) and person page (Profile / Training tabs, role and unit edits, remove with confirmation);
  - locations & teams: tree with per-node actions, managers picker, job roles;
  - invitations (single or bulk) and the public `/invite/:token` page (expired/used, wrong account, sign up → confirm email → back to the invite → accept → company workspace);
  - course library (assigned/completed, progress sheet) and 3-step assign with an exact count;
  - billing (plan, seats, portal, buy seats via the M1 team-plan flow) and company settings with live branding preview.
- **Runtime branding:** company colours tint the sidebar's active item and the header (CSS variables on the layout root and the phone drawer only; tokens untouched; text colour picked for contrast). Logo shown when it is an https link.
- **Layout:** `lib/page-art.ts` lets any workspace route pick its artwork (`handle: { art }`); the header search is real (business → `/business/people?q=`) and hidden where an area has none. New artwork: `chartgrid` (reports), `orgchart` (people, invites), `floorplan` (units).
- **API (all additive, typed, tested; no migrations):**
  - every `/api/v1/org/` and `/api/v1/compliance/` endpoint is typed (both in `TYPED_PREFIXES`; `export.csv` in `NOT_JSON`);
  - person view: `units`, `job_roles`, `requirement_id` on records/exemptions, `void_reason`, revoked exemptions kept as history (`revoked_at`);
  - `org/invitations/{token}` returns `role`; units return `manager_ids`; dashboard returns `people_overdue`; `org/assign` accepts `dry_run`.
- **Bugs found and fixed:**
  - managers received the whole company's unit tree (now only their own units);
  - archived requirements' cells leaked into the matrix (status filter, phone worst status);
  - people and matrix lists were in UUID order (now alphabetical: keyset on name + id);
  - the header search box did nothing;
  - unit detail claimed "no training" for sites/teams (now per-unit summary);
  - removing a person flashed an error page; admins were offered "remove yourself";
  - role badges stayed stale after assigning managers; invite redirect used the invited role instead of the real one; a dead pending invite could be offered after email confirmation;
  - CSV download could be cancelled in Firefox/Safari; compliance actions waited for every list to refetch;
  - unit pickers indented by company depth for managers; custom radio groups had no arrow-key support;
  - `/business/units` overflowed on phones (implicit grid column);
  - `serve.py` never started the Celery worker when `REDIS_URL` lives in `backend/.env` (requirement statuses never computed in E2E);
  - a killed test run left rows in the reused test database (the test base now truncates once at the start of each run).
- **Verified:**
  - backend: full suite 103 tests OK (32 min on Neon), ruff clean, `makemigrations --check` clean, query budgets now cover the person view and assignments;
  - `tsc -b` and `vite build` pass; main chunk 384 KB (115 KB gzip), unchanged;
  - `tools/harness/e2e_m3.js`: 21 steps covering acceptance 1–10 (admin, manager and learner, invite sign-up with real email confirmation, CSV header, audit, billing, branding, phone); `e2e_m1.js` and `e2e_m2.js` re-run green;
  - phone overflow + light/dark screenshots on every business route and the invite page: `node tools/harness/phone_business.js shots/phone` (builds its own company, so no demo password is needed); screenshots checked against the specs and mockups 26/05/33.
- **Reviewer:** run on the whole M3 change; all 16 findings fixed (listed above).
- **Harness additions:** `e2e_org.py` (fresh company), `e2e_wsgi.py` records `email<TAB>token` in `invite.log` when the API enqueues an invite (the app never stores or logs the token), `e2e_verify_key.py` (allauth's HMAC confirmation key), `stop.py` (stops the harness processes), `phone_business.js`; `phone_check.js` can switch company (`E2E_DEMO_ORG`).
- **Type generation without a running server:** `tools/dump_openapi.py` writes `logs/openapi.json`; then `npx openapi-typescript ../logs/openapi.json -o src/api/schema.d.ts` in `frontend/`.
- **Lessons:** never run two Django test processes at once against Neon (shared `test_*` database: deadlocks, duplicate keys); Django 5.2 calls `_fixture_setup` at class level, so hook `setUpClass`.

## M2 learning (done)
- **Player** `/learn/:slug/lecture/:key`; `/learn/:slug` resumes; `/learn/:slug/qa/:id` and `/announcements/:id` are notification links.
  - Curriculum sidebar on desktop, drawer on phones; progress ring; prev/next.
  - Finishing the course shows a celebration dialog with the certificate.
- **Lecture kinds:**
  - video: Bunny iframe + player.js; resume, real watch time every 30 s and on leave; placeholder with manual complete when not uploaded;
  - reading, external link, download;
  - live session (countdown; join link from 15 min before);
  - quiz: 7 answer types, timer with auto-submit, drafts survive a reload, review after submitting;
  - assignment: text, https link, up to 5 files sent directly to Azure; rubric; feedback.
- **Tabs:** overview + files, notes (pinned to video time), Q&A, announcements, review.
- **Pages:**
  - certificates (PDF, verify link) and public `/verify/:code`;
  - achievements;
  - required training (per company);
  - notifications page and bell;
  - settings (profile, time zone, currency, password, notification preferences, companies);
  - support tickets.
- **Backend additions:**
  - typed responses for learning/engagement/identity;
  - reloadable quiz review;
  - `my/courses?slug=`;
  - `my-review`, `my/badges`;
  - assignment file uploads (`apps/learning/uploads.py` + purge job);
  - notifications for certificate issued and work marked;
  - badges for personal completions;
  - name sanitising;
  - free enrolment goes straight to the player;
  - order items carry the course slug.
- **Bugs fixed:**
  - the workspace bell was a fake dot;
  - the review-reply link 404'd;
  - badges could get the wrong name;
  - the file purge would have crashed on hand-ins;
  - the quiz result was lost after submit;
  - a stale-cache redirect after enrolling;
  - a self-vote error;
  - an 800 KB icon bundle.
- **Verified:** `tools/harness/e2e_m2.js` (18 steps, every lecture kind, desktop + phone), M1 E2E re-run, phone overflow check, light/dark screenshots.

## M1 marketplace (done)
- **Built:**
  - catalogue filters (sidebar + phone drawer), chips, sort, grid/list, infinite load;
  - course page buy modes;
  - cart with coupon + currency;
  - Stripe checkout + thank-you polling;
  - plans (personal trial, team seats, billing portal);
  - wishlist;
  - purchase history with refunds.
- **Verified:** `tools/harness/e2e_m1.js`.

## STANDING RULES (from the user; apply to every milestone)
1. **Artwork on every page** (no flat backgrounds): see `frontend/README.md` for the variant per area.
2. **Motion**:
   - View Transitions;
   - skeleton cross-fade;
   - stagger;
   - living numbers;
   - micro-interactions;
   - subtle (150-300 ms), reduced motion respected.
3. **Design**: the approved mockups, refined; light and dark mode.
4. **Security and data**:
   - secrets only in `.env`;
   - the app never uses `lms_owner`;
   - no `--fake`;
   - Neon only gains tables, columns and rows; anything touching existing data → ask the user.

## Working rules learned (bugs these prevent)
- Duplicate Ninja schema class names silently corrupt the OpenAPI types → the contract test.
- React Query mutation callbacks don't fire if the component unmounts → derive views from server state, not local flags set in `onSuccess`.
- Never decide a redirect from cached data while it's refetching.
- Grid children need `min-w-0`; tables with `sr-only` need a `relative` wrapper (phone overflow).
- Celery must run (with Redis) for badges and emails; tests run tasks eagerly.
- Import icons one by one (the whole lucide set is ~800 KB).

## Next
1. M3 business: done (planner review welcome).
2. M4 studio, including marking assignments (the backend `grade_submission` exists; learners are notified) and replying to Q&A and reviews.
3. M5 console, M6 polish (check the main bundle size: ~520 KB minified / 160 KB gzipped).
4. Deployment.
