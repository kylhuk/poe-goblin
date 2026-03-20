#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast


OUTPUT_SCHEMA_VERSION = "task-1-baseline-shared-host-v1"
DEFAULT_STATUS_FILE = ".sisyphus/state/poeninja_snapshot-last-run.json"
DEFAULT_OUTPUT_PATH = ".sisyphus/evidence/task-1-baseline-shared-host.json"
AGGREGATE_RUN_COUNT = 3

REQUIRED_QUERY_METRICS = (
    "query_duration_ms",
    "read_rows",
    "read_bytes",
    "memory_usage",
)

REQUIRED_OUTPUT_METRICS = (
    "query_duration_ms",
    "read_rows",
    "read_bytes",
    "memory_usage",
    "concurrent_heavy_query_count",
    "rebuild_cycle_time_seconds",
)


class EvidenceBuildError(Exception):
    pass


@dataclass(frozen=True)
class MetricRun:
    run_index: int
    query_id: str
    query_duration_ms: float
    read_rows: float
    read_bytes: float
    memory_usage: float


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble Task-1 baseline evidence from benchmark, query-log, and "
            "poeninja_snapshot status artifacts."
        )
    )
    _ = parser.add_argument(
        "--benchmark-json",
        required=True,
        help="Path to benchmark_mod_token_query.py output JSON.",
    )
    _ = parser.add_argument(
        "--querylog-json",
        required=True,
        help="Path to collect_hot_query_log.py output JSON.",
    )
    _ = parser.add_argument(
        "--status-file",
        default=DEFAULT_STATUS_FILE,
        help="Path to poeninja_snapshot status JSON.",
    )
    _ = parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for assembled baseline evidence JSON.",
    )
    return parser


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    if not path.exists() or not path.is_file():
        raise EvidenceBuildError(f"missing {label} file: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceBuildError(
            f"failed to read {label} json ({path}): {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError(f"{label} json must be an object: {path}")
    return cast(dict[str, object], parsed)


def _require_number(value: object, *, context: str) -> float:
    if not isinstance(value, (int, float)):
        raise EvidenceBuildError(f"missing required numeric metric: {context}")
    return float(value)


def _extract_selected_runs(
    benchmark_payload: dict[str, object],
) -> list[dict[str, object]]:
    raw_runs = benchmark_payload.get("runs")
    if not isinstance(raw_runs, list):
        raise EvidenceBuildError("benchmark json missing runs array")

    successful_runs: list[dict[str, object]] = []
    for idx, raw in enumerate(raw_runs, start=1):
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "")
        query_id = str(raw.get("query_id") or "").strip()
        run_index_raw = raw.get("run_index")
        if status != "ok" or not query_id or not isinstance(run_index_raw, int):
            continue
        successful_runs.append(
            {
                "run_index": int(run_index_raw),
                "query_id": query_id,
                "source_position": idx,
            }
        )

    successful_runs.sort(key=lambda item: int(cast(int, item["run_index"])))
    if len(successful_runs) < AGGREGATE_RUN_COUNT:
        raise EvidenceBuildError(
            "benchmark json must contain at least 3 successful runs with run_index/query_id"
        )
    return successful_runs[:AGGREGATE_RUN_COUNT]


def _build_querylog_index(
    querylog_payload: dict[str, object],
) -> dict[str, dict[str, object]]:
    rows = querylog_payload.get("rows")
    if not isinstance(rows, list):
        raise EvidenceBuildError("query-log json missing rows array")

    index: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        query_id = str(row.get("query_id") or "").strip()
        if not query_id:
            continue
        if query_id not in index:
            index[query_id] = cast(dict[str, object], row)

    if not index:
        raise EvidenceBuildError("query-log json has no rows keyed by query_id")
    return index


def _parse_metric_runs(
    selected_runs: list[dict[str, object]], querylog_index: dict[str, dict[str, object]]
) -> list[MetricRun]:
    metric_runs: list[MetricRun] = []
    for run in selected_runs:
        run_index = int(cast(int, run["run_index"]))
        query_id = str(run["query_id"])
        row = querylog_index.get(query_id)
        if row is None:
            raise EvidenceBuildError(
                f"missing query-log row for benchmark query_id={query_id} run_index={run_index}"
            )

        metric_runs.append(
            MetricRun(
                run_index=run_index,
                query_id=query_id,
                query_duration_ms=_require_number(
                    row.get("query_duration_ms"),
                    context=f"rows[{query_id}].query_duration_ms",
                ),
                read_rows=_require_number(
                    row.get("read_rows"),
                    context=f"rows[{query_id}].read_rows",
                ),
                read_bytes=_require_number(
                    row.get("read_bytes"),
                    context=f"rows[{query_id}].read_bytes",
                ),
                memory_usage=_require_number(
                    row.get("memory_usage"),
                    context=f"rows[{query_id}].memory_usage",
                ),
            )
        )

    if len(metric_runs) != AGGREGATE_RUN_COUNT:
        raise EvidenceBuildError(
            f"expected exactly {AGGREGATE_RUN_COUNT} matched runs, got {len(metric_runs)}"
        )
    return sorted(metric_runs, key=lambda item: item.run_index)


def _aggregate_3(values: list[float]) -> dict[str, object]:
    if len(values) != AGGREGATE_RUN_COUNT:
        raise EvidenceBuildError(
            f"expected {AGGREGATE_RUN_COUNT} metric values for aggregate, got {len(values)}"
        )
    return {
        "run_count": AGGREGATE_RUN_COUNT,
        "values": [round(item, 3) for item in values],
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "max": round(max(values), 3),
        "mean": round(statistics.mean(values), 3),
    }


def _peak_concurrency(
    querylog_index: dict[str, dict[str, object]], query_ids: list[str]
) -> int:
    events: list[tuple[float, int]] = []
    for query_id in query_ids:
        row = querylog_index.get(query_id)
        if row is None:
            continue
        start_us = row.get("query_start_time_microseconds")
        duration_ms = row.get("query_duration_ms")
        if not isinstance(start_us, (int, float)) or not isinstance(
            duration_ms, (int, float)
        ):
            continue
        start_s = float(start_us) / 1_000_000.0
        end_s = start_s + (float(duration_ms) / 1_000.0)
        events.append((start_s, 1))
        events.append((end_s, -1))

    if not events:
        return len(query_ids)

    active = 0
    peak = 0
    for _, delta in sorted(events, key=lambda item: (item[0], -item[1])):
        active += delta
        if active > peak:
            peak = active
    return max(peak, 1)


def _parse_status(status_payload: dict[str, object]) -> dict[str, object]:
    rebuild_skipped = status_payload.get("rebuild_skipped")
    if not isinstance(rebuild_skipped, bool):
        raise EvidenceBuildError(
            "status json missing required boolean key: rebuild_skipped"
        )
    elapsed_seconds = _require_number(
        status_payload.get("elapsed_seconds"), context="status.elapsed_seconds"
    )
    rebuild_skip_reason = str(status_payload.get("rebuild_skip_reason") or "")
    return {
        "mode": "rebuild_skipped" if rebuild_skipped else "rebuild_executed",
        "rebuild_skipped": rebuild_skipped,
        "rebuild_skip_reason": rebuild_skip_reason,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }


def _validate_required_output_metrics(payload: dict[str, object]) -> None:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise EvidenceBuildError("output payload missing metrics object")

    missing_metrics = [key for key in REQUIRED_OUTPUT_METRICS if key not in metrics]
    if missing_metrics:
        raise EvidenceBuildError(
            "output payload missing required metrics: " + ", ".join(missing_metrics)
        )

    for key in REQUIRED_QUERY_METRICS:
        metric_block = metrics.get(key)
        if not isinstance(metric_block, dict):
            raise EvidenceBuildError(f"missing required metric block: metrics.{key}")
        aggregate = metric_block.get("aggregate_3_runs")
        if not isinstance(aggregate, dict):
            raise EvidenceBuildError(
                f"missing required 3-run aggregate: metrics.{key}.aggregate_3_runs"
            )
        run_count = aggregate.get("run_count")
        if run_count != AGGREGATE_RUN_COUNT:
            raise EvidenceBuildError(
                f"metrics.{key}.aggregate_3_runs.run_count must be {AGGREGATE_RUN_COUNT}"
            )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    benchmark_path = Path(str(args.benchmark_json))
    querylog_path = Path(str(args.querylog_json))
    status_path = Path(str(args.status_file))
    output_path = Path(str(args.output))

    try:
        benchmark_payload = _load_json_object(benchmark_path, label="benchmark")
        querylog_payload = _load_json_object(querylog_path, label="query-log")
        status_payload = _load_json_object(status_path, label="status")

        selected_runs = _extract_selected_runs(benchmark_payload)
        querylog_index = _build_querylog_index(querylog_payload)
        metric_runs = _parse_metric_runs(selected_runs, querylog_index)
        status_info = _parse_status(status_payload)

        query_ids = [entry.query_id for entry in metric_runs]
        query_duration_values = [entry.query_duration_ms for entry in metric_runs]
        read_rows_values = [entry.read_rows for entry in metric_runs]
        read_bytes_values = [entry.read_bytes for entry in metric_runs]
        memory_usage_values = [entry.memory_usage for entry in metric_runs]

        payload: dict[str, object] = {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "artifact": "task-1-baseline-shared-host",
            "inputs": {
                "benchmark_json": str(benchmark_path),
                "querylog_json": str(querylog_path),
                "status_file": str(status_path),
            },
            "sample": {
                "run_count": AGGREGATE_RUN_COUNT,
                "query_ids": query_ids,
                "run_indexes": [entry.run_index for entry in metric_runs],
            },
            "rebuild": status_info,
            "metrics": {
                "query_duration_ms": {
                    "aggregate_3_runs": _aggregate_3(query_duration_values),
                },
                "read_rows": {
                    "aggregate_3_runs": _aggregate_3(read_rows_values),
                },
                "read_bytes": {
                    "aggregate_3_runs": _aggregate_3(read_bytes_values),
                },
                "memory_usage": {
                    "aggregate_3_runs": _aggregate_3(memory_usage_values),
                },
                "concurrent_heavy_query_count": {
                    "value": _peak_concurrency(querylog_index, query_ids),
                },
                "rebuild_cycle_time_seconds": {
                    "value": status_info["elapsed_seconds"],
                },
            },
            "status": "ok",
        }

        _validate_required_output_metrics(payload)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        _ = output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"task-1 baseline evidence assembled: wrote {output_path}")
        return 0
    except EvidenceBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
