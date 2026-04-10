#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

RUNTIME=".machine/runtime"
OUT="$RUNTIME/ResumeMode.json"
mkdir -p "$RUNTIME"

mapfile -t DIRTY < <(python3 - <<'PY'
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
    if path.startswith('.machine/runtime/'):
        continue
    print(path)
PY
)

mode="fresh"
reason="new task worktree; no existing task-owned candidate state detected"

has_candidate=0
if [ "${#DIRTY[@]}" -gt 0 ]; then
  has_candidate=1
fi

has_matrix=0
if [ -f "$RUNTIME/TestMatrix.json" ] && [ -f "$RUNTIME/VerificationPlan.json" ] && [ -f "$RUNTIME/AtomicRequirements.json" ]; then
  has_matrix=1
fi

if [ "$has_candidate" -eq 1 ]; then
  if [ "$has_matrix" -eq 1 ] && bash .machine/runtime/test_matrix_guard.sh >/dev/null 2>&1 && bash .machine/runtime/verify_plan_guard.sh >/dev/null 2>&1; then
    mode="resume"
    reason="existing task-owned candidate state detected; matrix and verification plan are valid, so resume from executable proof"
  else
    mode="resume_replan"
    reason="existing task-owned candidate state detected but matrix/verification metadata is missing or invalid; replan against current candidate state before resuming"
  fi
fi

python3 - <<'PY' "$OUT" "$mode" "$reason"
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
out.write_text(json.dumps({
    'mode': sys.argv[2],
    'reason': sys.argv[3],
}, indent=2) + '\n')
print(out)
PY

echo "RESUME_GATE_MODE=$mode"
echo "$reason"
