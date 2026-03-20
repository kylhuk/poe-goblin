#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from poe_trade.config.settings import Settings
from poe_trade.db.clickhouse import ClickHouseClient, ClickHouseClientError


OUTPUT_SCHEMA_VERSION = "task-1-query-log-v1"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect baseline query metrics from system.query_log and emit "
            "normalized JSON for Task-1 evidence assembly."
        )
    )
    _ = parser.add_argument(
        "--query-id",
        action="append",
        default=[],
        help="Query ID to extract (repeatable).",
    )
    _ = parser.add_argument(
        "--since-seconds",
        type=int,
        default=None,
        help="Collect rows with event_time within the last N seconds.",
    )
    _ = parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of rows to return (default: 200).",
    )
    _ = parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path or '-' for stdout (default: -).",
    )
    return parser


def _escape_sql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _build_query(*, query_ids: list[str], since_seconds: int | None, limit: int) -> str:
    where_clauses = ["type = 'QueryFinish'", "is_initial_query = 1"]
    if query_ids:
        in_values = ", ".join(
            f"'{_escape_sql_string(query_id)}'" for query_id in query_ids
        )
        where_clauses.append(f"query_id IN ({in_values})")
    if since_seconds is not None:
        where_clauses.append(f"event_time >= now() - INTERVAL {since_seconds:d} SECOND")

    where_sql = "\n  AND ".join(where_clauses)
    return (
        "SELECT\n"
        "  query_id,\n"
        "  initial_query_id,\n"
        "  event_time,\n"
        "  event_time_microseconds,\n"
        "  query_start_time,\n"
        "  query_start_time_microseconds,\n"
        "  query_duration_ms,\n"
        "  query_kind,\n"
        "  query,\n"
        "  normalized_query_hash,\n"
        "  read_rows,\n"
        "  read_bytes,\n"
        "  result_rows,\n"
        "  result_bytes,\n"
        "  written_rows,\n"
        "  written_bytes,\n"
        "  memory_usage,\n"
        "  exception_code,\n"
        "  exception,\n"
        "  user,\n"
        "  current_database\n"
        "FROM system.query_log\n"
        f"WHERE {where_sql}\n"
        "ORDER BY event_time_microseconds DESC\n"
        f"LIMIT {limit:d}\n"
        "FORMAT JSONEachRow"
    )


def _parse_json_each_row(payload: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(cast(dict[str, object], item))
    return rows


def _query_text_hash(query_text: str) -> str | None:
    stripped = query_text.strip()
    if not stripped:
        return None
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def _normalize_row(row: dict[str, object]) -> dict[str, object]:
    query_text = str(row.get("query") or "")
    return {
        "query_id": row.get("query_id"),
        "initial_query_id": row.get("initial_query_id"),
        "event_time": row.get("event_time"),
        "event_time_microseconds": row.get("event_time_microseconds"),
        "query_start_time": row.get("query_start_time"),
        "query_start_time_microseconds": row.get("query_start_time_microseconds"),
        "query_duration_ms": row.get("query_duration_ms"),
        "query_kind": row.get("query_kind"),
        "normalized_query_hash": row.get("normalized_query_hash"),
        "query_text_hash": _query_text_hash(query_text),
        "read_rows": row.get("read_rows"),
        "read_bytes": row.get("read_bytes"),
        "result_rows": row.get("result_rows"),
        "result_bytes": row.get("result_bytes"),
        "written_rows": row.get("written_rows"),
        "written_bytes": row.get("written_bytes"),
        "memory_usage": row.get("memory_usage"),
        "exception_code": row.get("exception_code"),
        "exception": row.get("exception") or None,
        "user": row.get("user"),
        "current_database": row.get("current_database"),
    }


def _emit_output(output: str, payload: dict[str, object]) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output == "-":
        sys.stdout.write(serialized)
        return
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = output_path.write_text(serialized, encoding="utf-8")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    query_ids = [str(item).strip() for item in args.query_id]
    query_ids = sorted({query_id for query_id in query_ids if query_id})
    since_seconds = args.since_seconds
    limit = args.limit
    output = args.output

    if not query_ids and since_seconds is None:
        parser.error("provide at least one --query-id or --since-seconds")
    if since_seconds is not None and since_seconds <= 0:
        parser.error("--since-seconds must be a positive integer")
    if limit <= 0:
        parser.error("--limit must be a positive integer")

    settings = Settings.from_env()
    client = ClickHouseClient.from_env(settings.clickhouse_url)
    query_sql = _build_query(
        query_ids=query_ids, since_seconds=since_seconds, limit=limit
    )

    try:
        raw = client.execute(query_sql)
    except ClickHouseClientError as exc:
        print(f"ERROR: failed to query system.query_log: {exc}", file=sys.stderr)
        return 1

    rows = _parse_json_each_row(raw)
    normalized_rows = [_normalize_row(row) for row in rows]
    if not normalized_rows:
        filter_text = []
        if query_ids:
            filter_text.append(f"query_ids={','.join(query_ids)}")
        if since_seconds is not None:
            filter_text.append(f"since_seconds={since_seconds}")
        filter_text.append(f"limit={limit}")
        details = " ".join(filter_text)
        print(
            f"ERROR: no system.query_log rows found for filters: {details}",
            file=sys.stderr,
        )
        return 2

    output_payload: dict[str, object] = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "source": "system.query_log",
        "filters": {
            "query_ids": query_ids,
            "since_seconds": since_seconds,
            "limit": limit,
        },
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
    }
    _emit_output(output, output_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
