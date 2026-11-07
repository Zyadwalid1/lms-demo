# Build status

Maintained by Claude Code (`/status`) and read by the planner session. Newest milestone first.

## Where things stand (2026-11-06)
| Area | State |
|---|---|
| Backend | Complete for the demo: 102 tests, ruff clean. All learner/business/studio/console APIs exist. |
| M0 foundation | Done: design system (`/design`), layouts, sign-in, workspace switcher, home, course page, My learning, HR compliance overview |
| M1 marketplace | Done |
| M2 learning | Done |
| M3 business | **In progress**: API typed; screens being built (see M3 below) |
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

## M3 business (in progress)
- **P1 done:** every `/api/v1/org/` and `/api/v1/compliance/` endpoint is typed (both prefixes in `TYPED_PREFIXES`; `export.csv` in `NOT_JSON`). Additive: `compliance/people/{id}` now returns `units`, `job_roles`, and `requirement_id` on records/exemptions; `org/invitations/{token}` returns `role`. Tests added; ruff clean. No new migrations.
- **Frontend groundwork:** `lib/page-art.ts` (route `handle: { art }` now works in workspace areas too); the workspace header search is real (business: goes to `/business/people?q=`), and hidden where an area has no search; `BusinessLayout`; shared org hooks in `features/org/api.ts`; all business routes + `/invite/:token` in the router.
- **Type generation without a running server:** `tools/dump_openapi.py` writes the schema, then `openapi-typescript ../logs/openapi.json` (see `/sync-types`).
- **E2E fixture:** `tools/harness/e2e_org.py` builds a fresh company (admin, units, learners, courses, requirement), so M3 E2E needs no demo password.
- **Screens built (P2–P10):** matrix (+ person/requirement sheet with Extend, Exempt/Revoke, Record, Void, Remind), requirements (sheet form, archive), reports (by requirement, by unit, audit trail, CSV), people + person page, locations & teams (tree, managers, job roles), invitations + public `/invite/:token`, library + 3-step assign, billing, settings with runtime branding (sidebar accent + header logo; tokens untouched). New artwork: `chartgrid`, `orgchart`, `floorplan`.
- **More additive API (with tests):** `people_overdue` on the dashboard; `manager_ids` on units; person history keeps revoked exemptions (`revoked_at`) and `void_reason`; `dry_run` on `org/assign` (exact count for the confirm step).
- **Reviewer findings fixed (backend):** managers got the whole company's unit tree (now only their units); archived requirements' cells leaked into the matrix (status filter and phone "worst status"); matrix and people lists were in UUID order (now alphabetical, keyset on name + id); person view and assignments added to the query-budget test.
- **Invite flow:** "Create an account" remembers the invite; after email confirmation the verify page offers "Continue to your invitation".
- **Harness:** `e2e_wsgi.py` records `email<TAB>token` in `invite.log` when the API enqueues the invite email (the token is never stored or logged by the app); `e2e_verify_key.py` recomputes allauth's HMAC confirmation key.
- **Lesson:** never run two Django test processes at once against Neon: they share the `test_*` database and fail with deadlocks/duplicate keys.

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
1. M3 business (brief ready).
2. M4 studio, including marking assignments (the backend `grade_submission` exists; learners are notified) and replying to Q&A and reviews.
3. M5 console, M6 polish (check the main bundle size: ~520 KB minified / 160 KB gzipped).
4. Deployment.
