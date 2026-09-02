# Quality pass — <repo> — <YYYY-MM-DD>

Branch: `quality-pass-YYYY-MM` off `<default>@<sha>`
Baseline gate: <PASS/FAIL per gate, verbatim summary line from scripts/gate.sh --baseline; name any pre-existing failure>

## Verified findings (ranked; every item re-checked by the author, not just the reviewer)

| # | Sev | Dimension | Finding | Where | Evidence | Fix size |
|---|-----|-----------|---------|-------|----------|----------|
| H1 | HIGH | security | ... | `path:line` | ... | S/M/L |

## Rejected on verification

Reviewer claims that were wrong or overstated, with why. (There is always at least one. If this section is empty, the verification step was skipped.)

- <claim> — rejected because <evidence>

## Measured performance facts

Numbers from the built output / profiles, before values only at this stage.

## Dead-code candidates

Each with pattern-1 result (path importers) and pattern-2 result (symbol/string/glob references). Only items with both results empty are eligible. List "NOT dead" surprises too.

## Architecture: do-not-touch list and approved-shape changes

## Execution plan (needs approval)

1. Security + bugs: ...
2. Bundle/render: ...
3. Dead code: ...
4. Invariant tests: ...
5. Structural: ...

---

# After execution — append

## Shipped (per gated commit)

- `<sha>` <phase>: <what>, gate: <verbatim summary line>

## Deliberately not done

Each with the reason (cost > benefit at team size, blocked by X, needs a product decision). This section is what lets the next session continue the policy instead of re-deriving it.

## Policy going forward

New code follows <structure>. <Hot files> migrate when next touched. Open follow-ups: ...
