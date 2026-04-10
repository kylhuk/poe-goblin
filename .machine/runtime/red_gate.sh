#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

STATE_FILE=".machine/runtime/RunState.json"
[ -f "$STATE_FILE" ] || { echo "Missing $STATE_FILE"; exit 2; }

bash .machine/runtime/test_matrix_guard.sh
bash .machine/runtime/verify_plan_guard.sh

allow_red_file() {
  local f="$1"
  case "$f" in
    .machine/runtime/*) return 0 ;;
    tests/*|test/*|spec/*|__tests__/*) return 0 ;;
    *.test.*|*.spec.*|*_test.py|test_*.py) return 0 ;;
    *) return 1 ;;
  esac
}

mapfile -t BASELINE_DIRTY < <(python3 - <<'PYJSON'
import json, pathlib
state = json.loads(pathlib.Path('.machine/runtime/RunState.json').read_text())
for item in state.get('baseline_dirty_files') or []:
    if isinstance(item, str) and item.strip():
        print(item.strip())
PYJSON
)

declare -A BASELINE=()
for f in "${BASELINE_DIRTY[@]}"; do
  BASELINE["$f"]=1
done

mapfile -t CHANGED < <(python3 - <<'PYCHANGED'
import subprocess
for line in subprocess.check_output(
    ['git', 'status', '--porcelain=v1', '--untracked-files=all'],
    text=True,
).splitlines():
    path = line[3:]
    if not path:
        continue
    if ' -> ' in path:
        path = path.split(' -> ', 1)[1]
    print(path)
PYCHANGED
)

echo "==> changed files since HEAD"
if [ "${#CHANGED[@]}" -gt 0 ]; then
  printf '%s\n' "${CHANGED[@]}"
else
  echo "(none)"
fi

bad=0
for f in "${CHANGED[@]}"; do
  [ -n "$f" ] || continue
  if [ -n "${BASELINE[$f]:-}" ]; then
    continue
  fi
  if ! allow_red_file "$f"; then
    echo "RED GATE FAIL: non-test file modified before implementation: $f"
    bad=1
  fi
done
if [ "$bad" -ne 0 ]; then
  exit 1
fi

infra_fail() {
  local rc="$1"
  local file="$2"
  if [ "$rc" -eq 126 ] || [ "$rc" -eq 127 ]; then
    return 0
  fi
  grep -Eiq 'No such file or directory|command not found|MODULE_NOT_FOUND|Cannot find module|VITEST_INFRA_FAIL|Error: Cannot find module' "$file"
}

pytest_no_tests() {
  local rc="$1"
  local file="$2"
  [ "$rc" -eq 5 ] || grep -Eiq 'collected 0 items|0 selected|no tests ran|no tests were collected' "$file"
}

pytest_ran_tests() {
  local file="$1"
  grep -Eq 'collected [1-9][0-9]* items|[1-9][0-9]* passed|[1-9][0-9]* failed|=[[:space:]]+[1-9][0-9]* (passed|failed)' "$file"
}

vitest_no_tests() {
  local file="$1"
  grep -Eiq 'No test files found|No tests found|No test found in suite' "$file"
}

vitest_ran_tests() {
  local file="$1"
  grep -Eq '\([1-9][0-9]* tests?\b' "$file" || \
  grep -Eq 'Tests?[[:space:]]+[1-9][0-9]*[[:space:]]+(passed|failed|skipped|todo)' "$file"
}

python3 - <<'PYROWS' > /tmp/test-matrix-rows.$$
import json, pathlib
rows = json.loads(pathlib.Path('.machine/runtime/TestMatrix.json').read_text()).get('rows') or []
for row in rows:
    print(json.dumps(row))
PYROWS

ran=0
while IFS= read -r row_json; do
  [ -n "$row_json" ] || continue
  row_id="$(python3 - <<'PY' "$row_json"
import json, sys
row=json.loads(sys.argv[1])
print(row['id'])
PY
)"
  title="$(python3 - <<'PY' "$row_json"
import json, sys
row=json.loads(sys.argv[1])
print(row['title'])
PY
)"
  cmd="$(python3 - <<'PY' "$row_json"
import json, sys
row=json.loads(sys.argv[1])
print(row['red_cmd'])
PY
)"

  echo
  echo "==> red gate row: $row_id"
  echo "$title"
  echo "$cmd"

  tmp="$(mktemp)"
  set +e
  bash -lc "$cmd" >"$tmp" 2>&1
  rc=$?
  set -e
  cat "$tmp"

  if infra_fail "$rc" "$tmp"; then
    echo "RED GATE INFRA FAIL: command failed because the runner/tooling is not ready."
    rm -f "$tmp" /tmp/test-matrix-rows.$$
    exit 2
  fi

  if [[ "$cmd" == *pytest_cmd.sh* ]]; then
    if pytest_no_tests "$rc" "$tmp"; then
      echo "RED GATE FAIL: pytest command did not select a real test case."
      rm -f "$tmp" /tmp/test-matrix-rows.$$
      exit 1
    fi
    if ! pytest_ran_tests "$tmp"; then
      echo "RED GATE FAIL: pytest output did not prove that real tests executed."
      rm -f "$tmp" /tmp/test-matrix-rows.$$
      exit 1
    fi
  fi

  if [[ "$cmd" == *vitest_cmd.sh* ]]; then
    if vitest_no_tests "$tmp"; then
      echo "RED GATE FAIL: vitest did not find any real tests."
      rm -f "$tmp" /tmp/test-matrix-rows.$$
      exit 1
    fi
    if ! vitest_ran_tests "$tmp"; then
      echo "RED GATE FAIL: vitest output did not prove that real tests executed."
      rm -f "$tmp" /tmp/test-matrix-rows.$$
      exit 1
    fi
  fi

  if [ "$rc" -eq 0 ]; then
    echo "RED GATE FAIL: row $row_id unexpectedly passed before implementation."
    rm -f "$tmp" /tmp/test-matrix-rows.$$
    exit 1
  fi

  echo "EXPECTED FAILURE"
  rm -f "$tmp"
  ran=$((ran + 1))
done < /tmp/test-matrix-rows.$$
rm -f /tmp/test-matrix-rows.$$

if [ "$ran" -eq 0 ]; then
  echo "No test-matrix rows were executed."
  exit 2
fi

echo
echo "Red gate passed: every atomic requirement has a real failing test or repro before implementation."
