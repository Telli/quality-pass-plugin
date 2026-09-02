---
name: quality-pass-gate
description: Use when asked whether the build is green, before claiming a change is done, or before any commit during a quality pass — runs typecheck, lint, full tests, and the production build and reports the results verbatim.
license: MIT
metadata:
  version: "1.0.0"
  part-of: quality-pass
---

# Quality Pass — Gate

Run `../quality-pass/scripts/gate.sh` (sibling skill directory) from the repo root and paste its summary block unchanged.

- First run in a repo: `gate.sh --baseline` so later runs diff against it.
- Wrong detection (monorepo, custom scripts): write `.quality-pass/gates` with one command per line, then rerun. Commit that file; it is the team's definition of green.
- `gate.sh --print` shows what would run without running it.

## Reporting rule

Report the summary lines exactly as printed. A FAIL is reported as FAIL with the last 40 lines of its log, even if you believe it is pre-existing; say "pre-existing (in baseline)" next to it only when `.quality-pass/baseline.txt` shows the same gate failing. Never summarize a failing gate as "mostly passing".
