#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = ".sisyphus/evidence/task-12-final-release-gate.json"


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object expected: {path}")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run final consolidated release gate.")
    _ = parser.add_argument(
        "--cutover-gate",
        default=".sisyphus/evidence/task-10-cutover-gate.json",
    )
    _ = parser.add_argument(
        "--rollback-ready",
        default=".sisyphus/evidence/task-9-rollback-ready.json",
    )
    _ = parser.add_argument(
        "--runbook-check",
        default=".sisyphus/evidence/task-11-runbook-check.txt",
    )
    _ = parser.add_argument(
        "--parity-log",
        default=".sisyphus/evidence/task-2-parity-order.log",
    )
    _ = parser.add_argument(
        "--service-regression-log",
        default=".sisyphus/evidence/task-8-cadence.log",
    )
    _ = parser.add_argument("--output", default=DEFAULT_OUTPUT)
    return parser


def _log_passed(log_text: str) -> bool:
    normalized = log_text.lower()
    if any(token in normalized for token in (" failed", "error", "traceback")):
        return False
    return re.search(r"\b\d+\s+passed\b", normalized) is not None


def _runbook_check_passed(runbook_text: str) -> bool:
    stripped = runbook_text.strip()
    if stripped == "OK":
        return True
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and str(payload.get("status") or "") == "OK"


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    cutover = _load_json(str(args.cutover_gate))
    rollback = _load_json(str(args.rollback_ready))
    runbook_text = Path(str(args.runbook_check)).read_text(encoding="utf-8").strip()
    parity_log = Path(str(args.parity_log)).read_text(encoding="utf-8")
    service_regression_log = Path(str(args.service_regression_log)).read_text(
        encoding="utf-8"
    )

    raw_cutover_checks = cutover.get("checks")
    cutover_checks: dict[str, Any] = (
        raw_cutover_checks if isinstance(raw_cutover_checks, dict) else {}
    )

    checks = {
        "cutover_gate_pass": bool(cutover.get("cutover_approved") is True),
        "parity_gate_pass": bool(cutover_checks.get("parity_ok") is True),
        "performance_gate_pass": bool(
            cutover_checks.get("duration_reduction_ok") is True
        )
        and bool(cutover_checks.get("read_bytes_reduction_ok") is True),
        "memory_gate_pass": bool(cutover_checks.get("memory_ok") is True),
        "rollback_ready": bool(rollback.get("overall_ready") is True),
        "runbook_check_pass": _runbook_check_passed(runbook_text),
        "parity_tests_pass": _log_passed(parity_log),
        "service_regression_pass": _log_passed(service_regression_log),
    }
    recommendation = "approve" if all(checks.values()) else "reject"

    payload = {
        "schema_version": "task-12-final-release-gate-v1",
        "checks": checks,
        "recommendation": recommendation,
        "inputs": {
            "cutover_gate": str(args.cutover_gate),
            "rollback_ready": str(args.rollback_ready),
            "runbook_check": str(args.runbook_check),
            "parity_log": str(args.parity_log),
            "service_regression_log": str(args.service_regression_log),
        },
    }

    output_path = Path(str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if recommendation != "approve":
        print("ERROR: final release gate rejected", file=sys.stderr)
        return 1
    print(f"final release gate approved: wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
