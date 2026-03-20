#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_OUTPUT = ".sisyphus/evidence/task-9-rollback-ready.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify staged rollback prerequisites for mod-rollup cutover."
    )
    _ = parser.add_argument("--output", default=DEFAULT_OUTPUT)
    _ = parser.add_argument(
        "--require-file",
        action="append",
        default=[],
        help="Extra prerequisite path that must exist (repeatable).",
    )
    return parser


def _exists(path: str) -> bool:
    return Path(path).exists()


def _command_ok(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    checks = {
        "schema_introduced": {
            "migration_0042_exists": _exists(
                "schema/migrations/0042_ml_item_mod_rollups_v1.sql"
            ),
            "legacy_path_script_exists": _exists(
                "scripts/benchmark_mod_token_query.py"
            ),
            "migration_runner_help": _command_ok(
                [".venv/bin/python", "-m", "poe_trade.db.migrations", "--help"]
            ),
        },
        "shadow_enabled": {
            "shadow_evidence_exists": _exists(
                ".sisyphus/evidence/task-5-shadow-read.json"
            ),
            "shadow_strict_evidence_exists": _exists(
                ".sisyphus/evidence/task-5-shadow-read-strict.json"
            ),
            "comparator_help": _command_ok(
                ["python3", "scripts/compare_mod_feature_paths.py", "--help"]
            ),
        },
        "post_cutover": {
            "fallback_evidence_exists": _exists(
                ".sisyphus/evidence/task-6-fallback-pass.json"
            ),
            "comparator_script_exists": _exists("scripts/compare_mod_feature_paths.py"),
            "cutover_gate_help": _command_ok(
                ["python3", "scripts/evaluate_cutover_gate.py", "--help"]
            ),
            "final_gate_help": _command_ok(
                ["python3", "scripts/final_release_gate.py", "--help"]
            ),
        },
    }

    extras = [str(item).strip() for item in args.require_file if str(item).strip()]
    extra_results = {path: _exists(path) for path in extras}
    checks["extra_requirements"] = extra_results

    stage_ready = {
        stage: all(bool(value) for value in stage_checks.values())
        for stage, stage_checks in checks.items()
    }
    overall_ready = all(stage_ready.values())

    payload = {
        "schema_version": "task-9-rollback-ready-v1",
        "overall_ready": overall_ready,
        "stage_ready": stage_ready,
        "checks": checks,
    }

    output_path = Path(str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if not overall_ready:
        print(
            "ERROR: rollback readiness failed; inspect stage_ready/checks",
            file=sys.stderr,
        )
        return 1
    print(f"rollback readiness verified: wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
