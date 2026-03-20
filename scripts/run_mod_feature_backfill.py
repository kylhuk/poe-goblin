#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from typing import Any

from poe_trade.config.settings import Settings
from poe_trade.db.clickhouse import ClickHouseClient, ClickHouseClientError
from poe_trade.ml import workflows


DEFAULT_CHUNK_SIZE = 5000


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Chunked PoE Ninja mod feature backfill driven by checkpoint tables."
        )
    )
    parser.add_argument("--run-id", required=True, help="Logical ID for the backfill run.")
    parser.add_argument("--league", default="Mirage", help="League for the backfill run.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Number of items to process per chunk.",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Optional cap on the number of chunks to process.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the first non-completed chunk for the given run.",
    )
    return parser


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _chunk_query(league: str, chunk_size: int, offset: int) -> str:
    return " ".join(
        [
            "SELECT",
            "item_id",
            "groupArrayMerge(mod_tokens_state) AS mod_tokens,",
            "maxMerge(max_as_of_ts_state) AS max_as_of_ts",
            "FROM poe_trade.ml_item_mod_feature_states_v1",
            f"WHERE league = {_quote(league)}",
            "GROUP BY item_id",
            "ORDER BY item_id",
            f"LIMIT {max(1, chunk_size)}",
            f"OFFSET {max(0, offset)}",
            "FORMAT JSONEachRow",
        ]
    )


def _count_items(client: ClickHouseClient, league: str) -> int:
    query = (
        "SELECT count() AS value"
        " FROM poe_trade.ml_item_mod_feature_states_v1"
        f" WHERE league = {_quote(league)}"
    )
    return workflows._scalar_count(client, query)


def _next_chunk_index(client: ClickHouseClient, run_id: str) -> int:
    rows = workflows._query_rows(
        client,
        " ".join(
            [
                "SELECT chunk_index, status",
                "FROM poe_trade.poeninja_backfill_chunks",
                f"WHERE run_id = '{run_id}'",
                "ORDER BY chunk_index",
                "FORMAT JSONEachRow",
            ]
        ),
    )
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status != "completed":
            return int(row.get("chunk_index") or 0)
    return len(rows)


def _record_run_status(
    client: ClickHouseClient,
    run_id: str,
    league: str,
    status: str,
    chunk_size: int,
    total_chunks: int,
    error_message: str = "",
) -> None:
    now = workflows._now_ts()
    query = "\n".join(
        [
            "INSERT INTO poe_trade.poeninja_backfill_runs",
            "(run_id, league, chunk_size, total_chunks, status, started_at, finished_at, error_message)",
            "VALUES",
            "(\n             '{run_id}', '{league}', {chunk_size}, {total_chunks}, '{status}',",
            "             toDateTime64('{now}', 3, 'UTC'), toDateTime64('{now}', 3, 'UTC'), '{error_message}'\n            )",
        ]
    ).format(
        run_id=run_id,
        league=league,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        status=status,
        now=now,
        error_message=error_message.replace("'", "''"),
    )
    client.execute(query)


def _record_chunk_status(
    client: ClickHouseClient,
    run_id: str,
    chunk_index: int,
    league: str,
    chunk_start: str,
    chunk_end: str,
    status: str,
    inserted_rows: int,
    checksum: str,
    error_message: str = "",
) -> None:
    started_at = workflows._now_ts()
    finished_at = workflows._now_ts() if status in {"completed", "failed"} else "1970-01-01 00:00:00.000"
    query = "\n".join(
        [
            "INSERT INTO poe_trade.poeninja_backfill_chunks",
            "(run_id, chunk_index, league, chunk_start, chunk_end_inclusive, status, retries, checksum, inserted_rows, started_at, finished_at, error_message)",
            "VALUES",
            "(\n             '{run_id}', {chunk_index}, '{league}', '{chunk_start}', '{chunk_end}',",
            "             '{status}', 0, '{checksum}', {inserted_rows},",
            "             toDateTime64('{started_at}', 3, 'UTC'), toDateTime64('{finished_at}', 3, 'UTC'), '{error_message}'\n            )",
        ]
    ).format(
        run_id=run_id,
        chunk_index=chunk_index,
        league=league,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        status=status,
        checksum=checksum,
        inserted_rows=inserted_rows,
        started_at=started_at,
        finished_at=finished_at,
        error_message=error_message.replace("'", "''"),
    )
    client.execute(query)


def _build_chunk_checksum(rows: list[dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for row in rows:
        tokens = row.get("mod_tokens") or []
        normalized = [str(token) for token in tokens]
        payload = f"{row.get('item_id')}|{','.join(normalized)}|{row.get('max_as_of_ts')}"
        hasher.update(payload.encode("utf-8"))
    return hasher.hexdigest()


def _process_chunk_rows(client: ClickHouseClient, league: str, rows: list[dict[str, Any]]) -> None:
    batch: list[dict[str, Any]] = []
    now = workflows._now_ts()
    for row in rows:
        item_id = str(row.get("item_id") or "").strip()
        if not item_id:
            continue
        tokens = row.get("mod_tokens") or []
        mod_tokens = [str(token) for token in tokens]
        features = workflows._mod_features_from_tokens(mod_tokens)
        mod_features_json = json.dumps(features, separators=(",", ":"))
        batch.append(
            {
                "league": league,
                "item_id": item_id,
                "mod_features_json": mod_features_json,
                "mod_count": len(mod_tokens),
                "as_of_ts": str(row.get("max_as_of_ts") or now),
                "updated_at": now,
            }
        )
    workflows._insert_json_rows(client, "poe_trade.ml_item_mod_features_v1", batch)
    return len(batch)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()
    client = ClickHouseClient.from_env(settings.clickhouse_url)

    chunk_size = max(1, args.chunk_size)
    total_items = _count_items(client, args.league)
    if total_items == 0:
        print("No items found for league", args.league)
        return 0
    total_chunks = math.ceil(total_items / chunk_size)
    _record_run_status(
        client,
        args.run_id,
        args.league,
        "running",
        chunk_size,
        total_chunks,
    )
    rows_processed = 0
    chunk_index = _next_chunk_index(client, args.run_id) if args.resume else 0
    try:
        while chunk_index < total_chunks:
            if args.max_chunks is not None and chunk_index >= args.max_chunks:
                break
            offset = chunk_index * chunk_size
            rows = workflows._query_rows(client, _chunk_query(args.league, chunk_size, offset))
            if not rows:
                break
            chunk_start = str(rows[0].get("item_id") or "").strip()
            chunk_end = str(rows[-1].get("item_id") or "").strip()
            _record_chunk_status(
                client,
                args.run_id,
                chunk_index,
                args.league,
                chunk_start,
                chunk_end,
                "running",
                0,
                "",
            )
            inserted = _process_chunk_rows(client, args.league, rows)
            rows_processed += inserted
            checksum = _build_chunk_checksum(rows)
            _record_chunk_status(
                client,
                args.run_id,
                chunk_index,
                args.league,
                chunk_start,
                chunk_end,
                "completed",
                inserted,
                checksum,
            )
            chunk_index += 1
    except ClickHouseClientError as exc:
        _record_chunk_status(
            client,
            args.run_id,
            chunk_index,
            args.league,
            "",
            "",
            "failed",
            0,
            "",
            str(exc) or "backfill failure",
        )
        _record_run_status(
            client,
            args.run_id,
            args.league,
            "failed",
            chunk_size,
            total_chunks,
            str(exc) or "backfill failure",
        )
        print("ERROR: backfill chunk failed", exc, file=sys.stderr)
        return 1
    _record_run_status(
        client,
        args.run_id,
        args.league,
        "completed",
        chunk_size,
        total_chunks,
    )
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "league": args.league,
                "rows_processed": rows_processed,
                "chunks": chunk_index,
                "total_chunks": total_chunks,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
