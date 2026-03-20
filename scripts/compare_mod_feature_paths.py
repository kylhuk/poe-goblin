#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from poe_trade.config import settings as config_settings
from poe_trade.db import ClickHouseClient
from poe_trade.db.clickhouse import ClickHouseClientError

DEFAULT_OUTPUT_PATH = ".sisyphus/evidence/task-3-dual-read-baseline.json"


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _default_legacy_query(*, league: str, page_size: int, cursor: str) -> str:
    return " ".join(
        [
            "SELECT",
            "item_id,",
            "groupArray(mod_token) AS mod_tokens,",
            "max(as_of_ts) AS max_as_of_ts",
            "FROM poe_trade.ml_item_mod_tokens_v1",
            f"WHERE league = {_quote(league)}",
            f"AND item_id > {_quote(cursor)}",
            "GROUP BY item_id",
            "ORDER BY item_id",
            f"LIMIT {max(1, page_size)}",
            "FORMAT JSONEachRow",
        ]
    )


def _replace_template_vars(
    sql: str, *, league: str, page_size: int, cursor: str
) -> str:
    replacements = {
        "{{LEAGUE}}": _quote(league),
        "{{PAGE_SIZE}}": str(max(1, page_size)),
        "{{CURSOR}}": _quote(cursor),
    }
    result = sql
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def _parse_json_each_row(payload: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    tokens = row.get("mod_tokens")
    normalized_tokens = (
        [str(token) for token in tokens] if isinstance(tokens, list) else []
    )
    return {
        "item_id": str(row.get("item_id") or ""),
        "mod_tokens": normalized_tokens,
        "max_as_of_ts": str(row.get("max_as_of_ts") or ""),
    }


def _row_fingerprint(row: dict[str, Any], *, comparison_mode: str) -> str:
    tokens: list[str] = list(row["mod_tokens"])
    if comparison_mode == "multiset":
        tokens = sorted(tokens)
    payload = {
        "item_id": row["item_id"],
        "mod_tokens": tokens,
        "max_as_of_ts": row["max_as_of_ts"],
    }
    packed = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _execute_query(
    client: ClickHouseClient, *, query_id: str, sql: str
) -> list[dict[str, Any]]:
    payload = client.execute(sql, settings={"query_id": query_id})
    rows = _parse_json_each_row(payload)
    return [_normalize_row(row) for row in rows]


def _compare_rows(
    legacy_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    max_report: int,
    comparison_mode: str,
) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    sampled_keys = {
        "legacy_first_item_ids": [row.get("item_id") for row in legacy_rows[:5]],
        "candidate_first_item_ids": [row.get("item_id") for row in candidate_rows[:5]],
    }
    paired = min(len(legacy_rows), len(candidate_rows))
    for idx in range(paired):
        left = legacy_rows[idx]
        right = candidate_rows[idx]
        if _row_fingerprint(left, comparison_mode=comparison_mode) == _row_fingerprint(
            right, comparison_mode=comparison_mode
        ):
            continue
        mismatches.append(
            {
                "index": idx,
                "legacy": left,
                "candidate": right,
            }
        )
        break

    if len(legacy_rows) != len(candidate_rows) and len(mismatches) < max_report:
        mismatches.append(
            {
                "index": paired,
                "legacy": "<extra_rows>" if len(legacy_rows) > paired else "<none>",
                "candidate": "<extra_rows>"
                if len(candidate_rows) > paired
                else "<none>",
            }
        )

    return {
        "comparison_mode": comparison_mode,
        "legacy_row_count": len(legacy_rows),
        "candidate_row_count": len(candidate_rows),
        "mismatch_count": len(mismatches),
        "sampled_keys": sampled_keys,
        "mismatches": mismatches,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare legacy and candidate mod-feature source queries over the same "
            "league/cursor/page window and emit deterministic JSON diff output."
        )
    )
    _ = parser.add_argument("--league", default="Mirage")
    _ = parser.add_argument("--cursor", default="")
    _ = parser.add_argument("--page-size", type=int, default=5000)
    _ = parser.add_argument(
        "--legacy-sql",
        default="",
        help=(
            "Optional custom legacy SQL. Template variables allowed: "
            "{{LEAGUE}}, {{CURSOR}}, {{PAGE_SIZE}}."
        ),
    )
    _ = parser.add_argument(
        "--candidate-sql",
        default="",
        help=(
            "Optional candidate SQL. Template variables allowed: "
            "{{LEAGUE}}, {{CURSOR}}, {{PAGE_SIZE}}. "
            "If omitted, defaults to legacy SQL for baseline sanity checks."
        ),
    )
    _ = parser.add_argument("--max-mismatches", type=int, default=20)
    _ = parser.add_argument(
        "--comparison-mode",
        choices=["strict", "multiset"],
        default="strict",
        help=(
            "strict compares token arrays order-sensitively; multiset compares token "
            "arrays order-insensitively."
        ),
    )
    _ = parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    league = str(args.league)
    cursor = str(args.cursor)
    page_size = int(args.page_size)
    max_mismatches = int(args.max_mismatches)
    comparison_mode = str(args.comparison_mode)
    output_path = Path(str(args.output))

    if page_size <= 0:
        parser.error("--page-size must be > 0")
    if max_mismatches <= 0:
        parser.error("--max-mismatches must be > 0")

    legacy_sql_raw = str(args.legacy_sql).strip()
    candidate_sql_raw = str(args.candidate_sql).strip()

    if legacy_sql_raw:
        legacy_sql = _replace_template_vars(
            legacy_sql_raw, league=league, page_size=page_size, cursor=cursor
        )
    else:
        legacy_sql = _default_legacy_query(
            league=league, page_size=page_size, cursor=cursor
        )

    if candidate_sql_raw:
        candidate_sql = _replace_template_vars(
            candidate_sql_raw, league=league, page_size=page_size, cursor=cursor
        )
    else:
        candidate_sql = legacy_sql

    cfg = config_settings.get_settings()
    client = ClickHouseClient.from_env(cfg.clickhouse_url)

    legacy_query_id = (
        "task3-legacy-" + hashlib.sha1(legacy_sql.encode("utf-8")).hexdigest()[:12]
    )
    candidate_query_id = (
        "task3-candidate-"
        + hashlib.sha1(candidate_sql.encode("utf-8")).hexdigest()[:12]
    )

    try:
        legacy_rows = _execute_query(client, query_id=legacy_query_id, sql=legacy_sql)
        candidate_rows = _execute_query(
            client, query_id=candidate_query_id, sql=candidate_sql
        )
    except (ClickHouseClientError, json.JSONDecodeError) as exc:
        output = {
            "status": "query_error",
            "error": str(exc),
            "league": league,
            "cursor": cursor,
            "page_size": page_size,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _ = output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
        print(f"ERROR: failed to compare paths: {exc}", file=sys.stderr)
        return 1

    diff = _compare_rows(
        legacy_rows,
        candidate_rows,
        max_mismatches,
        comparison_mode,
    )
    payload = {
        "schema_version": "task-3-dual-read-v1",
        "status": "ok" if diff["mismatch_count"] == 0 else "mismatch",
        "league": league,
        "cursor": cursor,
        "page_size": page_size,
        "comparison_mode": comparison_mode,
        "legacy_query_id": legacy_query_id,
        "candidate_query_id": candidate_query_id,
        "legacy_sql_hash": hashlib.sha256(legacy_sql.encode("utf-8")).hexdigest(),
        "candidate_sql_hash": hashlib.sha256(candidate_sql.encode("utf-8")).hexdigest(),
        "diff": diff,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if diff["mismatch_count"] > 0:
        print(
            f"ERROR: found {diff['mismatch_count']} mismatches; wrote {output_path}",
            file=sys.stderr,
        )
        return 1
    print(f"dual-read comparator passed; wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
