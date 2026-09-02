---
name: quality-pass-execute
description: Use when an approved quality-pass report (or a user-approved list of verified findings) exists and the fixes now need to be applied in phases with green gates and one commit per phase.
license: MIT
metadata:
  version: "1.0.0"
  part-of: quality-pass
---

# Quality Pass — Execute (Phase 2 + hand-off)

Apply an already-approved plan. If there is no report with verified findings, stop and run `quality-pass-review` first; executing from raw reviewer output violates iron rule 2.

**REQUIRED BACKGROUND:** the `quality-pass` skill in this plugin (iron rules 1, 3, 4, 5, 6 all apply). Recipes live in `../quality-pass/references/refactor-recipes.md`.

## Steps

1. **Confirm the branch and baseline.** On `quality-pass-YYYY-MM`, `.quality-pass/baseline.txt` exists. If not, create both now.
2. **Work the phases in order**, one commit each, gate green (or no worse than the named baseline red) before each commit:
   1. Security + bug fixes (smallest diffs first)
   2. Bundle/render wins (re-measure the built output after; put before/after numbers in the commit message)
   3. Dead-code sweep — run `quality-pass-dead-code` for this step
   4. Behavior tests for the 2–3 scariest invariants (mutation-check each: break the code, watch the test fail, restore)
   5. Structural refactors by recipe only
3. **Per commit**: run `../quality-pass/scripts/gate.sh`, paste the summary line into the commit body, then commit. A failed gate is reported verbatim and fixed before anything else happens.
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
