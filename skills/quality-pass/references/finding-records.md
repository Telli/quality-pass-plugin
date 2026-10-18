# Evidence records and saved progress

The coordinator records every claim, including suspected and rejected claims, in `.quality-pass/state.json`. Reviewers remain read-only. This state is local; keep human reports in the team's chosen location and do not store secrets or sensitive payloads in reproductions.

Stable IDs are `QP-` plus a hash of dimension, repository-relative primary file, and a stable symbol/contract anchor. Line numbers and wording are excluded, so moving lines does not rename a finding. Use the same anchor when rechecking it. Status is `suspected`, `demonstrated`, `rejected`, or `needs-reverification`. Only demonstrated findings are actionable and eligible for approval. Zero rejected claims is valid; every claim still needs its own verification record.

Example JSON input for `scripts/review.py record --input /path/to/finding.json`:

```json
{
  "dimension": "security",
  "title": "Export does not restrict tenant ownership",
  "file": "src/export.py",
  "anchor": "export_report:tenant-ownership",
  "locations": ["src/export.py:42"],
  "related_files": ["src/auth.py", "tests/test_export.py", "pyproject.toml"],
  "verification": {
    "status": "demonstrated",
    "evidence": "The query filters report_id but has no tenant predicate",
    "reproduction": ["Create a report for tenant A in a local fixture", "Request it as tenant B"],
    "validation_commands": ["pytest tests/test_export.py -k cross_tenant"],
    "observed_result": "Tenant B receives tenant A's report; expected 403"
  }
}
```

For suspected findings, say what remains untested. A code inspection can demonstrate a deterministic defect when the precise inputs, execution path, expected/actual result, and repeatable inspection or diagnostic command are recorded. Performance findings need the actual measured output, environment, and command. A failed reproduction rejects or narrows the claim; never invent a rejection or a measurement.

## Resume

1. Run `python scripts/review.py --dir /path/to/app status` and inspect the working diff before continuing. The helper hashes primary and related files, invalidates affected approvals when they change, and marks findings `needs-reverification`. It cannot infer unlisted dependencies: update related files whenever scope expands.
2. Match the reviewed commit and scope to the saved report. Recheck affected evidence and record a fresh finding before requesting or reusing approval. Unchanged accepted/dismissed findings retain their IDs and disposition; do not report them as new.
3. After approval already given by the user, record it with `review.py ... approve QP-<id>`. This command records authorization; running it does not grant authorization.
4. Implement a bug's regression test alongside its fix. Show the test failing against the original bug and passing with the fix. Restore temporary mutations and run the full gate before committing.
5. After the fix commit, run the gates again against that commit. Then `review.py ... complete QP-<id> --fix-commit HEAD --gate-result .quality-pass/latest.json` records the commit and full gate result. Completion requires fresh passing gates and a verified baseline comparison; unresolved baseline failures remain recorded, rather than marked completed.
6. A changed watched file reopens a completed/dismissed finding for re-verification while retaining its prior fixes and decision history. Unrelated changes leave the decision intact.

The state writer is atomic and uses a lock. If interrupted while holding `state.lock`, confirm no writer remains before removing the lock; never overwrite or discard saved progress to get past it.
