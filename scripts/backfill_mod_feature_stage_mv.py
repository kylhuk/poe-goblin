#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from poe_trade.config.settings import Settings
from poe_trade.db.clickhouse import ClickHouseClient
from poe_trade.ml import workflows


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill mod-feature MV stage table in bounded hour chunks."
    )
    parser.add_argument("--league", default="Mirage")
    parser.add_argument("--max-hours", type=int, default=None)
    parser.add_argument("--truncate-first", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    settings = Settings.from_env()
    client = ClickHouseClient.from_env(settings.clickhouse_url)

    workflows._ensure_mod_feature_sql_stage_table(client)
    if args.truncate_first:
        client.execute("TRUNCATE TABLE poe_trade.ml_item_mod_features_sql_stage_v1")

    hour_rows = workflows._query_rows(
        client,
        " ".join(
            [
                "SELECT toStartOfHour(as_of_ts) AS hour_ts",
                "FROM poe_trade.ml_item_mod_tokens_v1",
                f"WHERE league = {workflows._quote(str(args.league))}",
                "GROUP BY hour_ts",
                "ORDER BY hour_ts",
                "FORMAT JSONEachRow",
            ]
        ),
    )

    inserted_hours = 0
    for row in hour_rows:
        if args.max_hours is not None and inserted_hours >= int(args.max_hours):
            break
        hour_ts = str(row.get("hour_ts") or "").strip()
        if not hour_ts:
            continue
        client.execute(
            "INSERT INTO poe_trade.ml_item_mod_features_sql_stage_v1 "
            + workflows._build_sql_mod_feature_stage_query(
                league=str(args.league), hour_ts=hour_ts
            ),
            settings=workflows._mod_feature_sql_query_settings(),
        )
        inserted_hours += 1

    print(json.dumps({"league": args.league, "hours_inserted": inserted_hours}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
