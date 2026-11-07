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

