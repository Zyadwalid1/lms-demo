# Questions for the user

1. **Course language (M4 Details tab).** The brief asks for a "language" field, but `catalog.courses` has no language column. Adding one is an additive migration (a new column with default `'en'`), so it needs `migrate --database owner` on dev and e2e.
   **Recommended:** yes, add `language` (ISO code, default `en`) in M6 or after the planner's review. Until then the Details tab leaves it out.

2. **Money screens vs mockups 01 and 31 (no API yet, not small).** Mockup 01 shows gross sales, number of courses sold, a transaction list and trends. Mockup 31 shows "request a payout", a payout schedule or minimum amount, more than one payout method and the next payout date. Stripe Connect onboarding is also missing: instructors type their `acct_` id. These depend on payout rules that are client questions.
   **Recommended:** leave them out of the demo; ask the client how payouts should work (schedule, minimum, on-request or automatic) and build them after that.

3. **Prerequisite lesson (mockup 12).** "Require students to complete another lesson first" needs a new column on lectures (an additive migration) plus a player rule (locked until the other lesson is done).
   **Recommended:** add it after the M4 review, together with the course language column (question 1), in one migration.
