#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from poe_trade.config import settings
from poe_trade.db import ClickHouseClient
from poe_trade.ml import workflows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate ml/anchor/hybrid single-item pricing modes"
    )
    parser.add_argument("--league", required=True)
    parser.add_argument("--dataset-table", default="poe_trade.ml_price_dataset_v2")
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--league-reset-start", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cfg = settings.get_settings()
    client = ClickHouseClient.from_env(cfg.clickhouse_url)
    payload = workflows.compare_single_item_algorithms(
        client,
        league=str(args.league),
        dataset_table=str(args.dataset_table),
        limit=max(1, int(args.limit)),
        league_reset_start=(str(args.league_reset_start).strip() or None),
    )

    output_path = Path(str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
