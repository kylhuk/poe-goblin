from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from poe_trade.api.valuation import (
    build_comparable_query,
    build_stash_scan_valuations_payload,
    day_series_from_rows,
    normalize_chaos_price,
)
from poe_trade.db import ClickHouseClient


class _SequentialClickHouse(ClickHouseClient):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.responses = list(responses)
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:  # type: ignore[override]
        del settings
        self.queries.append(query)
        if self.responses:
            return self.responses.pop(0)
        return ""


def test_build_comparable_query_filters_base_type_affixes_thresholds_and_age() -> None:
    query = build_comparable_query(
        league="Mirage",
        base_type="Hubris Circlet",
        affixes=["+93 to maximum Life", "+30% to Fire Resistance"],
        min_threshold=10,
        max_threshold=50,
        max_age_days=7,
    )

    assert "league = 'Mirage'" in query
    assert "base_type = 'Hubris Circlet'" in query
    assert "target_price_chaos >= 10" in query
    assert "target_price_chaos <= 50" in query
    assert "INTERVAL 7 DAY" in query
    assert "ml_fx_hour_latest_v2" in query
    assert "normalized_price_chaos" in query
    assert "+93 to maximum Life" in query
    assert "+30% to Fire Resistance" in query


def test_stash_scan_valuations_full_match_empty_runs_one_fallback_query_per_affix() -> (
    None
):
    scan_row = {
        "scan_id": "scan-1",
        "account_name": "qa-exile",
        "league": "Mirage",
        "realm": "pc",
        "tab_id": "tab-1",
        "tab_index": 0,
        "tab_name": "Currency",
        "tab_type": "normal",
        "lineage_key": "sig:item-1",
        "item_id": "item-1",
        "item_name": "Grim Bane",
        "item_class": "Helmet",
        "rarity": "rare",
        "x": 0,
        "y": 0,
        "w": 2,
        "h": 2,
        "listed_price": None,
        "currency": "chaos",
        "predicted_price": 42.0,
        "confidence": 0.9,
        "price_p10": 38.0,
        "price_p90": 51.0,
        "price_recommendation_eligible": 1,
        "estimate_trust": "normal",
        "estimate_warning": "",
        "fallback_reason": "",
        "icon_url": "https://example.invalid/icon.png",
        "priced_at": "2026-03-21 12:00:00",
        "payload_json": json.dumps(
            {
                "baseType": "Hubris Circlet",
                "typeLine": "Hubris Circlet",
                "explicitMods": [
                    "+93 to maximum Life",
                    "+30% to Fire Resistance",
                ],
            }
        ),
    }
    client = _SequentialClickHouse(
        [
            json.dumps(scan_row, ensure_ascii=False) + "\n",
            "",
            '{"as_of_ts":"2026-03-20 12:00:00","target_price_chaos":12.0,"target_price_divine":0.1,"mod_features_json":"{\\"+93 to maximum Life\\":1}"}\n',
            '{"as_of_ts":"2026-03-19 12:00:00","target_price_chaos":24.0,"target_price_divine":0.2,"mod_features_json":"{\\"+30% to Fire Resistance\\":1}"}\n',
        ]
    )

    payload = build_stash_scan_valuations_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        scan_id="scan-1",
        item_id="item-1",
        structured_mode=False,
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["structuredMode"] is False
    assert payload["stashId"] == "scan-1"
    assert payload["itemId"] == "item-1"
    assert payload["chaosMedian"] is None
    assert len(payload["daySeries"]) == 10
    assert all(entry["chaosMedian"] is None for entry in payload["daySeries"])
    assert payload["affixFallbackMedians"] == [
        {"affix": "+93 to maximum Life", "chaosMedian": 12.0},
        {"affix": "+30% to Fire Resistance", "chaosMedian": 24.0},
    ]
    assert len(client.queries) == 4
    assert any("+93 to maximum Life" in query for query in client.queries)
    assert any("+30% to Fire Resistance" in query for query in client.queries)


def test_stash_scan_valuations_empty_full_and_fallback_returns_null_median() -> None:
    scan_row = {
        "scan_id": "scan-1",
        "account_name": "qa-exile",
        "league": "Mirage",
        "realm": "pc",
        "tab_id": "tab-1",
        "tab_index": 0,
        "tab_name": "Currency",
        "tab_type": "normal",
        "lineage_key": "sig:item-1",
        "item_id": "item-1",
        "item_name": "Grim Bane",
        "item_class": "Helmet",
        "rarity": "rare",
        "x": 0,
        "y": 0,
        "w": 2,
        "h": 2,
        "listed_price": None,
        "currency": "chaos",
        "predicted_price": 42.0,
        "confidence": 0.9,
        "price_p10": 38.0,
        "price_p90": 51.0,
        "price_recommendation_eligible": 1,
        "estimate_trust": "normal",
        "estimate_warning": "",
        "fallback_reason": "",
        "icon_url": "https://example.invalid/icon.png",
        "priced_at": "2026-03-21 12:00:00",
        "payload_json": json.dumps(
            {
                "baseType": "Hubris Circlet",
                "typeLine": "Hubris Circlet",
                "explicitMods": [
                    "+93 to maximum Life",
                ],
            }
        ),
    }
    client = _SequentialClickHouse(
        [
            json.dumps(scan_row, ensure_ascii=False) + "\n",
            "",
            "",
        ]
    )

    payload = build_stash_scan_valuations_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        scan_id="scan-1",
        item_id="item-1",
        structured_mode=False,
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["chaosMedian"] is None
    assert payload["affixFallbackMedians"] == []


def test_day_series_from_rows_fills_missing_days_with_nulls() -> None:
    series = day_series_from_rows(
        [
            {"as_of_ts": "2026-03-01 12:00:00", "target_price_chaos": 10.0},
            {"as_of_ts": "2026-03-03 12:00:00", "target_price_chaos": 20.0},
            {"as_of_ts": "2026-03-10 12:00:00", "target_price_chaos": 30.0},
        ],
        days=10,
    )

    assert len(series) == 10
    assert series[0] == {"date": "2026-03-01", "chaosMedian": 10.0}
    assert series[1] == {"date": "2026-03-02", "chaosMedian": None}
    assert series[2] == {"date": "2026-03-03", "chaosMedian": 20.0}
    assert series[-1] == {"date": "2026-03-10", "chaosMedian": 30.0}


@pytest.mark.parametrize(
    ("value", "currency", "fx_rate", "expected"),
    [
        (5, "chaos", None, 5.0),
        (2, "divine", 150, 300.0),
        (2, "div", 200, 400.0),
        (2, "divine", None, None),
    ],
)
def test_normalize_chaos_price_handles_chaos_and_divine_aliases(
    value: object,
    currency: str,
    fx_rate: object | None,
    expected: float | None,
) -> None:
    assert (
        normalize_chaos_price(
            value,
            currency=currency,
            fx_chaos_per_divine=fx_rate,
        )
        == expected
    )
