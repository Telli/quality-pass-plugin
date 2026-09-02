#!/usr/bin/env bash
# Regenerates skills/quality-pass/references/reviewer-briefs.md from agents/*.md so non-Claude runtimes
# (Codex, etc.) get the same reviewer prompts. Run after editing any agent. Verified in CI by --check.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/skills/quality-pass/references/reviewer-briefs.md"
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1

gen() {
  echo "# Reviewer briefs (generated from agents/ — edit there, then run scripts/build-reviewer-briefs.sh)"
  echo
  echo "Use these as the system prompt / task for one read-only subagent or fresh session per dimension when the Claude Code agents are not available. Give each reviewer the repo path and nothing else."
  echo
  for f in "$ROOT"/agents/qp-*.md; do
    name="$(sed -n 's/^name: *//p' "$f" | head -1)"
    echo "---"; echo; echo "## $name"; echo
    # body = everything after the closing frontmatter fence
    awk 'BEGIN{fm=0} /^---$/{fm++; next} fm>=2{print}' "$f"
    echo
  done
}

if [ $CHECK -eq 1 ]; then
  diff -u "$OUT" <(gen) >/dev/null && echo "reviewer-briefs.md up to date" || { echo "reviewer-briefs.md is stale; run scripts/build-reviewer-briefs.sh" >&2; exit 1; }
else
  gen > "$OUT"; echo "wrote $OUT"
fi
