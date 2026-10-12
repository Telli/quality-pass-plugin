---
name: quality-pass-dead-code
description: Use when removing unused files, exports, components, packages, or tests from a codebase — "delete dead code", "remove unused", "clean up leftovers" — or when a reviewer has produced a list of dead-code candidates that must be verified before deletion.
license: MIT
metadata:
  version: "1.1.0"
  part-of: quality-pass
---

# Quality Pass — Dead-code sweep

Deleting is the only irreversible step in a quality pass, so it gets the strictest rule: **two different searches, immediately before each deletion, both empty.**

## Before the first deletion

Read [gate comparison](../quality-pass/references/gate-configuration.md) and [saved finding history](../quality-pass/references/finding-records.md). Run `../quality-pass/scripts/gate.sh --baseline` before deletion if no JSON baseline exists for the reviewed scope. Resume with `../quality-pass/scripts/review.py status`; re-verify changed candidates. Standalone packages bundle these resources locally.

## Per candidate

1. **Pattern 1 — path.** Search for the module specifier and the basename without extension across the whole repo (all apps, packages, configs, docs that are executed such as storybook/e2e).
2. **Pattern 2 — symbol and string.** Search for every exported identifier, plus string references: dynamic `import()`, route tables, DI/service registration, reflection/attributes, config files, test-runner globs, CI workflows, Dockerfiles.
3. **Either search finds a live user → keep it**, and write it in the report under "NOT dead".
4. Delete the file/export **and its tests**. Remove a package only after its last importer is gone.
5. After the last deletion run the full gate (`../quality-pass/scripts/gate.sh`). Fix or revert new failures. If removing dead tests intentionally reduces counts, review and record that coverage change explicitly before deliberately replacing a baseline; never conceal a regression or treat unknown failure equivalence as pre-existing.
6. Report: files, line count removed, packages removed, and the "NOT dead" surprises with the reference that saved them. A rejected candidate is stated in the commit body **and** back to whoever produced the list (report, reviewer, tech lead), even when they said not to re-search; a wrong "certain" verdict is a finding about the review, not a private judgment call.

## Classic false positives (pattern 1 misses these, pattern 2 catches them)

Endpoint handler files paired with route registration · DI-registered services · classes found by reflection or attribute scan · files referenced by string in config, globs, or CI · storybook/e2e fixtures · code consumed by a different app in the monorepo · migrations.

## Order the sweep

Largest confirmed-dead file first, packages last. Commit as one `qp(dead-code)` commit with the removed line count in the message.

## Red flags

- "Pattern 1 was empty, pattern 2 is a formality" — pattern 2 can reveal callers that path searches miss; perform both and record their results.
- "The reviewer already searched" — reviewers searched earlier; things move. Search again now.
- "I'll leave the tests, they still pass" — tests of deleted code are dead code.
