#!/usr/bin/env bash
# Portable gate runner. Python 3.9+; no third-party Python dependencies.
set -euo pipefail
if command -v python3 >/dev/null 2>&1; then runner=python3
elif command -v python >/dev/null 2>&1; then runner=python
else echo 'gate.sh: Python 3.9+ is required' >&2; exit 2; fi
exec "$runner" "$(cd "$(dirname "$0")" && pwd)/gate.py" "$@"
