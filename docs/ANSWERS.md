# Notes from the planner

## 2026-11-06 20:35 UTC: line endings (no action needed except committing one file)
Edits on Windows turned several backend files from LF to CRLF, so `git diff` showed whole
files rewritten (e.g. org/api.py: 907 lines instead of 33). I added `.gitattributes`
(`* text=auto eol=lf`). Git now stores LF and the diffs show only real changes.
**Include `.gitattributes` in your next M3 commit.** No need to convert files by hand.
