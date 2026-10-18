---
name: quality-pass-execute
description: Use when an approved quality-pass report (or a user-approved list of verified findings) exists and the fixes now need to be applied in phases with green gates and one commit per phase.
license: MIT
metadata:
  version: "1.1.0"
  part-of: quality-pass
---

# Quality Pass — Execute (Phase 2 + hand-off)

Apply an already-approved plan. If there is no report with verified findings, stop and run `quality-pass-review` first; executing from raw reviewer output violates iron rule 2.

**REQUIRED BACKGROUND:** [quality-pass rules](../quality-pass/SKILL.md), [refactor recipes](../quality-pass/references/refactor-recipes.md), and [saved finding history](../quality-pass/references/finding-records.md). Iron rules 1, 3, 4, 5, 6 apply. Standalone packages include these resources and the [dead-code checklist](../quality-pass-dead-code/SKILL.md).

## Steps

1. **Confirm saved scope, approval, branch, and baseline.** Run `../quality-pass/scripts/review.py status`, inspect the diff, and re-verify stale records before reusing approval. Use the existing task checkout; create no worktree unless requested. `.quality-pass/baseline.json` records the original commit/configuration and identified failures. Record approval already granted with `review.py approve`; suspected findings cannot be approved.
2. **Work the phases in order**, one commit each, gate green (or no worse than the named baseline red) before each commit:
   1. Security + bug fixes with regression tests in the same commit; demonstrate each test failing with the original bug and passing with the fix
   2. Bundle/render wins (re-measure the built output after; put before/after numbers in the commit message)
   3. Dead-code sweep — follow the bundled dead-code checklist
   4. Additional invariant coverage not already included with fixes (mutation-check each: break the code, watch the test fail, restore)
   5. Structural refactors by recipe only
3. **Per commit**: run `../quality-pass/scripts/gate.sh`, report status/comparison verbatim, then commit. New or unidentified failures, missing tools, timeouts, and coverage reductions block a no-regression claim. After committing, rerun gates and persist the fix SHA, finding IDs, and full result with `../quality-pass/scripts/review.py complete`. Unresolved baseline failures remain recorded instead of being marked completed.
4. **Hand-off**: append "Shipped", "Deliberately not done", and "Policy going forward" to the report; save a pointer in the runtime's memory/notes if it has one; run the gate one last time and paste it.

## Commit message shape

```
qp(<phase>): <what changed in one line>

<why, with the finding id from the report>
Gate: PASS typecheck · PASS lint · PASS test (1162) · PASS build
```

## Red flags

- "I'll batch phases 1–3 into one commit" — no; a revert must be able to target one phase.
- "Tests fail but the refactor is right" — the refactor changed behavior. Fix the change.
- "The interrupted agent's output compiles" — diff against HEAD and run the original tests before continuing.
- "Skip the mutation check, the test obviously works" — a green test against broken code is the most common fake test.
