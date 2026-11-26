#!/usr/bin/env bash
# User-wide install for Claude Code, Codex, Gemini CLI and Antigravity CLI. See install.py --help.
set -euo pipefail
if command -v python3 >/dev/null 2>&1; then runner=python3
elif command -v python >/dev/null 2>&1; then runner=python
else echo 'install.sh: Python 3.9+ is required' >&2; exit 2; fi
exec "$runner" "$(cd "$(dirname "$0")" && pwd)/install.py" "$@"
