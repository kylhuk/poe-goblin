#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

python3 - <<'PY'
import json, pathlib

plan = json.loads(pathlib.Path('.machine/runtime/VerificationPlan.json').read_text())
caps = json.loads(pathlib.Path('.machine/runtime/Capabilities.json').read_text()) if pathlib.Path('.machine/runtime/Capabilities.json').exists() else {}
cmds = [cmd.strip() for cmd in plan.get('acceptance_gate_commands') or [] if isinstance(cmd, str) and cmd.strip()]
uses_docker = any(cmd.startswith(('docker ', 'docker-compose ')) for cmd in cmds)
if not uses_docker:
    print('PRECHECK_OK')
    raise SystemExit(0)
if not caps.get('docker_info'):
    print('PRECHECK_FAIL: acceptance requires Docker but docker access is unavailable in this environment')
    raise SystemExit(1)
if not (caps.get('docker_compose_v2') or caps.get('docker_compose_v1')):
    print('PRECHECK_FAIL: acceptance requires docker compose but compose is unavailable in this environment')
    raise SystemExit(1)
print('PRECHECK_OK')
PY
