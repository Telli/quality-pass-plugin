---
name: quality-pass-review
description: Use when asked to review, audit, or assess an existing codebase for problems without changing it yet — "what's wrong with this repo", "review before we refactor", "give me a prioritized list", or when a quality pass needs approval before any fixes.
license: MIT
metadata:
  version: "1.1.0"
  part-of: quality-pass
---

# Quality Pass — Review only (Phase 1)

Produce the ranked, evidence-backed report and stop. No code changes, no deletions, no "quick fixes while I'm here".

**REQUIRED BACKGROUND:** read [quality-pass rules](../quality-pass/SKILL.md), [targeted coverage](../quality-pass/references/review-scope.md), and [evidence records](../quality-pass/references/finding-records.md). Rules 1 and 2 apply. These resources are bundled locally in standalone distributions.

## Steps

1. **Scope and baseline.** Accept a base branch/PR diff, paths/globs, or feature scope. Resolve concrete seeds and run `../quality-pass/scripts/review.py scope --base origin/main --mode standard` (or `--files`/`--feature`). Default to standard for a target and full otherwise; quick focuses on bugs/security. Resume with `review.py status`. Run `../quality-pass/scripts/gate.sh --baseline` if no JSON baseline exists. Paste the summary and record identified failures or unknown equivalence.
2. **Scoped read-only reviewers**, one per selected dimension. Standard/full use slop, bugs, security, performance, dead code, architecture; quick uses bugs/security. Claude Code uses this plugin's `qp-*` agents; other hosts use `../quality-pass/references/reviewer-briefs.md`. Pass reviewed commit, seeds, mode, boundaries, and exclusions. Follow affected callers, tests, authorization boundaries, and contracts beyond the diff. Report actual coverage; use parallel or sequential fresh contexts as the host supports.
3. **Verify every claim yourself.** Confirm, reject, or label suspected with a reproduction/measurement, command, and observed result. Persist each claim with `../quality-pass/scripts/review.py record`. Zero rejections is valid; an absent verification record is not.
4. **Write the report** using [the template](../quality-pass/references/report-template.md), with stable IDs, scope limits, per-finding records, rejected claims (possibly none), and deliberately deferred work. Keep suspected/stale claims outside the action plan and reuse unchanged accepted/dismissed findings.
5. **Stop.** End with the execution plan and the sentence: "Approve to continue with `quality-pass-execute`."

## Output shape

The deliverable is the report file (e.g. `docs/quality-pass/YYYY-MM-DD.md`) plus a 10-line summary in chat: top 5 findings with `file:line`, the baseline gate status, and the count of rejected reviewer claims.

## Red flags

- "This one is trivial, I'll just fix it" — no. The value of a review-only pass is that nothing moved.
- "Reviewer confidence: certain" — verify anyway.
- Missing verification records, unrun reproductions described as demonstrated, or a targeted pass described as a whole-codebase audit.
