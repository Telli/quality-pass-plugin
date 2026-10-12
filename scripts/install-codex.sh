#!/usr/bin/env bash
# Linked checkout installation, or standalone copies with --copy / --skill NAME.
set -euo pipefail
if command -v python3 >/dev/null 2>&1; then runner=python3
elif command -v python >/dev/null 2>&1; then runner=python
else echo 'install-codex.sh: Python 3.9+ is required' >&2; exit 2; fi
exec "$runner" "$(cd "$(dirname "$0")" && pwd)/install-codex.py" "$@"
