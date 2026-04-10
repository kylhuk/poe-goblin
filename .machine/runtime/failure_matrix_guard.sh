#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

MATRIX_FILE=".machine/runtime/FailureMatrix.json"
[ -f "$MATRIX_FILE" ] || { echo "FAILURE_MATRIX_GUARD_FAIL: missing $MATRIX_FILE"; exit 1; }

python3 - <<'PY'
import json
import pathlib

matrix_doc = json.loads(pathlib.Path('.machine/runtime/FailureMatrix.json').read_text())
errors = []
failures = matrix_doc.get('failures')

allowed_cmd_prefixes = (
    'bash .machine/runtime/bin/pytest_cmd.sh ',
    'bash .machine/runtime/bin/vitest_cmd.sh ',
    'bash .machine/runtime/repros/',
    'python .machine/runtime/repros/',
    'python3 .machine/runtime/repros/',
)

def has_targeted_selector(cmd: str) -> bool:
    if cmd.startswith('bash .machine/runtime/bin/pytest_cmd.sh '):
        return (' -k ' in cmd) or ('::' in cmd)
    if cmd.startswith('bash .machine/runtime/bin/vitest_cmd.sh '):
        return (' -t ' in cmd) or (' --testNamePattern ' in cmd) or (' --test-name-pattern ' in cmd)
    return True

if not isinstance(failures, list) or not failures:
    errors.append('FailureMatrix.json must contain a non-empty failures array')

seen_ids = set()
if isinstance(failures, list):
    for idx, row in enumerate(failures):
        if not isinstance(row, dict):
            errors.append(f'failures[{idx}] must be an object')
            continue
        row_id = str(row.get('id') or '').strip()
        title = str(row.get('title') or '').strip()
        layer = str(row.get('layer') or '').strip()
        red_cmd = str(row.get('red_cmd') or '').strip()
        green_cmd = str(row.get('green_cmd') or '').strip()
        test_paths = row.get('test_paths')

        if not row_id:
            errors.append(f'failures[{idx}] missing id')
        elif row_id in seen_ids:
            errors.append(f'duplicate failure id: {row_id}')
        else:
            seen_ids.add(row_id)
        if not title:
            errors.append(f'failures[{idx}] missing title')
        if layer not in {'unit','integration','api','ui','migration','repro'}:
            errors.append(f'failures[{idx}] invalid layer: {layer}')
        for field, cmd in [('red_cmd', red_cmd), ('green_cmd', green_cmd)]:
            if not cmd:
                errors.append(f'failures[{idx}] missing {field}')
            elif not cmd.startswith(allowed_cmd_prefixes):
                errors.append(f'failures[{idx}] {field} must use machine-owned wrappers or repro scripts: {cmd}')
            elif not has_targeted_selector(cmd):
                errors.append(f'failures[{idx}] {field} must target a specific test or repro, not a whole file/suite: {cmd}')
        if not isinstance(test_paths, list) or not test_paths:
            errors.append(f'failures[{idx}] test_paths must be a non-empty array')
        else:
            for p in test_paths:
                if not isinstance(p, str) or not p.strip():
                    errors.append(f'failures[{idx}] test_paths contains an invalid entry')

if errors:
    for item in errors:
        print(f'FAILURE_MATRIX_GUARD_FAIL: {item}')
    raise SystemExit(1)

print('FAILURE_MATRIX_GUARD_OK')
PY
