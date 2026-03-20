#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = ".sisyphus/evidence/task-10-cutover-gate.json"
DEFAULT_BASELINE = ".sisyphus/evidence/task-1-baseline-shared-host.json"
DEFAULT_SHADOW = ".sisyphus/evidence/task-5-shadow-read-strict.json"
DEFAULT_FALLBACK = ".sisyphus/evidence/task-6-fallback-pass.json"
DEFAULT_SETTINGS = ".sisyphus/evidence/task-7-settings-active.txt"
DEFAULT_USER_CONFIG = "config/clickhouse/users/poe.xml"

EXPECTED_SETTINGS = {
    "max_memory_usage": "1610612736",
    "max_threads": "4",
    "max_execution_time": "180",
    "max_bytes_before_external_group_by": "268435456",
    "max_bytes_before_external_sort": "268435456",
}


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object expected: {path}")
    return payload


def _metric_mean(payload: dict[str, Any], metric: str) -> float:
    block = payload.get("metrics", {}).get(metric, {}).get("aggregate_3_runs", {})
    value = block.get("mean")
    if not isinstance(value, (int, float)):
        raise ValueError(f"missing mean metric: {metric}")
    return float(value)


def _metric_p95(payload: dict[str, Any], metric: str) -> float:
    values = (
        payload.get("metrics", {})
        .get(metric, {})
        .get("aggregate_3_runs", {})
        .get("values")
    )
    if not isinstance(values, list) or not values:
        raise ValueError(f"missing values metric for p95: {metric}")
    numeric = [float(item) for item in values if isinstance(item, (int, float))]
    if not numeric:
        raise ValueError(f"no numeric values for p95: {metric}")
    numeric.sort()
    rank = max(1, int(round(0.95 * len(numeric))))
    return float(numeric[min(len(numeric) - 1, rank - 1)])


def _load_settings_evidence(path: str) -> dict[str, str]:
    raw_text = Path(path).read_text(encoding="utf-8").strip()
    if not raw_text:
        return {}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return {str(key): str(value) for key, value in parsed.items()}
    settings_map: dict[str, str] = {}
    for raw_line in raw_text.splitlines():
        parts = raw_line.strip().split()
        if len(parts) >= 2:
            settings_map[parts[0]] = parts[-1]
    return settings_map


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate cutover gate for mod-rollup path."
    )
    _ = parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    _ = parser.add_argument(
        "--candidate",
        default="",
        help="Candidate metrics json path (required).",
    )
    _ = parser.add_argument("--shadow", default=DEFAULT_SHADOW)
    _ = parser.add_argument("--fallback", default=DEFAULT_FALLBACK)
    _ = parser.add_argument("--settings", default=DEFAULT_SETTINGS)
    _ = parser.add_argument("--user-config", default=DEFAULT_USER_CONFIG)
    _ = parser.add_argument("--output", default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not str(args.candidate).strip():
        print("ERROR: --candidate is required", file=sys.stderr)
        return 1

    baseline = _load_json(str(args.baseline))
    candidate = _load_json(str(args.candidate))
    shadow = _load_json(str(args.shadow))
    fallback = _load_json(str(args.fallback))
    settings_values = _load_settings_evidence(str(args.settings))
    user_config_text = Path(str(args.user_config)).read_text(encoding="utf-8")

    baseline_duration = _metric_mean(baseline, "query_duration_ms")
    baseline_read_bytes = _metric_mean(baseline, "read_bytes")
    candidate_duration = _metric_mean(candidate, "query_duration_ms")
    candidate_read_bytes = _metric_mean(candidate, "read_bytes")
    candidate_memory = _metric_mean(candidate, "memory_usage")
    candidate_memory_p95 = _metric_p95(candidate, "memory_usage")
    baseline_duration_p95 = _metric_p95(baseline, "query_duration_ms")
    candidate_duration_p95 = _metric_p95(candidate, "query_duration_ms")

    duration_reduction = (
        0.0
        if baseline_duration <= 0
        else (baseline_duration - candidate_duration) / baseline_duration
    )
    read_bytes_reduction = (
        0.0
        if baseline_read_bytes <= 0
        else (baseline_read_bytes - candidate_read_bytes) / baseline_read_bytes
    )

    duration_reduction_p95 = (
        0.0
        if baseline_duration_p95 <= 0
        else (baseline_duration_p95 - candidate_duration_p95) / baseline_duration_p95
    )

    shadow_mismatch_count = int(shadow.get("shadow", {}).get("mismatch_count", 0))
    shadow_mode = str(shadow.get("shadow", {}).get("comparison_mode", ""))
    fallback_ready = bool(fallback.get("status") == "ok")

    settings_checks = {
        key: settings_values.get(key) == value for key, value in EXPECTED_SETTINGS.items()
    }
    settings_checks.update(
        {
        "max_concurrent_queries": "<max_concurrent_queries>1</max_concurrent_queries>"
        in user_config_text,
        }
    )

    thresholds = {
        "parity_mismatch_count": 0,
        "max_memory_usage": 1610612736.0,
        "min_read_bytes_reduction": 0.30,
        "min_duration_reduction": 0.20,
    }

    checks = {
        "parity_ok": shadow_mismatch_count == thresholds["parity_mismatch_count"],
        "memory_ok": candidate_memory_p95 <= thresholds["max_memory_usage"],
        "read_bytes_reduction_ok": read_bytes_reduction
        >= thresholds["min_read_bytes_reduction"],
        "duration_reduction_ok": duration_reduction_p95
        >= thresholds["min_duration_reduction"],
        "shadow_mode_strict": shadow_mode == "strict",
        "fallback_ready": fallback_ready,
        "settings_ok": all(settings_checks.values()),
    }
    cutover_approved = all(checks.values())

    payload = {
        "schema_version": "task-10-cutover-gate-v1",
        "cutover_approved": cutover_approved,
        "thresholds": thresholds,
        "metrics": {
            "baseline_duration_mean": baseline_duration,
            "candidate_duration_mean": candidate_duration,
            "baseline_duration_p95": baseline_duration_p95,
            "candidate_duration_p95": candidate_duration_p95,
            "baseline_read_bytes_mean": baseline_read_bytes,
            "candidate_read_bytes_mean": candidate_read_bytes,
            "candidate_memory_mean": candidate_memory,
            "candidate_memory_p95": candidate_memory_p95,
            "duration_reduction": duration_reduction,
            "duration_reduction_p95": duration_reduction_p95,
            "read_bytes_reduction": read_bytes_reduction,
            "shadow_mismatch_count": shadow_mismatch_count,
            "shadow_comparison_mode": shadow_mode,
        },
        "checks": checks,
        "settings_checks": settings_checks,
    }

    output_path = Path(str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if not cutover_approved:
        print("ERROR: cutover gate failed", file=sys.stderr)
        return 1
    print(f"cutover gate approved: wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
