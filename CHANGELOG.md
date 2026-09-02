# Changelog

## 1.0.0 — 2026-09-02

First packaged release. Derived from the single-file `quality-pass` personal skill, with these changes:

- Split into five skills so phases can run alone: full pass, review-only, execute, dead-code sweep, gate.
- Added a **security & data integrity** review dimension (authz, tenant/owner scoping, enumeration, secrets in responses, unbounded pagination, private-data egress). Previous passes found these under "bugs"; they deserve their own reviewer.
- Six read-only reviewer agents with a fixed output contract (`Where` + `Evidence` required, "Not findings" section, ≤15 items) and a generated mirror of the briefs for non-Claude hosts.
- New iron rules: **baseline gate before touching anything** (pre-existing reds are named, not chased) and **mutation-check every added test** (a replacement test that stays green against broken code is deleted).
- `gate.sh`: detects the toolchain, runs each gate, logs to `.quality-pass/logs/`, diffs against the saved baseline, exits non-zero on any failure. `.quality-pass/gates` overrides detection.
- Report template gained "Rejected on verification" and "Deliberately not done" sections, both mandatory.
- Structural recipes moved to a reference file and gained the façade-first service split and seeder guidance; explicit "not a recipe" list.
- Portable frontmatter only; `agents/openai.yaml` per skill for the Codex picker; `install-codex.sh`.
