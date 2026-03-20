#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from poe_trade.config.settings import Settings
from poe_trade.db.clickhouse import ClickHouseClient, ClickHouseClientError

EVIDENCE_NAME = "task-1-parity-contract.json"
EXPECTED_CONTRACTS: dict[str, dict[str, Any]] = {
    "raw_poeninja_currency_overview": {
        "matching_mode": "exact_order",
        "key_columns": ["league", "currency_type_name", "sample_time_utc"],
        "comparison_columns": [
            "line_type",
            "chaos_equivalent",
            "listing_count",
            "payload_json",
            "stale",
        ],
    },
    "ml_price_labels_v1": {
        "matching_mode": "exact_order",
        "key_columns": ["league", "realm", "item_id", "as_of_ts"],
        "comparison_columns": [
            "normalized_price_chaos",
            "stack_size",
            "outlier_status",
            "label_quality",
            "category",
            "base_type",
        ],
    },
    "ml_item_mod_features_v1": {
        "matching_mode": "exact_order",
        "key_columns": ["league", "item_id"],
        "comparison_columns": ["mod_features_json", "mod_count", "as_of_ts"],
    },
    "ml_price_dataset_v1": {
        "matching_mode": "exact_order",
        "key_columns": ["league", "item_id", "as_of_ts"],
        "comparison_columns": [
            "normalized_price_chaos",
            "support_count_recent",
            "mod_token_count",
            "route_candidate",
        ],
    },
    "ml_comps_v1": {
        "matching_mode": "exact_order",
        "key_columns": [
            "league",
            "as_of_ts",
            "target_item_id",
            "comp_item_id",
        ],
        "comparison_columns": ["distance_score", "comp_price_chaos", "retrieval_window_hours"],
    },
    "ml_serving_profile_v1": {
        "matching_mode": "set_equivalent",
        "key_columns": ["league", "category", "base_type", "profile_as_of_ts"],
        "comparison_columns": [
            "reference_price_p10",
            "reference_price_p50",
            "reference_price_p90",
            "support_count_recent",
        ],
    },
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the parity contract table and emit evidence for Task 1."
    )
    parser.add_argument(
        "--output",
        default=str(Path(".sisyphus/evidence") / EVIDENCE_NAME),
        help="Path to write the verification evidence JSON.",
    )
    return parser


def _parse_json_each_row(payload: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _compare_array(expected: list[Any], actual: list[Any]) -> bool:
    return [str(item) for item in expected] == [str(item) for item in actual]


def _validate_rows(rows: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    found = {row["table_name"]: row for row in rows}
    missing = []
    mismatches = []
    checked = []
    for table, spec in EXPECTED_CONTRACTS.items():
        row = found.get(table)
        if row is None:
            missing.append(table)
            continue
        checked.append(table)
        for field in ("matching_mode", "key_columns", "comparison_columns"):
            expected_value = spec.get(field)
            actual_value = row.get(field)
            if expected_value is None:
                continue
            if field.endswith("columns"):
                if not isinstance(actual_value, list) or not _compare_array(
                    expected_value, actual_value
                ):
                    mismatches.append(
                        f"{table}:{field}_mismatch (expected {expected_value}, got {actual_value})"
                    )
            else:
                if str(actual_value) != str(expected_value):
                    mismatches.append(
                        f"{table}:{field}_mismatch (expected {expected_value}, got {actual_value})"
                    )
    return missing, mismatches, checked


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    settings = Settings.from_env()
    client = ClickHouseClient.from_env(settings.clickhouse_url)
    query = (
        "SELECT table_name, matching_mode, key_columns, comparison_columns, watermark_columns"  # noqa: E501
        " FROM poe_trade.qa_parity_contract"
        " ORDER BY table_name"
        " FORMAT JSONEachRow"
    )

    try:
        payload = client.execute(query)
    except ClickHouseClientError as exc:
        print(f"ERROR: failed to query qa_parity_contract: {exc}", file=sys.stderr)
        return 1

    rows = _parse_json_each_row(payload)
    missing, mismatches, checked = _validate_rows(rows)

    payload: dict[str, Any] = {
        "checked_tables": checked,
        "missing_tables": missing,
        "mismatches": mismatches,
        "row_count": len(rows),
        "expected_count": len(EXPECTED_CONTRACTS),
        "status": (
            "ok"
            if not missing and not mismatches and len(rows) >= len(EXPECTED_CONTRACTS)
            else "contract_mismatch"
        ),
    }

    output_path = Path(str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if missing or mismatches or len(rows) < len(EXPECTED_CONTRACTS):
        print(
            f"ERROR: parity contract validation failed; details in {output_path}",
            file=sys.stderr,
        )
        return 2

    print(f"parity contract validation passed; wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
