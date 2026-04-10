#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

REQ_FILE=".machine/runtime/AtomicRequirements.json"
MATRIX_FILE=".machine/runtime/TestMatrix.json"

[ -f "$REQ_FILE" ] || { echo "TEST_MATRIX_GUARD_FAIL: missing $REQ_FILE"; exit 1; }
[ -f "$MATRIX_FILE" ] || { echo "TEST_MATRIX_GUARD_FAIL: missing $MATRIX_FILE"; exit 1; }

python3 - <<'PY'
import json
import pathlib

req_path = pathlib.Path('.machine/runtime/AtomicRequirements.json')
matrix_path = pathlib.Path('.machine/runtime/TestMatrix.json')
req_doc = json.loads(req_path.read_text())
matrix_doc = json.loads(matrix_path.read_text())
errors = []

requirements = req_doc.get('requirements')
rows = matrix_doc.get('rows')

if not isinstance(requirements, list) or not requirements:
    errors.append('AtomicRequirements.json must contain a non-empty requirements array')
if not isinstance(rows, list) or not rows:
    errors.append('TestMatrix.json must contain a non-empty rows array')

allowed_cmd_prefixes = (
    'bash .machine/runtime/bin/pytest_cmd.sh ',
    'bash .machine/runtime/bin/vitest_cmd.sh ',
    'bash .machine/runtime/repros/',
    'python .machine/runtime/repros/',
    'python3 .machine/runtime/repros/',
)

allowed_kinds = {'functional','lifecycle','contract','migration','ui','integration'}
allowed_layers = {'unit','integration','api','ui','migration','repro'}
allowed_states = {'start','running','complete','published','recovery','failure','history'}

def has_targeted_selector(cmd: str) -> bool:
    if cmd.startswith('bash .machine/runtime/bin/pytest_cmd.sh '):
        return (' -k ' in cmd) or ('::' in cmd)
    if cmd.startswith('bash .machine/runtime/bin/vitest_cmd.sh '):
        return (' -t ' in cmd) or (' --testNamePattern ' in cmd) or (' --test-name-pattern ' in cmd)
    return True

req_ids = set()
behavior_ids = set()
behavior_to_req = {}
coverage = {}
state_coverage = {}

if isinstance(requirements, list):
    for idx, req in enumerate(requirements):
        if not isinstance(req, dict):
            errors.append(f'requirements[{idx}] must be an object')
            continue
        rid = str(req.get('id') or '').strip()
        title = str(req.get('title') or '').strip()
        kind = str(req.get('kind') or '').strip()
        behaviors = req.get('behaviors')
        states = req.get('states') or []

        if not rid:
            errors.append(f'requirements[{idx}] missing id')
        if not title:
            errors.append(f'requirements[{idx}] missing title')
        if kind not in allowed_kinds:
            errors.append(f'requirements[{idx}] invalid kind: {kind}')
        if rid:
            if rid in req_ids:
                errors.append(f'duplicate requirement id: {rid}')
            req_ids.add(rid)

        if not isinstance(behaviors, list) or not behaviors:
            errors.append(f'requirements[{idx}] must contain a non-empty behaviors array')
            continue

        lifecycle_states = []
        if kind == 'lifecycle':
            if not isinstance(states, list) or not states:
                errors.append(f'requirements[{idx}] kind=lifecycle requires a non-empty states array')
            else:
                for s in states:
                    if not isinstance(s, str) or s not in allowed_states:
                        errors.append(f'requirements[{idx}] invalid lifecycle state: {s}')
                    else:
                        lifecycle_states.append(s)
                state_coverage[rid] = {s: 0 for s in lifecycle_states}

        for bidx, behavior in enumerate(behaviors):
            if not isinstance(behavior, dict):
                errors.append(f'requirements[{idx}].behaviors[{bidx}] must be an object')
                continue
            bid = str(behavior.get('id') or '').strip()
            btitle = str(behavior.get('title') or '').strip()
            bstate = behavior.get('state')
            if not bid:
                errors.append(f'requirements[{idx}].behaviors[{bidx}] missing id')
                continue
            if bid in behavior_ids:
                errors.append(f'duplicate behavior id: {bid}')
            behavior_ids.add(bid)
            behavior_to_req[bid] = rid
            coverage[bid] = 0
            if not btitle:
                errors.append(f'requirements[{idx}].behaviors[{bidx}] missing title')
            if kind == 'lifecycle':
                if not isinstance(bstate, str) or bstate not in lifecycle_states:
                    errors.append(f'requirements[{idx}].behaviors[{bidx}] must declare state from requirement.states')
                else:
                    state_coverage[rid][bstate] += 0

seen_row_ids = set()
if isinstance(rows, list):
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f'rows[{idx}] must be an object')
            continue
        row_id = str(row.get('id') or '').strip()
        req_id = str(row.get('requirement_id') or '').strip()
        behavior_id = str(row.get('behavior_id') or '').strip()
        title = str(row.get('title') or '').strip()
        layer = str(row.get('layer') or '').strip()
        red_cmd = str(row.get('red_cmd') or '').strip()
        green_cmd = str(row.get('green_cmd') or '').strip()
        test_paths = row.get('test_paths')

        if not row_id:
            errors.append(f'rows[{idx}] missing id')
        elif row_id in seen_row_ids:
            errors.append(f'duplicate row id: {row_id}')
        else:
            seen_row_ids.add(row_id)

        if req_id not in req_ids:
            errors.append(f'rows[{idx}] references unknown requirement_id: {req_id}')
        if behavior_id not in behavior_ids:
            errors.append(f'rows[{idx}] references unknown behavior_id: {behavior_id}')
        elif behavior_to_req.get(behavior_id) != req_id:
            errors.append(f'rows[{idx}] behavior_id {behavior_id} does not belong to requirement_id {req_id}')
        else:
            coverage[behavior_id] += 1

        if not title:
            errors.append(f'rows[{idx}] missing title')
        if layer not in allowed_layers:
            errors.append(f'rows[{idx}] invalid layer: {layer}')

        for field, cmd in [('red_cmd', red_cmd), ('green_cmd', green_cmd)]:
            if not cmd:
                errors.append(f'rows[{idx}] missing {field}')
            elif not cmd.startswith(allowed_cmd_prefixes):
                errors.append(f'rows[{idx}] {field} must use machine-owned wrappers or repro scripts: {cmd}')
            elif not has_targeted_selector(cmd):
                errors.append(f'rows[{idx}] {field} must target a specific test or repro, not a whole file/suite: {cmd}')

        if not isinstance(test_paths, list) or not test_paths:
            errors.append(f'rows[{idx}] test_paths must be a non-empty array')
        else:
            for p in test_paths:
                if not isinstance(p, str) or not p.strip():
                    errors.append(f'rows[{idx}] test_paths contains an invalid entry')

for bid, count in coverage.items():
    if count < 1:
        errors.append(f'behavior {bid} has no test-matrix row')

# lifecycle state coverage: at least one behavior per declared state and at least one row per state
if isinstance(requirements, list):
    req_by_id = {str(r.get('id')): r for r in requirements if isinstance(r, dict) and r.get('id')}
    for rid, req in req_by_id.items():
        if str(req.get('kind')) != 'lifecycle':
            continue
        states = req.get('states') or []
        state_to_behaviors = {s: [] for s in states if isinstance(s, str)}
        for behavior in req.get('behaviors') or []:
            if isinstance(behavior, dict):
                s = behavior.get('state')
                bid = behavior.get('id')
                if isinstance(s, str) and isinstance(bid, str) and s in state_to_behaviors:
                    state_to_behaviors[s].append(bid)
        for s, bids in state_to_behaviors.items():
            if not bids:
                errors.append(f'lifecycle requirement {rid} has no behavior for state {s}')
            elif all(coverage.get(bid, 0) < 1 for bid in bids):
                errors.append(f'lifecycle requirement {rid} state {s} has no test-matrix coverage')

if errors:
    for item in errors:
        print(f'TEST_MATRIX_GUARD_FAIL: {item}')
    raise SystemExit(1)

print('TEST_MATRIX_GUARD_OK')
PY
