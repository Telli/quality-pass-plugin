# Changelog

## 1.2.0 — Unreleased

- Reviewer agents pin model tiers: Claude `opus`/`sonnet` with explicit effort; mapped to `gpt-6.2-astra`/`gpt-6.2-sol` for Codex and `gemini-3.1-pro-preview`/`gemini-3.5-flash` for Gemini CLI via `hosts/models.json`.
- Native Codex custom agents (`~/.codex/agents/qp_*.toml`) and Gemini CLI subagents (`~/.gemini/agents/qp-*.md`) plus `/quality-pass:*` Gemini commands, generated from `agents/` by `scripts/build-host-agents.py` and checked in CI.
- `scripts/install.py` (with `install.sh`/`install.ps1`) installs user-wide for Claude Code, Codex, Gemini CLI, and Antigravity CLI; skills go to the shared `~/.agents/skills`. Re-runs refresh only unmodified files it installed.

## 1.1.0 — Unreleased

- Structured baselines record commits, gate configuration, counts, failure identities/details, and current-run report evidence. Changed failures and reduced execution counts are regressions; unsupported/legacy evidence reports failure equivalence unknown. Existing baselines require explicit replacement.
- Removed the rejection quota. Every claim needs a verification record, and zero rejections is valid.
- Added branch/diff/file/feature scopes and quick, standard, and full modes with explicit coverage limits and affected-boundary tracing.
- Added stable finding IDs, reproducible evidence records, local progress/decision history, stale-approval invalidation, and gated completion. Regression tests accompany bug fixes.
- Generate deterministic self-contained ZIPs validated in isolation. Single-skill installation uses complete standalone copies and preserves modified installations.
- Portable Python gate and installer cores, Bash/PowerShell entry points, recursive project discovery with explicit .NET targets, timeouts, and distinct missing-tool/optional-skip/zero-test outcomes.
- .NET discovery attaches structured test gates only to test projects; relative argv executables resolve against the gate `cwd`; path containment compares resolved roots (Windows short names, macOS `/private` temp dirs); legacy shell gates on Windows use Git Bash rather than the WSL launcher.
- Added regression tests and Linux/Windows CI coverage. Python 3.9+ is now required for the executable tools; legacy Bash gate commands remain supported.

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
