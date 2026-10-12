# Quality pass — <repo> — <YYYY-MM-DD>

Branch: `quality-pass-YYYY-MM` off `<default>@<sha>`
Reviewed commit: `<full SHA>`; base/merge-base: `<branch / SHA or none>`
Scope: `<selected paths / feature>`; mode: `<quick / standard / full>`
Scanned and expanded boundaries: `<paths actually read, callers, tests, auth, contracts>`
Not scanned / unrun checks: `<limits and reasons>`
Baseline gate: <verbatim summary; baseline commit/config hash, counts, identified failures, or failure equivalence unknown>

## Verified findings (ranked; every item re-checked by the author, not just the reviewer)

| ID | Sev | Dimension | Finding | Where | Verification record | Fix size |
|---|-----|-----------|---------|-------|----------|----------|
| QP-<stable hash> | HIGH | security | ... | `path:line` | demonstrated; reproduction, command, expected/actual result | S/M/L |

Every claim has a record with stable ID, reviewed commit, status, quoted/measured evidence, reproduction steps, validation commands, observed result, and watched primary/related files. Keep unproven claims under **Suspected / needs re-verification**, outside the approved execution plan.

## Suspected / needs re-verification

<ID, specific missing evidence, next validation step; zero is valid>

## Rejected on verification

Reviewer claims that were wrong or overstated, with their verification records. Zero rejections is valid: write "None; all claims have verification records." Do not manufacture rejected findings.

- <claim> — rejected because <evidence>

## Measured performance facts

Numbers from the built output / profiles, before values only at this stage.

## Dead-code candidates

Each with pattern-1 result (path importers) and pattern-2 result (symbol/string/glob references). Only items with both results empty are eligible. List "NOT dead" surprises too.

## Architecture: do-not-touch list and approved-shape changes

## Execution plan (needs approval)

1. Security + bugs, with regression tests in the same fix: ...
2. Bundle/render: ...
3. Dead code: ...
4. Additional invariant coverage not already included with fixes: ...
5. Structural: ...

---

# After execution — append

## Shipped (per gated commit)

- `<sha>` <phase>: <finding IDs and what>, gate: <verbatim summary line and results.json path>

## Saved progress

State: `.quality-pass/state.json`; reviewed SHA; approved IDs; completed fix SHAs; gate run paths; stale IDs requiring re-verification. Reuse unchanged accepted/dismissed decisions and record reopened findings after relevant changes.

## Deliberately not done

Each with the reason (cost > benefit at team size, blocked by X, needs a product decision). This section is what lets the next session continue the policy instead of re-deriving it.

## Policy going forward

New code follows <structure>. <Hot files> migrate when next touched. Open follow-ups: ...
