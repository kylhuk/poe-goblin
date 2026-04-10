#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [ -x ".venv/bin/pytest" ]; then
  exec .venv/bin/pytest "$@"
fi

exec python3 -m pytest "$@"
