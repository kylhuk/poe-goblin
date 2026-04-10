#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [ ! -f "vitest.config.ts" ]; then
  echo "VITEST_INFRA_FAIL: missing vitest.config.ts"
  exit 2
fi

if [ -f "frontend/vitest-ensure-tmp.cjs" ]; then
  export NODE_OPTIONS="${NODE_OPTIONS:+$NODE_OPTIONS }--require ./frontend/vitest-ensure-tmp.cjs"
fi

exec npx vitest "$@"
