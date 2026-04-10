#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

PLAN_FILE=".machine/runtime/VerificationPlan.json"
[ -f "$PLAN_FILE" ] || { echo "PLAN_GUARD_FAIL: missing $PLAN_FILE"; exit 1; }

bash .machine/runtime/test_matrix_guard.sh

python3 - <<'PY'
import json
import pathlib
import subprocess

plan = json.loads(pathlib.Path('.machine/runtime/VerificationPlan.json').read_text())
errors = []

required_keys = ['acceptance_gate_commands', 'allowed_paths', 'non_goals']
for key in required_keys:
    if key not in plan:
        errors.append(f'missing key: {key}')
    elif not isinstance(plan[key], list):
        errors.append(f'{key} must be an array')

allowed_cmd_prefixes = (
    'bash .machine/runtime/bin/pytest_cmd.sh ',
    'bash .machine/runtime/bin/vitest_cmd.sh ',
    'bash .machine/runtime/repros/',
    'python .machine/runtime/repros/',
    'python3 .machine/runtime/repros/',
    'docker ',
    'docker compose ',
)

forbidden_substrings = [
    '.venv/bin/pytest',
    'python -m pytest',
    'pytest ',
    'npx vitest',
    'npm test',
    'pnpm test',
    'yarn test',
    '.machine/runtime/Task.md',
    '.machine/runtime/ProductSpec.md',
    '.machine/runtime/ExecutionPlan.md',
    '.machine/runtime/Runbook.md',
    '.machine/runtime/Documentation.md',
    '.machine/runtime/Evidence.md',
    'git status',
    'git diff',
    'git worktree',
    'scope-clean',
]

acceptance_cmds = [x.strip() for x in plan.get('acceptance_gate_commands', []) if isinstance(x, str) and x.strip()]
for cmd in acceptance_cmds:
    if any(bad in cmd for bad in forbidden_substrings):
        errors.append(f'acceptance_gate_commands contains forbidden command content: {cmd}')
    if not cmd.startswith(allowed_cmd_prefixes):
        errors.append(f'acceptance_gate_commands must use machine-owned wrappers, repro scripts, or docker/compose: {cmd}')

allowed_paths = [x.strip() for x in plan.get('allowed_paths', []) if isinstance(x, str) and x.strip()]
if not allowed_paths:
    errors.append('allowed_paths must not be empty')

current_dirty = []
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
    current_dirty.append(path)


def covered(path: str) -> bool:
    for a in allowed_paths:
        if path == a:
            return True
        if a.endswith('/') and path.startswith(a):
            return True
        if path.startswith(a.rstrip('/') + '/'):
            return True
    return False

for path in sorted(set(current_dirty)):
    if not covered(path):
        errors.append(f'allowed_paths excludes current task-owned dirty file: {path}')

if errors:
    for item in errors:
        print(f'PLAN_GUARD_FAIL: {item}')
    raise SystemExit(1)

print('PLAN_GUARD_OK')
PY
