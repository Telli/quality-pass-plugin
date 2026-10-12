# Targeted review and coverage

Accept a base branch/commit, PR diff, explicit paths/globs, or a feature description. Resolve a feature to concrete seed files first. For a PR, use its checked-out branch and the PR base; do not assume the default branch is the base. Record the merge base and reviewed HEAD. An empty diff is valid and does not trigger a full scan.

| Mode | Review coverage | Limits |
|---|---|---|
| quick | Bugs and security in the selected changes, direct callers, relevant tests, authorization boundaries, and contracts | Other dimensions and unrelated code are unreviewed; no unmeasured performance claims |
| standard | All six dimensions within the selected changes and their affected callers, tests, authorization boundaries, and contracts | Unrelated services and repository-wide cleanup are excluded |
| full | All six dimensions across the repository | Explicitly record unread files, unavailable services, and unrun builds/profiles |

Default to standard when a target is supplied and full for a whole-codebase request. A quick pass is available when requested. Do not silently broaden the target to a deletion sweep or migration.

Record seed coverage with the bundled `scripts/review.py` (paths below are relative to this skill, not the application):

```bash
python scripts/review.py --dir /path/to/app scope --base origin/main --mode standard
python scripts/review.py --dir /path/to/app scope --files 'src/auth/*' --feature 'tenant authorization' --mode quick
```

The helper enumerates seed paths; it does not build a dependency graph. Each reviewer follows affected imports/callers, tests, authorization boundaries, schemas, public API contracts, registration/glob/string references, and configuration beyond the diff. Record those expanded paths in the report and finding `related_files`. Include dependency manifests and other relevant configuration in watched files. Explain why each boundary matters and distinguish scanned from merely located files.

Give every reviewer the repository path, reviewed commit, base/selected files, pass mode, expanded boundary paths, and exclusions. Scope constrains the hunt; it never permits skipping a necessary authorization or contract check. If coverage cannot support a conclusion, state that limit.
