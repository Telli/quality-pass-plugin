---
name: quality-pass-gate
description: Use when asked whether the build is green, before claiming a change is done, or before any commit during a quality pass — runs typecheck, lint, full tests, and the production build and reports the results verbatim.
license: MIT
metadata:
  version: "1.1.0"
  part-of: quality-pass
---

# Quality Pass — Gate

Read [gate configuration and comparison](../quality-pass/references/gate-configuration.md). Run `../quality-pass/scripts/gate.sh` from the repo root and paste its summary block and baseline comparison unchanged. Standalone packages carry local `scripts/gate.sh`, `scripts/gate.py`, and `scripts/gate.ps1`.

- First run in a repo: `gate.sh --baseline` records HEAD, configuration, counts, identities, and failure details. Preserve the original baseline; replacement requires deliberate review and `--replace-baseline`.
- Wrong detection (monorepo, custom scripts): write `.quality-pass/gates` with one command per line, then rerun. Commit that file; it is the team's definition of green.
- `gate.sh --print` shows what would run without running it.
- `--project` selects nested projects explicitly; `--timeout` sets per-gate limits. Use native argv in `.quality-pass/gates.json` on Windows; shell strings require Bash.

## Reporting rule

Report FAIL, TIMEOUT, MISSING_TOOL, NO_TESTS, ERROR, and optional SKIP distinctly. A FAIL remains FAIL with the last 40 log lines. Call it pre-existing only when current-run structured evidence identifies the same failures/details and the comparison is verified. Matching red command names are insufficient: report **failure equivalence unknown** otherwise. Include actual test counts and unavailable/unrun checks; zero executed tests do not validate a test workflow.
