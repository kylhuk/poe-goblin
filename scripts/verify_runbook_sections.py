#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_ENTRIES = [
    "scripts/run_mod_feature_backfill.py",
    "scripts/monitor_mod_feature_backfill.py",
    "scripts/check_mod_feature_settings.py",
    "scripts/verify_mod_rollup_rollback.py",
    "scripts/evaluate_cutover_gate.py",
    "scripts/final_release_gate.py",
    ".sisyphus/evidence/task-7-settings-active.txt",
    ".sisyphus/evidence/task-10-cutover-gate.json",
]

OUTPUT_PATH = Path(".sisyphus/evidence/task-11-runbook-check.txt")


def main() -> int:
    doc_path = Path("docs/ops-runbook.md")
    if not doc_path.exists():
        print("ERROR: runbook missing", file=sys.stderr)
        return 1
    content = doc_path.read_text(encoding="utf-8")
    missing = [entry for entry in REQUIRED_ENTRIES if entry not in content]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if missing:
        OUTPUT_PATH.write_text(
            json.dumps({"status": "missing", "missing": missing}, indent=2),
            encoding="utf-8",
        )
        return 1

    OUTPUT_PATH.write_text(json.dumps({"status": "OK"}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
