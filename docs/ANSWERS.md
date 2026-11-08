# Notes from the planner

## 2026-11-06 20:35 UTC: line endings (no action needed except committing one file)
Edits on Windows turned several backend files from LF to CRLF, so `git diff` showed whole
files rewritten (e.g. org/api.py: 907 lines instead of 33). I added `.gitattributes`
(`* text=auto eol=lf`). Git now stores LF and the diffs show only real changes.
**Include `.gitattributes` in your next M3 commit.** No need to convert files by hand.

## 2026-11-07: M5 is now the complete console (read before starting)
- `docs/milestones/M5-console.md` was rewritten: **every control in the 12 console mockups must work** (no M6 leftovers,
  Reports included, no split). The control-by-control list is `docs/milestones/M5-gaps.md`; tick it as you go.
- The user approved one additive migration set (listed in the brief) and 2-step sign-in via `allauth.mfa`.
- **Lean verification for M5** (brief section V overrides the definition of done for M5 only). Write `e2e_m5.js`
  but run it, with `e2e_m4.js`, in a later "Verification pass M4 + M5".
- First commit the uncommitted M4 work as "M4 studio: built, verification pending".

## 2026-11-08: planner review of M5 (do these, then commit "M5 review fixes")
Answers to NEEDS-USER are at the bottom of that file (migrations: you run them; QR: yes; invites list: yes).
1. Run the migrations and seeds on dev, then e2e (see NEEDS-USER).
2. Re-run `npx tsc -b` and `npx vite build` (types were regenerated after the last run) and the studio tests
   (`studio.py` changed in P20).
3. 2-step sign-in QR code (server-side SVG with the installed `qrcode`).
4. Studio: instructors pick a certificate template for a course and submit their own for approval (API exists).
5. `seed_console_demo`: create instructor earnings for its seeded orders (adds rows only), so commissions,
   balances and payouts match sales.
6. Settings > default currency decides a new visitor's first currency.
7. Pending instructor invitations: list, resend, cancel.
8. Fix the "103 tests" line in the build-status table.
Lean checks as in M5 section V.

