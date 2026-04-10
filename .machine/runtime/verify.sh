#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

VERIFY_PHASE="${VERIFY_PHASE:-quality}"
failures=0

run_check() {
  local title="$1"
  local cmd="$2"
  echo
  echo "==> $title"
  echo "$cmd"
  if bash -lc "$cmd"; then
    echo "PASS: $title"
  else
    echo "FAIL: $title"
    failures=$((failures + 1))
  fi
}

bash .machine/runtime/test_matrix_guard.sh
bash .machine/runtime/verify_plan_guard.sh

python3 - <<'PYROWS' > /tmp/verify-test-rows.$$
import json, pathlib
rows = json.loads(pathlib.Path('.machine/runtime/TestMatrix.json').read_text()).get('rows') or []
for row in rows:
    print(json.dumps(row))
PYROWS

count=0
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
print(row['green_cmd'])
PY
)"
  run_check "matrix $row_id - $title" "$cmd"
  count=$((count + 1))
done < /tmp/verify-test-rows.$$
rm -f /tmp/verify-test-rows.$$

if [ "$count" -eq 0 ]; then
  echo "Verification failed: no TestMatrix rows were executed."
  exit 2
fi

if [ -f ".machine/runtime/FailureMatrix.json" ]; then
  if python3 - <<'PY'
import json, pathlib
p = pathlib.Path('.machine/runtime/FailureMatrix.json')
if p.exists():
    doc = json.loads(p.read_text())
    raise SystemExit(0 if (doc.get('failures') or []) else 1)
raise SystemExit(1)
PY
  then
    bash .machine/runtime/failure_matrix_guard.sh
    python3 - <<'PYROWS' > /tmp/verify-failure-rows.$$
import json, pathlib
rows = json.loads(pathlib.Path('.machine/runtime/FailureMatrix.json').read_text()).get('failures') or []
for row in rows:
    print(json.dumps(row))
PYROWS
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
print(row['green_cmd'])
PY
)"
      run_check "failure-matrix $row_id - $title" "$cmd"
    done < /tmp/verify-failure-rows.$$
    rm -f /tmp/verify-failure-rows.$$
  fi
fi

if [ "$VERIFY_PHASE" = "acceptance" ] && [ -f ".machine/runtime/VerificationPlan.json" ]; then
  mapfile -t ACCEPT_CMDS < <(python3 - <<'PY'
import json, pathlib
plan = json.loads(pathlib.Path('.machine/runtime/VerificationPlan.json').read_text())
for cmd in plan.get('acceptance_gate_commands') or []:
    if isinstance(cmd, str) and cmd.strip():
        print(cmd.strip())
PY
)
  for i in "${!ACCEPT_CMDS[@]}"; do
    run_check "acceptance planned $((i + 1))" "${ACCEPT_CMDS[$i]}"
  done
fi

if [ "$failures" -gt 0 ]; then
  echo
  echo "Verification failed: $failures check(s) failed."
  exit 1
fi

echo
echo "Verification passed."
