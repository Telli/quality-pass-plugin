#!/usr/bin/env bash
# Install the quality-pass skills for OpenAI Codex (or any Agent Skills host) by symlinking each skill
# directory into the target skills directory. Symlinks mean `git pull` in this repo updates the install.
#
# Usage: scripts/install-codex.sh [--copy] [--target DIR]
#   default target: $CODEX_HOME/skills, else ~/.codex/skills
#   --copy         copy instead of symlink (for machines that will not keep this checkout)
#   --target DIR   e.g. ~/.agents/skills (cross-runtime), or a repo's .codex/skills
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${CODEX_HOME:-$HOME/.codex}/skills"; COPY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --copy) COPY=1 ;;
    --target) shift; TARGET="$1" ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac; shift
done
mkdir -p "$TARGET"
for d in "$ROOT"/skills/*/; do
  name="$(basename "$d")"; dest="$TARGET/$name"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "skip $name: $dest exists and is not a symlink (remove it to reinstall)" >&2; continue
  fi
  rm -f "$dest"
  if [ $COPY -eq 1 ]; then cp -R "${d%/}" "$dest"; else ln -s "${d%/}" "$dest"; fi
  echo "installed $name -> $dest"
done
echo
echo "Done. In Codex, invoke with \$quality-pass (or the /skills picker). The sub-skills reference"
echo "../quality-pass/references and ../quality-pass/scripts, so keep all five installed together."
