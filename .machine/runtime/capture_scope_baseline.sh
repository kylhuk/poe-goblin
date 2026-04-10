#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

python3 - <<'PY'
import json, pathlib, subprocess

runtime = pathlib.Path('.machine/runtime')
runtime.mkdir(parents=True, exist_ok=True)
files = []
for line in subprocess.check_output(
    ['git', 'status', '--porcelain=v1', '--untracked-files=all'], text=True
).splitlines():
    path = line[3:]
    if not path:
        continue
    if ' -> ' in path:
        path = path.split(' -> ', 1)[1]
    files.append(path)
path = runtime / 'BatchBaseline.json'
path.write_text(json.dumps({'dirty_files': sorted(set(files))}, indent=2) + '\n')
print(path)
PY
