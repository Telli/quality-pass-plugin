# quality-pass

An evidence-first quality pass for existing codebases, packaged as a Claude Code plugin **and** a set of portable [Agent Skills](https://agentskills.io) that work in OpenAI Codex and other hosts.

The method: **review with evidence → verify every claim yourself → fix in return-on-effort order, one green-gated commit per phase.** It has run on three production codebases (React + .NET, React + Node) and found multi-tenant data leaks, cut ~26% of first-paint JS, and removed 3,500–9,000 dead lines per pass without behavior changes.

## What's inside

| Skill | Invoke (Claude Code) | Invoke (Codex) | Does |
|---|---|---|---|
| `quality-pass` | `/quality-pass:quality-pass` | `$quality-pass` | Full pass: baseline → 6 reviews → verify → plan → approval → gated execution → hand-off |
| `quality-pass-review` | `/quality-pass:quality-pass-review` | `$quality-pass-review` | Phase 1 only. Ranked report with `file:line` evidence, no code changes |
| `quality-pass-execute` | `/quality-pass:quality-pass-execute` | `$quality-pass-execute` | Phase 2 from an approved report, one commit per phase |
| `quality-pass-dead-code` | `/quality-pass:quality-pass-dead-code` | `$quality-pass-dead-code` | Two-pattern verified deletion sweep |
| `quality-pass-gate` | `/quality-pass:quality-pass-gate` | `$quality-pass-gate` | Runs typecheck/lint/tests/build, reports verbatim |

Plus six **read-only reviewer agents** (Claude Code): `qp-slop-reviewer`, `qp-bug-hunter`, `qp-security-reviewer`, `qp-perf-reviewer`, `qp-dead-code-reviewer`, `qp-architecture-reviewer`. Their briefs are mirrored in `skills/quality-pass/references/reviewer-briefs.md` for runtimes without custom agents.

And `skills/quality-pass/scripts/gate.sh`: a toolchain-detecting gate runner (npm/pnpm/yarn/bun, dotnet, cargo, go, python) with `--baseline` and a `.quality-pass/gates` override for monorepos.

## Install

### Claude Code

```
/plugin marketplace add telli/quality-pass-plugin
/plugin install quality-pass@quality-pass-marketplace
```

Local checkout, without installing: `claude --plugin-dir /path/to/quality-pass-plugin`.

### Codex (and other Agent Skills hosts)

```bash
git clone https://github.com/telli/quality-pass-plugin
quality-pass-plugin/scripts/install-codex.sh            # symlinks into ~/.codex/skills
quality-pass-plugin/scripts/install-codex.sh --target ~/.agents/skills   # cross-runtime location
quality-pass-plugin/scripts/install-codex.sh --skill quality-pass-review --target ~/.agents/skills
```

The default installation links all five skills into the retained checkout. `--copy` installs self-contained copies; `--skill NAME` selects independently usable skills and implies `--copy`. Existing files and unrelated links are preserved, and refreshing a modified copied skill fails with a clear message. Python 3.9+ is required, with no third-party Python dependencies. On Windows use `scripts/install-codex.ps1` or `python scripts/install-codex.py`.

Generate individually distributable packages before listing skills on a marketplace:

```bash
python scripts/package-skills.py --output dist
```

Each deterministic ZIP includes its required references, complete background/checklists, portable scripts, license, and ownership manifest. The builder extracts each archive into its own temporary directory, verifies local links, and runs its standalone gate with no sibling skills. `dist/SHA256SUMS` records archive hashes.

## Targeted reviews and evidence

Request a base branch or PR diff, selected paths, or a feature boundary. **Quick** reviews bugs/security and their direct affected boundaries; **standard** covers all six dimensions within the selected feature and affected callers, tests, authorization boundaries, and contracts; **full** reviews the repository. Every report states what was scanned, excluded, and unrun. Standard is the default for a target; full is the default for a whole-codebase request.

```bash
python skills/quality-pass/scripts/review.py scope --base origin/main --mode standard
python skills/quality-pass/scripts/review.py scope --files 'src/auth/*' --feature 'tenant authorization' --mode quick
python skills/quality-pass/scripts/review.py status
```

The scope helper records seed files and commits; reviewers follow affected boundaries beyond the diff. Findings have stable IDs, per-claim verification, reproductions, validation commands, and observed results. Suspected defects are separate from demonstrated findings. Zero rejected claims is valid. Bug fixes include their regression tests in the same commit.

Local `.quality-pass/state.json` retains reviewed scope, approval already granted by the user, accepted/dismissed findings, completed fixes, and gate results. Watched primary/related files changing marks affected findings for re-verification and invalidates their approvals. See [finding records and resume commands](skills/quality-pass/references/finding-records.md).

## Reliable gates

```bash
skills/quality-pass/scripts/gate.sh --baseline
skills/quality-pass/scripts/gate.sh --project services/api/Api.csproj --timeout 300
```

Use `gate.ps1` or `python skills/quality-pass/scripts/gate.py` on Windows. Discovery handles nested projects and explicit .NET targets; native argv configurations are portable, while legacy shell commands require Bash. Missing required tools, optional skips, zero reported tests, failures, and timeouts have distinct statuses.

JSON baselines retain HEAD, source fingerprint, configuration, test counts, test identities, and failure details from current-run JUnit, TRX, Jest JSON, or Go reports. A red command changing from failure A to failure B is a regression. Unsupported, stale, or incomplete evidence reports **failure equivalence unknown**, including legacy text baselines. Failing gates keep a failure exit code even when identified as pre-existing. Baselines are preserved unless deliberately replaced. See [configuration examples and comparison rules](skills/quality-pass/references/gate-configuration.md).

Codex has no custom-agent files; the skill tells the model to spawn subagents or fresh sessions with the mirrored briefs, or to run the six dimensions sequentially in fresh contexts.

## Iron rules (short form)

1. Baseline first, gate every phase, paste output verbatim.
2. Verify and record every reviewer claim before acting; zero rejections is valid.
3. Two search patterns (path + symbol/string) immediately before every deletion.
4. Resume from saved progress, inspect the diff, and re-verify changed findings before reusing approval.
5. Mechanical means mechanical: no state moves for line counts; tests pass unchanged.
6. Every added/rewritten test is mutation-checked once.

## Layout

```
.claude-plugin/plugin.json, marketplace.json   Claude Code manifest + single-repo marketplace
skills/quality-pass/                           orchestrator skill
  references/review-dimensions.md              what each reviewer hunts for + output contract
  references/reviewer-briefs.md                generated mirror of agents/ for non-Claude hosts
  references/refactor-recipes.md               the only structural refactors allowed
  references/report-template.md
  scripts/gate.sh, gate.ps1, gate.py             portable gate runner with structured baselines
  scripts/review.py                              scope, finding records, approval/progress history
skills/quality-pass-{review,execute,dead-code,gate}/
agents/qp-*.md                                 Claude Code read-only reviewer agents (source of truth)
scripts/build-reviewer-briefs.sh               regenerate the mirror (CI runs --check)
scripts/install-codex.sh
scripts/install-codex.py, install-codex.ps1       safe single-skill/copy installation
scripts/package-skills.py                        deterministic standalone ZIPs + isolation validation
scripts/test.py, tests/                          behavioral regression suite (optional JUnit output)
```

Skill frontmatter uses only the portable fields (`name`, `description`, `license`, `metadata`) so the same folders load unchanged in any Agent Skills host. Each skill also carries `agents/openai.yaml` for Codex's skill picker; Claude Code ignores it.

## Contributing

Run `python scripts/test.py` for behavioral regression tests, `scripts/build-reviewer-briefs.sh --check` for the generated mirror, and `python scripts/package-skills.py` for standalone archives. This repository's `.quality-pass/gates.json` runs the regression tests with JUnit evidence and package validation; `skills/quality-pass/scripts/gate.sh` runs both.

Edit an agent → run `scripts/build-reviewer-briefs.sh`. Validate with `claude plugin validate --strict .claude-plugin/plugin.json`, `claude plugin validate --strict skills`, and `claude plugin validate --strict agents`. CI runs behavioral tests on Linux and Windows, including gate evidence, discovery, timeouts, saved progress, and isolated archives. Keep new guidance in the form that matches the failure: rules for discipline failures, recipes for shape failures.

MIT.
