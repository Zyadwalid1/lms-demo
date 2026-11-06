# Design reference: approved mockups and screen specs

`mockups/` holds every approved mockup, compressed to ~250 KB each. The originals are in
`E:\Kent\LearnHub screens`. The file names say which milestone and screen each belongs to.
**Open the relevant mockups before building a screen, and compare your screenshot with them
before calling it done.**

## How to use the mockups (the user chose "mockups, refined")
Follow them for:
- **layout**: what's on the page, where, and in what order;
- **content**: which data, KPIs, columns, actions and filters appear;
- **density**: how much fits on the screen.

These differences are **intentional**. Don't copy the mockup in these ways:

| Mockup shows | We build |
|---|---|
| Flat white/lilac page backgrounds | Custom artwork on every page (`Backdrop`), shapes clear of the text |
| Light mode only | Light **and** dark, both checked |
| Static screens | The agreed motion: View Transitions, skeleton cross-fade, stagger, living numbers, micro-interactions |
| Stock photos of people (avatars, hero, instructors) | Initials avatars or the user's own avatar URL. No photos of real people. Course thumbnails come from data. |
| Hard-coded names, numbers, percentages (e.g. "Ayman Badewi", "Your share 75%", commission 70%) | Real API data. Revenue shares, refund policy, prices and commissions are client decisions (`docs/client-questions.md`): display what the API returns, never hard-code it. |
| "Admin reviews refunds" (06) | Built as instant self-service within 30 days. This is an open client question; don't change it. |
| Their colour hexes and fonts | Our tokens in `frontend/src/index.css` and our components in `src/components/ui`. The look should match; the values come from us. |
| Learner sidebar inside a dark rail (04, 14, 42) | Our approved learner layout: site header + light sidebar on desktop, bottom nav on phones |
| Features with no backend yet (see "Gaps" below) | Add the API if it's small and additive (tests + typed). Otherwise list it in `docs/NEEDS-USER.md`. Never fake it in the UI. |

Navigation decisions (09, 10, 16, 17, 41):
- learner: bottom nav on phones;
- instructor and admin: a hamburger drawer on phones and a sidebar on desktop;
- the player: focus mode.

`49` in the originals folder is an unrelated Arabic project: ignore it.

## Mockup index
| # | Screen | Milestone |
|---|---|---|
| 03, 48 | Guest home (48 = final split hero) | done |
| 07, 28, 47, 37 | Catalogue with sidebar filters / mobile drawer; 37 adds **instant search suggestions** (gap) | done / M6 |
| 39, 40 | Minimal course card | done |
| 35 | Course details | done |
| 44 | Basket → sign up → checkout → thank you | done |
| 04, 42 | My learning (42 adds "Upcoming assignments" and "My certificates" panels: gap) | done / M6 |
| 43, 17 | Course player (focus mode) | done |
| 27, 32 | Quiz and assignment, learner side | done |
| 23 | Certificates: learner list, preview, verify, course certificate settings | done (learner); M4 (course settings) |
| 14, 34 | My account (profile, achievements, certificates, orders, subscription, security) | done |
| 06 | Learner orders, subscription, billing and invoices | done |
| 19 | Instructor dashboard | M4 |
| 21 | Create course: quick start, completion checklist | M4 |
| 12 | Course editor: curriculum + video lesson editor (12 also shows external video URL and subtitles: gap) | M4 |
| 08, 11 | Quiz builder: details, settings, question editor | M4 |
| 29 | Assignment builder, submissions list, grading view | M4 |
| 24 | Students and progress | M4 |
| 01 | Sales and earnings | M4 |
| 31 | Payouts and payout methods | M4 |
| 46 | Instructor profile and public preview | M4 |
| 26 | Admin dashboard | M5 |
| 25 | Course approval and moderation | M5 |
| 45 | Course management, all courses with bulk actions (gap: needs a console course-list API) | M5 |
| 05 | Students and instructor management | M5 |
| 22 | Sales and orders | M5 |
| 20 | Subscription plans | M5 |
| 13 | Pricing and promotions | M5 |
| 33 | Commissions and payouts (commission *rules* editing is a client decision) | M5 |
| 30 | Certificate template management (gap: no console API for templates) | M5 |
| 36 | Communications and support: tickets, notifications, announcements, templates | M5 |
| 18 | Platform settings | M5 |
| 02 | Reports and analytics | M5 |
| 15 | Unified design + admin sitemap | all |
| 38 | Design system (final) | all |
| 09, 10, 16, 41 | Navigation decisions (mobile) | all |

## Screens with NO mockup: build them from these specs
Same family as the mockups:
- workspace layout (dark sidebar, header);
- a KPI row of `StatCard`s;
- a filter bar, then a table or cards;
- a right-hand detail sheet;
- artwork at the top.
Compare with the closest mockup named below.

### M3 business workspace (none of it was mocked)
Closest references: 26 (dashboard pattern), 05 (people table + detail panel), 33 (table + side summary).

| Route | Layout |
|---|---|
| `/business/matrix` | KPI strip (compliance %, overdue, expiring 30 days). Filter bar: unit tree, job role, status, requirement, search. Sticky-header table: person column (avatar, name, job title) × requirement columns with coloured status pills; legend under the table. Cell click → right sheet: person, requirement, due/expiry dates, history timeline, actions (Extend, Exempt, Record completion, Void, Remind). Phone: list of people with their worst status → sheet. |
| `/business/requirements` | Cards or rows: name, course thumbnail, targets as chips, compliance ring, overdue count. "New requirement" → sheet form in sections (Course, Schedule, Reminders, Who it applies to). |
| `/business/people` | Like 05: KPI row (people, managers, overdue people, invited), table (name, units, job roles, role, compliance mini-bar, last active), detail sheet with tabs (Profile, Training, Activity). |
| `/business/units` | Two columns: unit tree (indented, drag-free, with actions per node) and a detail panel (managers, people count, compliance %, job roles list). |
| `/business/invites` | Invite form card (emails textarea for bulk, role, unit, job role) + pending invites table with expiry and revoke. |
| `/invite/:token` | Public, aurora artwork: company logo/name card, "You've been invited as …", sign-in/sign-up buttons, then the accept button. States for expired / used / wrong account. |
| `/business/library`, `/business/assign` | Library: course cards like the catalogue (39) with "assigned / completed" counts. Assign: a 3-step stepper like 21's quick start (Course → People and units → Confirm, with a count). |
| `/business/reports` | Like 02: tabs (Compliance, By unit, Audit), charts with living numbers, an "Export CSV" button. |
| `/business/billing` | Like 06's subscription card: plan, seats used/limit bar, renewal, actions (billing portal, add seats). |
| `/business/settings` | Like 18 (settings with sections): branding with a live header preview, colours, logo URL, retention info. |

### M2 learner screens built without a mockup (already done; keep them consistent)
- notifications page;
- help and support tickets;
- achievements (14 shows a small version);
- required training;
- public verify page (23 shows a small version).

### M4 gaps without a mockup
- **Become an instructor** (onboarding form + pending state): use 46's form style.
- **Coupons tab** in the course builder: use 13's promotions table style.
- **Q&A and reviews inbox** (`/studio/questions`): use 36's ticket list + thread pattern.
- **Announcement composer**: a sheet with title and body, plus a preview of how learners see it.
- **Marking queue**: 29 shows it.

### M5 gaps without a mockup
- **Companies**: list + detail sheet with seats, status and entitlements (pattern 05).
- **Currencies and FX rates**, **price tier grid**: an editable table (pattern 13).
- **Moderation** of reviews, questions and answers: list + hide/show with a reason (pattern 25).
- **Audit log**: a filterable table with an expandable JSON detail.
- **System health**: a status grid (green/amber/red tiles) on the dashboard.
