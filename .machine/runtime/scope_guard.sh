#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

PLAN_FILE=".machine/runtime/VerificationPlan.json"
BASELINE_FILE=".machine/runtime/BatchBaseline.json"

[ -f "$PLAN_FILE" ] || { echo "SCOPE_GUARD_FAIL: missing $PLAN_FILE"; exit 1; }

mapfile -t BASELINE_DIRTY < <(python3 - <<'PY'
import json, pathlib
path = pathlib.Path('.machine/runtime/BatchBaseline.json')
if path.exists():
    try:
        data = json.loads(path.read_text())
    except Exception:
        data = {}
    for item in data.get('dirty_files') or []:
        if isinstance(item, str) and item.strip():
            print(item.strip())
PY
)
mapfile -t ALLOWED_PATHS < <(python3 - <<'PY'
import json, pathlib
plan = json.loads(pathlib.Path('.machine/runtime/VerificationPlan.json').read_text())
for item in plan.get('allowed_paths') or []:
    if isinstance(item, str) and item.strip():
        print(item.strip())
PY
)

declare -A BASELINE=()
for f in "${BASELINE_DIRTY[@]}"; do
  BASELINE["$f"]=1
done

allow_file() {
  local f="$1"
  case "$f" in
    .machine/runtime/*) return 0 ;;
  esac
  for a in "${ALLOWED_PATHS[@]}"; do
    [ -n "$a" ] || continue
    if [ "$f" = "$a" ]; then
      return 0
    fi
    case "$a" in
      */)
        case "$f" in
          "$a"*) return 0 ;;
        esac
        ;;
      *)
        if [ -d "$a" ]; then
          case "$f" in
            "$a"/*) return 0 ;;
          esac
        fi
        ;;
    esac
  done
  return 1
}

mapfile -t CHANGED < <(git status --porcelain=v1 --untracked-files=all | awk '{print substr($0,4)}' | sed 's#.* -> ##')
violations=0
for f in "${CHANGED[@]}"; do
  [ -n "$f" ] || continue
  if [ -n "${BASELINE[$f]:-}" ]; then
    continue
  fi
  if ! allow_file "$f"; then
    echo "SCOPE_GUARD_FAIL: changed file outside allowed_paths: $f"
    violations=1
  fi
done

if [ "$violations" -ne 0 ]; then
  exit 1
fi

echo "SCOPE_GUARD_OK"
