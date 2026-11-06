# M5 - Admin console (`/console`, platform staff)

**Goal.** Platform staff run the marketplace from `/console`:
- review and publish courses;
- approve instructors;
- manage users and companies;
- handle money (orders, refunds, payouts, currencies, prices, plans, promotions);
- moderate content;
- answer support;
- edit settings and notification templates;
- read the audit log.

**Already there:**
- the `/console` layout (`circuit` artwork, `consoleNav`);
- `RequireRole allowed="staff"`.

Every console route is a `ComingSoon` placeholder; replace them all.

**Backend:** `/api/v1/console/` (and `GET /platform/settings`). Every endpoint is untyped today.

**Mockups:** `docs/design/mockups/` 26, 25, 45, 05, 22, 20, 13, 33, 30, 36, 18, 02. Gaps (no console course list, no certificate template API) and screens without a mockup are in `docs/design/README.md`.

**Demo login:** the seeded staff admin (ask the user).

## Work packages
- **P1 API contract.**
  - Type every `/console/` and `/platform/` endpoint (`Console…` schema names).
  - Add both prefixes to `TYPED_PREFIXES`.
  - Run `/sync-types`.
- **P2 Overview (`/console`):**
  - KPIs from `console/overview`: sales, new users, courses in review, open tickets, payouts due;
  - `console/health` as a status panel (database, cache, queue, storage, Bunny, email, Stripe; green/amber/red);
  - living charts.
- **P3 Course review (`/console/review`):**
  - queue (`review/courses`);
  - review page: the version diff/summary, curriculum, checklist, preview of lectures (reuse the M2 player components read-only where possible);
  - Approve, or Request changes with notes (required);
  - unpublish a live course, with a reason.
- **P4 Instructors (`/console/instructors`):** applications, with approve / reject and a reason.
- **P5 Users (`/console/users`):**
  - search, user detail (enrolments, orders, roles);
  - edit staff/active flags;
  - **anonymise** (GDPR): a typed confirmation phrase, an irreversible warning, and an audit entry.
- **P6 Companies:**
  - list, create a company, edit (name, seats, status);
  - entitlements (DRM add-on etc. via `companies/{id}/entitlements`).
- **P7 Money:**
  - **orders** with search, filters and refunds (reason);
  - **payouts**: approve, or mark failed with a reason; payout accounts: verify;
  - **currencies**: enable/disable; FX rates: manual entry and "refresh";
  - **price tiers**: an amount per currency, as an editable grid;
  - **plans**: prices per currency;
  - **promotions** and coupons: create, delete.
  - Money is shown from minor units with `money()`. Never use floats.
- **P8 Moderation (`/console/reviews`):** reviews, questions and answers, with hide/show and a reason.
- **P9 Support (`/console/tickets`):** a queue by status/category; a ticket thread (reuse M2's thread UI with a staff composer); assign, change status, reply. The learner gets the `ticket_reply` notification.
- **P10 System:**
  - settings (`console/settings`, `PUT /{key}`) with typed editors per value;
  - notification templates (`console/templates`), with `{placeholder}` hints and a preview;
  - audit log (`console/audit`, filters, keyset).

## Rules specific to M5
- Staff only. A company admin or instructor must be refused: test it.
- Every destructive or money action needs:
  - a confirmation;
  - a reason field where the API takes one;
  - an audit entry visible afterwards in `/console/audit`.
- Things that are client decisions are shown as data, never hard-coded: revenue shares, refund policy, prices.
- New artwork:
  - review queue: **"stamp / approval seal"** (new);
  - money: **coin stacks** (from M4);
  - support: **bubbles** (existing);
  - system: **circuit** (existing).

## Acceptance (`tools/harness/e2e_m5.js`)
1. Staff signs in → overview KPIs and the health panel render.
2. Approve the instructor application created by a harness script.
3. Review a submitted course: request changes (the instructor sees the notes in the studio) → re-submit → approve → live.
4. Refund an order item. The learner loses access; the order shows refunded.
5. Approve a payout, and mark another as failed.
6. Change a price tier amount for one currency. The catalogue shows the new price in that currency.
7. Hide a review; it disappears from the course page.
8. Answer a support ticket opened by a learner (M2 flow). The learner sees the reply and the notification.
9. Edit a notification template. The next notification uses the new wording.
10. The audit log lists all the above.
11. Non-staff refused. Phone check on every console route. M1–M4 E2E still pass.
