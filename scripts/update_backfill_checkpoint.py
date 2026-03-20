#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from poe_trade.config.settings import Settings
from poe_trade.db.clickhouse import ClickHouseClient, ClickHouseClientError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Advance the PoE Ninja historical backfill checkpoints."
    )
    parser.add_argument("--run-id", required=True, help="Backfill run identifier.")
    parser.add_argument("--league", default="Mirage", help="League for the run.")
    parser.add_argument("--chunk-index", type=int, required=True)
    parser.add_argument("--chunk-start", required=True)
    parser.add_argument("--chunk-end", required=True)
    parser.add_argument(
        "--status",
        choices=("pending", "running", "completed", "failed"),
        required=True,
    )
    parser.add_argument("--inserted-rows", type=int, default=0)
    parser.add_argument("--checksum", default="")
    parser.add_argument("--error", default="")
    parser.add_argument("--update-run", action="store_true", help="Update the run status row to match the chunk.")
    return parser


def _now_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _query_existing_chunk(client: ClickHouseClient, run_id: str, chunk_index: int) -> dict[str, Any] | None:
    query = (
        "SELECT status, retries, finished_at"
        " FROM poe_trade.poeninja_backfill_chunks"
        f" WHERE run_id = '{run_id}' AND chunk_index = {chunk_index}"
        " ORDER BY finished_at DESC"
        " LIMIT 1 FORMAT JSONEachRow"
    )
    payload = client.execute(query)
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[0])
    except Exception:
        return None


def _update_chunk(
    client: ClickHouseClient,
    run_id: str,
    league: str,
    chunk_index: int,
    chunk_start: str,
    chunk_end: str,
    status: str,
    inserted_rows: int,
    checksum: str,
    error: str,
) -> None:
    existing = _query_existing_chunk(client, run_id, chunk_index)
    retries = int((existing or {}).get("retries")) if existing else 0
    if status == "failed":
        retries += 1
    started_at = _now_ts()
    finished_at = _now_ts() if status in ("completed", "failed") else started_at
    checksum_value = checksum or (existing or {}).get("checksum", "")

    insert_sql = "\n".join(
        [
            "INSERT INTO poe_trade.poeninja_backfill_chunks",
            "(run_id, chunk_index, league, chunk_start, chunk_end_inclusive, status, retries, checksum, inserted_rows, started_at, finished_at, error_message)",
            "VALUES",
            "(\n             '{run_id}', {chunk_index}, '{league}', '{chunk_start}', '{chunk_end}',\n             '{status}', {retries}, '{checksum_value}', {inserted_rows},\n             toDateTime64('{started_at}', 3, 'UTC'), toDateTime64('{finished_at}', 3, 'UTC'), '{error}'\n            )"
        ]
    ).format(
        run_id=run_id,
        chunk_index=chunk_index,
        league=league,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        status=status,
        retries=retries,
        checksum_value=checksum_value,
        inserted_rows=inserted_rows,
        started_at=started_at,
        finished_at=finished_at,
        error=error.replace("'", "''"),
    )
    client.execute(insert_sql)


def _update_run_status(client: ClickHouseClient, run_id: str, league: str, status: str) -> None:
    now = _now_ts()
    query = "\n".join(
        [
            "INSERT INTO poe_trade.poeninja_backfill_runs",
            "(run_id, league, status, started_at, finished_at)",
            "VALUES",
            f"('{run_id}', '{league}', '{status}', toDateTime64('{now}', 3, 'UTC'), toDateTime64('{now}', 3, 'UTC'))",
        ]
    )
    client.execute(query)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()
    client = ClickHouseClient.from_env(settings.clickhouse_url)

    try:
        _update_chunk(
            client,
            args.run_id,
            args.league,
            args.chunk_index,
            args.chunk_start,
            args.chunk_end,
            args.status,
            args.inserted_rows,
            args.checksum,
            args.error,
        )
        if args.update_run:
            _update_run_status(client, args.run_id, args.status)
    except ClickHouseClientError as exc:
        print(f"ERROR: failed to update backfill checkpoint: {exc}", file=sys.stderr)
        return 1

    print("Backfill checkpoint updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
