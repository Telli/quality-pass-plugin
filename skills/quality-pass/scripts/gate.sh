#!/usr/bin/env bash
# gate.sh — run the quality-pass gate (typecheck, lint, tests, production build) and print verbatim results.
#
# Usage:
#   gate.sh [--baseline] [--print] [--dir PATH]
#
#   --baseline   also save the summary to .quality-pass/baseline.txt (run once before touching anything)
#   --print      only print the commands that would run
#   --dir PATH   repo root (default: current directory)
#
# Command source, in priority order:
#   1. .quality-pass/gates              one shell command per line, '#' comments allowed  (write this for monorepos)
#   2. auto-detection                   npm/pnpm/yarn/bun scripts, dotnet, cargo, go, python
#
# Exit code is 1 if any gate fails. Logs: .quality-pass/logs/<timestamp>/<n>.log
set -u

BASELINE=0; PRINT=0; ROOT="$(pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --baseline) BASELINE=1 ;;
    --print) PRINT=1 ;;
    --dir) shift; ROOT="$1" ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done
cd "$ROOT" || exit 2

CMDS=()

add() { CMDS+=("$1"); }

pkg_has_script() { # pkg_has_script <script> <package.json>
  node -e 'const p=require(require("path").resolve(process.argv[1]));process.exit(p.scripts&&p.scripts[process.argv[2]]?0:1)' "$2" "$1" 2>/dev/null
}

detect_node() {
  local dir="$1" pm="npm run" runner="npx"
  [ -f "$dir/pnpm-lock.yaml" ] && pm="pnpm run" && runner="pnpm exec"
  [ -f "$dir/yarn.lock" ] && pm="yarn" && runner="yarn"
  [ -f "$dir/bun.lockb" ] || [ -f "$dir/bun.lock" ] && pm="bun run" && runner="bunx"
  local prefix=""; [ "$dir" != "." ] && prefix="cd $dir && "
  local pj="$dir/package.json"
  if pkg_has_script typecheck "$pj"; then add "${prefix}${pm} typecheck"
  elif pkg_has_script type-check "$pj"; then add "${prefix}${pm} type-check"
  elif [ -f "$dir/tsconfig.json" ]; then add "${prefix}${runner} tsc --noEmit -p tsconfig.json"; fi
  pkg_has_script lint "$pj" && add "${prefix}${pm} lint"
  pkg_has_script test "$pj" && add "${prefix}CI=true ${pm} test"
  pkg_has_script build "$pj" && add "${prefix}${pm} build"
}

detect() {
  # Node: root, or common app dirs when the root has no package.json
  if [ -f package.json ]; then
    detect_node .
    # npm/yarn/pnpm workspaces: detect each member too (root often has no gate scripts of its own)
    for d in $(node -e 'const p=require(require("path").resolve("package.json"));const w=Array.isArray(p.workspaces)?p.workspaces:(p.workspaces&&p.workspaces.packages)||[];console.log(w.join("\n"))' 2>/dev/null); do
      for m in $d; do [ -f "$m/package.json" ] && detect_node "${m%/}"; done
    done
    if [ -f pnpm-workspace.yaml ]; then
      for d in $(sed -n "s/^[[:space:]]*-[[:space:]]*['\"]\{0,1\}\([^'\"]*\)['\"]\{0,1\}/\1/p" pnpm-workspace.yaml); do
        for m in $d; do [ -f "$m/package.json" ] && detect_node "${m%/}"; done
      done
    fi
  else
    for d in Frontend frontend web client app Console console admin packages/*; do
      [ -f "$d/package.json" ] && detect_node "$d"
    done
  fi
  # .NET
  if ls ./*.sln ./*.slnx >/dev/null 2>&1 || find . -maxdepth 3 -name '*.csproj' -not -path '*/node_modules/*' | grep -q .; then
    add "dotnet build --nologo"
    add "dotnet test --nologo --no-build"
  fi
  # Rust
  if [ -f Cargo.toml ]; then
    add "cargo build --all-targets"
    command -v cargo-clippy >/dev/null 2>&1 && add "cargo clippy --all-targets -- -D warnings"
    add "cargo test"
  fi
  # Go
  if [ -f go.mod ]; then add "go vet ./..."; add "go build ./..."; add "go test ./..."; fi
  # Python
  if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f requirements.txt ]; then
    command -v ruff >/dev/null 2>&1 && add "ruff check ."
    command -v mypy >/dev/null 2>&1 && [ -f mypy.ini ] && add "mypy ."
    command -v pytest >/dev/null 2>&1 && add "pytest -q"
  fi
}

if [ -f .quality-pass/gates ]; then
  while IFS= read -r line; do
    line="${line%%#*}"; line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ -n "$line" ] && add "$line"
  done < .quality-pass/gates
  SOURCE=".quality-pass/gates"
else
  detect; SOURCE="auto-detected (override with .quality-pass/gates)"
fi

if [ ${#CMDS[@]} -eq 0 ]; then
  echo "gate.sh: no gates found in $ROOT. Write .quality-pass/gates with one command per line." >&2
  exit 2
fi

echo "== quality-pass gate  root=$ROOT  source=$SOURCE"
i=0; for c in "${CMDS[@]}"; do i=$((i+1)); echo "  [$i] $c"; done
[ $PRINT -eq 1 ] && exit 0

STAMP="$(date +%Y%m%d-%H%M%S)"; LOGDIR=".quality-pass/logs/$STAMP"; mkdir -p "$LOGDIR"
SUMMARY=(); FAILED=0; i=0
for c in "${CMDS[@]}"; do
  i=$((i+1)); log="$LOGDIR/$i.log"
  echo; echo "== [$i/${#CMDS[@]}] $c"
  start=$(date +%s)
  if bash -o pipefail -c "$c" >"$log" 2>&1; then status=PASS; else status=FAIL; FAILED=1; fi
  dur=$(( $(date +%s) - start ))
  SUMMARY+=("$status  ${dur}s  $c")
  echo "   -> $status (${dur}s)  log: $log"
  if [ "$status" = FAIL ]; then
    echo "   ---- last 40 lines ----"; tail -n 40 "$log" | sed 's/^/   | /'; echo "   -----------------------"
  fi
done

echo; echo "== summary ($STAMP)"
printf '  %s\n' "${SUMMARY[@]}" | tee "$LOGDIR/summary.txt"
if [ $BASELINE -eq 1 ]; then
  cp "$LOGDIR/summary.txt" .quality-pass/baseline.txt
  echo "  baseline saved to .quality-pass/baseline.txt"
elif [ -f .quality-pass/baseline.txt ]; then
  echo; echo "== vs baseline"
  diff <(sed -E 's/  [0-9]+s  /  /' .quality-pass/baseline.txt) <(sed -E 's/  [0-9]+s  /  /' "$LOGDIR/summary.txt") \
    && echo "  no change in gate status vs baseline" || echo "  (lines with < are baseline, > are now)"
fi
# Keep .quality-pass out of the repo unless the team wants the logs.
[ -f .quality-pass/.gitignore ] || printf 'logs/\n' > .quality-pass/.gitignore
exit $FAILED
