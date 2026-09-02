---
name: quality-pass
description: Use when asked to review and improve an existing application end-to-end — "clean this up", "remove AI slop", "review for improvements", "is the architecture right", pre-launch hardening, or an inherited/AI-generated codebase that needs a bug hunt, security check, performance pass, dead-code removal, or structural refactoring. Also use when a partial pass (review only, dead-code only) needs the full method as background.
license: MIT
metadata:
  version: "1.0.0"
  runtimes: "claude-code, codex, any agent-skills host"
---

# Quality Pass

Take an existing app from "works" to "solid": **review with evidence, verify every claim, then fix in return-on-effort order, gating and committing each phase.** Validated on three production codebases (React + .NET, React + Node): ~26% first-paint JS cut, multi-tenant data-leak fixes, 3,500–9,000 dead lines removed per pass, ten 1,000–3,900-line pages split, all behavior-preserving.

**Violating the letter of the iron rules is violating their spirit.** There is no "spirit of the rule" shortcut.

## Iron rules (breaking one invalidates the pass)

1. **Baseline first, gate every phase.** Run `scripts/gate.sh --baseline` before touching anything and record what is already red. Typecheck + lint + full tests + production build must be green (or no worse than baseline, with the pre-existing failure named) before each commit. Paste gate output verbatim; never claim done without it.
2. **Verify before acting on any review claim.** Reviews come from read-only reviewers, one per dimension. Re-verify every High/Critical and every destructive claim yourself in the code before acting. Expect at least one reviewer claim per pass to be wrong or overstated. Record rejected claims in the report.
3. **Two patterns before every deletion.** Immediately before deleting a file/export/package: search by path (import string) AND by symbol (identifier, dynamic import, string reference, config/glob reference). Either pattern finding a live user cancels the deletion. Endpoint handlers, DI-registered classes, reflection targets, and files matched by a runner glob are the classic false positives.
4. **Interrupted work is suspect.** If any agent or rewrite was cut off, diff the tree against HEAD before continuing. Compiling is not complete. Behavior silently dropped by a half-finished rewrite is only caught by the original's tests.
5. **Mechanical means mechanical.** In structural refactors, state ownership never moves to hit a line-count target; existing tests must pass unchanged. A failing test after a "mechanical" change means the change altered behavior. Fix the change, never the test.
6. **Replacement tests must be able to fail.** Any test you add or rewrite gets mutation-checked once: break the code it guards and confirm the test goes red. A test that stays green against a broken implementation is deleted, not kept.

## Phase 0 — Setup (5 minutes)

- Create a branch: `quality-pass-YYYY-MM`. Never work on the default branch.
- Run `scripts/gate.sh --baseline` (in this skill's `scripts/` directory). If detection is wrong for the repo, write the real commands to `.quality-pass/gates` (one per line) and rerun.
- Note repo shape: apps, packages, test runners and their globs, build outputs.

## Phase 1 — Review (report only)

Run six reviewers in parallel, each read-only, each covering one dimension from `references/review-dimensions.md`:
slop & honesty · bugs · security & data integrity · performance · dead code · architecture.

- Claude Code: use this plugin's agents, which load as `quality-pass:qp-slop-reviewer`, `quality-pass:qp-bug-hunter`, `quality-pass:qp-security-reviewer`, `quality-pass:qp-perf-reviewer`, `quality-pass:qp-dead-code-reviewer`, `quality-pass:qp-architecture-reviewer`. Give each only the repo path.
- Other runtimes: spawn subagents or fresh sessions with the briefs in `references/reviewer-briefs.md`. If parallelism is unavailable, run them sequentially in fresh contexts; never run all six in one context.

Then **you** verify (rule 2) and consolidate into `references/report-template.md`: ranked by severity, `file:line` evidence, measured numbers, a "rejected on verification" section, and a "deliberately not doing" section. Present the plan and **stop for approval before Phase 2** unless the user already granted it.

## Phase 2 — Execute, in this order, one gated commit per step

1. **Security and bug fixes** — smallest diffs, highest value. Include authz/tenant scoping gaps, teardown-on-logout gaps, silent reconnect death, unbounded page sizes.
2. **Bundle and render wins** — measured from the built output, never guessed.
3. **Dead-code sweep** — rule 3 per target; delete the tests of deleted code; remove now-unused packages; re-run the full gate after the last deletion.
4. **Behavior tests for the 2–3 scariest invariants** — test the real modules, not copies; rule 6 applies.
5. **Structural refactors** — only the recipes in `references/refactor-recipes.md`, rule 5 applies. Default posture for big migrations: slice-first for new code, strangler for hot spots, never big-bang.

## Phase 3 — Hand-off

Write the final report (same template, with what shipped, what was rejected, what was deliberately deferred and why) to the repo's docs or the runtime's memory, so the next session continues the policy: new code follows the new structure, old code migrates when touched. Then run `scripts/gate.sh` one last time and paste it.

## Style rules for fixes

One brand name, one accent system, one icon library, both themes. Honest copy only: replace invented numbers, testimonials, and status badges with verifiable product facts or delete them. Look at anything before deleting or overwriting it.

## Red flags — stop and re-check

| Thought | Reality |
|---|---|
| "The reviewer marked it certain" | Reviewers are wrong about one thing every pass. Open the file. (rule 2) |
| "Pattern 1 found nothing, ship the delete" | Pattern 2 is what catches handlers, DI, reflection, globs. (rule 3) |
| "It compiles, the split must be done" | Run the original's tests. (rules 4, 5) |
| "Moving this state gets the page under N lines" | Line counts never justify ownership moves. (rule 5) |
| "Tests fail but the refactor is right" | The refactor changed behavior. Fix it. (rule 5) |
| "The new test passes, good enough" | Break the code; if the test stays green it tests nothing. (rule 6) |
| "Typecheck was already red, so red is fine" | Only the named pre-existing failure is fine. New reds block. (rule 1) |
| "This is a small pass, skip the branch/baseline" | Small passes delete files too. Phase 0 is five minutes. |

## Related skills in this plugin

- `quality-pass-review` — Phase 1 only, no code changes.
- `quality-pass-execute` — Phase 2 from an approved report.
- `quality-pass-dead-code` — the deletion sweep on its own.
- `quality-pass-gate` — run and report the gate verbatim.
