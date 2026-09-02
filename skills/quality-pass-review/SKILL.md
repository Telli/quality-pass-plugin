---
name: quality-pass-review
description: Use when asked to review, audit, or assess an existing codebase for problems without changing it yet — "what's wrong with this repo", "review before we refactor", "give me a prioritized list", or when a quality pass needs approval before any fixes.
license: MIT
metadata:
  version: "1.0.0"
  part-of: quality-pass
---

# Quality Pass — Review only (Phase 1)

Produce the ranked, evidence-backed report and stop. No code changes, no deletions, no "quick fixes while I'm here".

**REQUIRED BACKGROUND:** the `quality-pass` skill in this plugin defines the iron rules; rules 1 and 2 apply here. Its `references/` directory (sibling skill directory `../quality-pass/references/`) holds the dimension checklists, reviewer briefs, and report template.

## Steps

1. **Baseline gate.** Run `../quality-pass/scripts/gate.sh --baseline` from the repo root (write `.quality-pass/gates` first if detection is wrong). Paste the summary. Pre-existing reds are recorded, not fixed.
2. **Six read-only reviewers in parallel**, one per dimension: slop & honesty, bugs, security & data integrity, performance, dead code, architecture. Claude Code: agents `quality-pass:qp-slop-reviewer`, `quality-pass:qp-bug-hunter`, `quality-pass:qp-security-reviewer`, `quality-pass:qp-perf-reviewer`, `quality-pass:qp-dead-code-reviewer`, `quality-pass:qp-architecture-reviewer`, all dispatched in one message so they run concurrently. Elsewhere: use the briefs in `../quality-pass/references/reviewer-briefs.md`; sequential fresh contexts if parallelism is unavailable.
3. **Verify yourself.** Open the file for every CRITICAL/HIGH finding and every deletion candidate. Confirm or reject with evidence. Expect at least one rejection; if you found none, look harder before reporting.
4. **Write the report** using `../quality-pass/references/report-template.md`, including "Rejected on verification" and "Deliberately not doing".
5. **Stop.** End with the execution plan and the sentence: "Approve to continue with `quality-pass-execute`."

## Output shape

The deliverable is the report file (e.g. `docs/quality-pass/YYYY-MM-DD.md`) plus a 10-line summary in chat: top 5 findings with `file:line`, the baseline gate status, and the count of rejected reviewer claims.

## Red flags

- "This one is trivial, I'll just fix it" — no. The value of a review-only pass is that nothing moved.
- "Reviewer confidence: certain" — verify anyway.
- Zero rejected claims — the verification step was skipped.
