#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

bash .machine/runtime/failure_matrix_guard.sh

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

python3 - <<'PYROWS' > /tmp/failure-matrix-rows.$$
import json, pathlib
rows = json.loads(pathlib.Path('.machine/runtime/FailureMatrix.json').read_text()).get('failures') or []
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
  echo "==> finding red gate row: $row_id"
  echo "$title"
  echo "$cmd"

  tmp="$(mktemp)"
  set +e
  bash -lc "$cmd" >"$tmp" 2>&1
  rc=$?
  set -e
  cat "$tmp"

  if infra_fail "$rc" "$tmp"; then
    echo "FINDING RED GATE INFRA FAIL: command failed because the runner/tooling is not ready."
    rm -f "$tmp" /tmp/failure-matrix-rows.$$
    exit 2
  fi

  if [[ "$cmd" == *pytest_cmd.sh* ]]; then
    if pytest_no_tests "$rc" "$tmp"; then
      echo "FINDING RED GATE FAIL: pytest command did not select a real test case."
      rm -f "$tmp" /tmp/failure-matrix-rows.$$
      exit 1
    fi
    if ! pytest_ran_tests "$tmp"; then
      echo "FINDING RED GATE FAIL: pytest output did not prove that real tests executed."
      rm -f "$tmp" /tmp/failure-matrix-rows.$$
      exit 1
    fi
  fi

  if [[ "$cmd" == *vitest_cmd.sh* ]]; then
    if vitest_no_tests "$tmp"; then
      echo "FINDING RED GATE FAIL: vitest did not find any real tests."
      rm -f "$tmp" /tmp/failure-matrix-rows.$$
      exit 1
    fi
    if ! vitest_ran_tests "$tmp"; then
      echo "FINDING RED GATE FAIL: vitest output did not prove that real tests executed."
      rm -f "$tmp" /tmp/failure-matrix-rows.$$
      exit 1
    fi
  fi

  if [ "$rc" -eq 0 ]; then
    echo "FINDING RED GATE FAIL: row $row_id unexpectedly passed before repair implementation."
    rm -f "$tmp" /tmp/failure-matrix-rows.$$
    exit 1
  fi

  echo "EXPECTED FAILURE"
  rm -f "$tmp"
  ran=$((ran + 1))
done < /tmp/failure-matrix-rows.$$
rm -f /tmp/failure-matrix-rows.$$

if [ "$ran" -eq 0 ]; then
  echo "No failure-matrix rows were executed."
  exit 2
fi

echo
echo "Finding red gate passed: every current review/acceptance finding has a real failing test or repro before repair implementation."
