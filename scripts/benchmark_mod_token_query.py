#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

from poe_trade.config import settings as config_settings
from poe_trade.db import ClickHouseClient
from poe_trade.db.clickhouse import ClickHouseClientError

DEFAULT_OUTPUT_PATH = ".sisyphus/evidence/task-1-baseline-shared-host.json"


class RunResult(TypedDict):
    run_index: int
    query_id: str
    started_at_utc: str
    completed_at_utc: str
    duration_ms: float
    row_count: int
    status: Literal["ok", "error"]
    error: str | None


QueryMode = Literal["legacy", "rollup"]


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _legacy_mod_token_query(*, league: str, page_size: int) -> str:
    return " ".join(
        [
            "SELECT",
            "item_id,",
            "groupArray(mod_token) AS mod_tokens,",
            "max(as_of_ts) AS max_as_of_ts",
            "FROM poe_trade.ml_item_mod_tokens_v1",
            f"WHERE league = {_quote(league)}",
            "AND item_id > ''",
            "GROUP BY item_id",
            "ORDER BY item_id",
            f"LIMIT {max(1, page_size)}",
            "FORMAT JSONEachRow",
        ]
    )


def _rollup_mod_token_query(*, league: str, page_size: int) -> str:
    return " ".join(
        [
            "SELECT",
            "item_id,",
            "groupArrayMerge(mod_tokens_state) AS mod_tokens,",
            "maxMerge(max_as_of_ts_state) AS max_as_of_ts",
            "FROM poe_trade.ml_item_mod_rollups_v1",
            f"WHERE league = {_quote(league)}",
            "AND item_id > ''",
            "GROUP BY item_id",
            "ORDER BY item_id",
            f"LIMIT {max(1, page_size)}",
            "FORMAT JSONEachRow",
        ]
    )


def _count_json_each_row(payload: str) -> int:
    row_count = 0
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed_obj: object = json.loads(line)
        if not isinstance(parsed_obj, dict):
            raise ValueError("JSONEachRow payload contains a non-object row")
        row_count += 1
    return row_count


def _iso_utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run_once(
    client: ClickHouseClient,
    *,
    mode: QueryMode,
    league: str,
    page_size: int,
) -> RunResult:
    query_id = f"task1-{mode}-mod-token-{uuid.uuid4()}"
    started_at = _iso_utc_now()
    start_perf = time.perf_counter()
    query = (
        _legacy_mod_token_query(league=league, page_size=page_size)
        if mode == "legacy"
        else _rollup_mod_token_query(league=league, page_size=page_size)
    )
    try:
        payload = client.execute(
            query,
            settings={"query_id": query_id},
        )
        row_count = _count_json_each_row(payload)
        duration_ms = round((time.perf_counter() - start_perf) * 1000.0, 3)
        return {
            "run_index": 0,
            "query_id": query_id,
            "started_at_utc": started_at,
            "completed_at_utc": _iso_utc_now(),
            "duration_ms": duration_ms,
            "row_count": row_count,
            "status": "ok",
            "error": None,
        }
    except (ClickHouseClientError, json.JSONDecodeError, ValueError) as exc:
        duration_ms = round((time.perf_counter() - start_perf) * 1000.0, 3)
        return {
            "run_index": 0,
            "query_id": query_id,
            "started_at_utc": started_at,
            "completed_at_utc": _iso_utc_now(),
            "duration_ms": duration_ms,
            "row_count": 0,
            "status": "error",
            "error": str(exc),
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the legacy mod-token hot query repeatedly and write deterministic "
            "JSON benchmark metrics."
        )
    )
    _ = parser.add_argument(
        "--league",
        default="Mirage",
        help="League filter for the benchmark query.",
    )
    _ = parser.add_argument(
        "--mode",
        choices=["legacy", "rollup"],
        default="legacy",
        help="Query mode: legacy raw-token aggregation or rollup-state merge.",
    )
    _ = parser.add_argument(
        "--page-size",
        type=int,
        default=5000,
        help="LIMIT value used by the legacy query.",
    )
    _ = parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of benchmark repetitions.",
    )
    _ = parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSON path for benchmark metrics.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    league = str(args.league)
    mode_value = str(args.mode)
    if mode_value not in {"legacy", "rollup"}:
        parser.error("--mode must be one of: legacy, rollup")
    mode: QueryMode = "legacy" if mode_value == "legacy" else "rollup"
    page_size = int(args.page_size)
    run_count = int(args.runs)
    output_path = Path(str(args.output))

    if page_size <= 0:
        parser.error("--page-size must be greater than 0")
    if run_count <= 0:
        parser.error("--runs must be greater than 0")

    cfg = config_settings.get_settings()
    client = ClickHouseClient.from_env(cfg.clickhouse_url)

    run_results: list[RunResult] = []
    for idx in range(run_count):
        result = _run_once(client, mode=mode, league=league, page_size=page_size)
        result["run_index"] = idx + 1
        run_results.append(result)

    successful_runs = [entry for entry in run_results if entry["status"] == "ok"]
    durations = [float(entry["duration_ms"]) for entry in successful_runs]

    summary: dict[str, object] = {
        "timing_ms": {
            "min": round(min(durations), 3) if durations else None,
            "median": round(statistics.median(durations), 3) if durations else None,
            "max": round(max(durations), 3) if durations else None,
        },
        "query_ids": [str(entry["query_id"]) for entry in run_results],
        "mode": mode,
        "success_count": len(successful_runs),
        "failure_count": len(run_results) - len(successful_runs),
    }

    output_payload: dict[str, object] = {
        "benchmark": f"{mode}_mod_token_query",
        "mode": mode,
        "league": league,
        "page_size": page_size,
        "runs_requested": run_count,
        "generated_at_utc": _iso_utc_now(),
        "summary": summary,
        "runs": run_results,
        "status": "ok"
        if len(successful_runs) == len(run_results)
        else "query_failures",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = output_path.write_text(
        json.dumps(output_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if len(successful_runs) != len(run_results):
        failed_count = len(run_results) - len(successful_runs)
        print(f"ERROR: {failed_count} benchmark run(s) failed; wrote {output_path}")
        return 1

    print(
        f"benchmark completed: mode={mode} league={league} page_size={page_size} runs={run_count}; wrote {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
