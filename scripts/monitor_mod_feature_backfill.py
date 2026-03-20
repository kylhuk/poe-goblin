#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from poe_trade.config.settings import Settings
from poe_trade.db.clickhouse import ClickHouseClient
from poe_trade.ml import workflows


DEFAULT_CHUNK_SIZE = 5000


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor PoE Ninja mod feature backfill progress backed by checkpoints."
    )
    parser.add_argument("--run-id", required=True, help="Backfill run ID to inspect.")
    parser.add_argument("--league", default="Mirage", help="League for the run.")
    parser.add_argument(
        "--resume-script",
        default="scripts/run_mod_feature_backfill.py",
        help="Relative path to the backfill driver script for auto-resume.",
    )
    parser.add_argument(
        "--auto-resume",
        action="store_true",
        help="Trigger the backfill driver with --resume when failures detected.",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Optional cap forwarded to the backfill driver during resume.",
    )
    return parser


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run_summary(run_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_row.get("run_id"),
        "league": run_row.get("league"),
        "status": run_row.get("status"),
        "chunk_size": run_row.get("chunk_size"),
        "total_chunks": int(run_row.get("total_chunks") or 0),
    }


def _chunk_counts(client: ClickHouseClient, run_id: str) -> dict[str, int]:
    rows = workflows._query_rows(
        client,
        " ".join(
            [
                "SELECT status",
                "FROM poe_trade.poeninja_backfill_chunks",
                f"WHERE run_id = '{run_id}'",
                "FORMAT JSONEachRow",
            ]
        ),
    )
    counts: dict[str, int] = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for row in rows:
        status = str(row.get("status") or "").lower()
        counts[status] = counts.get(status, 0) + 1
    return counts


def _load_run_row(client: ClickHouseClient, run_id: str) -> dict[str, Any] | None:
    rows = workflows._query_rows(
        client,
        " ".join(
            [
                "SELECT run_id, league, status, chunk_size, total_chunks",
                "FROM poe_trade.poeninja_backfill_runs",
                f"WHERE run_id = '{run_id}'",
                "ORDER BY finished_at DESC",
                "LIMIT 1",
                "FORMAT JSONEachRow",
            ]
        ),
    )
    if not rows:
        return None
    return rows[0]


def _execute_resume_script(
    script_path: Path,
    run_id: str,
    league: str,
    chunk_size: int | None,
    max_chunks: int | None,
) -> int:
    command = [sys.executable, str(script_path.resolve()), "--run-id", run_id, "--league", league, "--resume"]
    if chunk_size is not None:
        command.extend(["--chunk-size", str(chunk_size)])
    if max_chunks is not None:
        command.extend(["--max-chunks", str(max_chunks)])
    return subprocess.run(command).returncode


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()
    client = ClickHouseClient.from_env(settings.clickhouse_url)

    run_row = _load_run_row(client, args.run_id)
    if run_row is None:
        print(f"No backfill run found for run_id={args.run_id}", file=sys.stderr)
        return 1
    summary = _run_summary(run_row)
    counts = _chunk_counts(client, args.run_id)

    print("Backfill run summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("Chunk status counts:")
    print(json.dumps(counts, indent=2, sort_keys=True))

    need_resume = counts.get("failed", 0) > 0 or counts.get("running", 0) == 0 and summary["status"] != "completed"
    if args.auto_resume and need_resume:
        resume_chunk_size = int(summary.get("chunk_size") or DEFAULT_CHUNK_SIZE)
        script_path = Path(__file__).resolve().parents[1] / args.resume_script
        print("Auto-resume triggered; running", script_path)
        return _execute_resume_script(
            script_path,
            args.run_id,
            args.league,
            resume_chunk_size,
            args.max_chunks,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
