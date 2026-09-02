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
```

Codex has no custom-agent files; the skill tells the model to spawn subagents or fresh sessions with the mirrored briefs, or to run the six dimensions sequentially in fresh contexts.

## Iron rules (short form)

1. Baseline first, gate every phase, paste output verbatim.
2. Verify every reviewer claim before acting. Expect at least one to be wrong.
3. Two search patterns (path + symbol/string) immediately before every deletion.
4. Interrupted work is suspect: diff against HEAD before continuing.
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
  scripts/gate.sh
skills/quality-pass-{review,execute,dead-code,gate}/
agents/qp-*.md                                 Claude Code read-only reviewer agents (source of truth)
scripts/build-reviewer-briefs.sh               regenerate the mirror (CI runs --check)
scripts/install-codex.sh
```

Skill frontmatter uses only the portable fields (`name`, `description`, `license`, `metadata`) so the same folders load unchanged in any Agent Skills host. Each skill also carries `agents/openai.yaml` for Codex's skill picker; Claude Code ignores it.

## Contributing

Edit an agent → run `scripts/build-reviewer-briefs.sh`. Validate with `claude plugin validate --strict .`. Keep new guidance in the form that matches the failure: rules for discipline failures, recipes for shape failures.

MIT.
