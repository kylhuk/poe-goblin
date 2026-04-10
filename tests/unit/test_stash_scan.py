from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from poe_trade.db import ClickHouseClient
from poe_trade.stash_scan import (
    content_signature_for_item,
    fetch_active_scan,
    fetch_active_valuation_refresh,
    fetch_item_history,
    fetch_latest_scan_run,
    fetch_latest_valuation_refresh_run,
    fetch_latest_published_valuation_refresh_run,
    fetch_published_tabs,
    fetch_published_scan_id,
    lineage_key_for_item,
    lineage_key_from_previous_scan,
    normalize_stash_prediction,
    normalize_chaos_price,
    price_band_for_delta_pct,
    fetch_valuation_refresh_status_payload,
    serialize_stash_item_to_clipboard,
)


class _StubClickHouse(ClickHouseClient):
    def __init__(self, payload: str) -> None:
        super().__init__(endpoint="http://clickhouse")
        self._payload = payload
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        self.queries.append(query)
        return self._payload


class _SequentialStubClickHouse(ClickHouseClient):
    def __init__(self, payloads: list[str]) -> None:
        super().__init__(endpoint="http://clickhouse")
        self._payloads = list(payloads)
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        self.queries.append(query)
        del settings
        if self._payloads:
            return self._payloads.pop(0)
        return ""


def test_lineage_key_prefers_upstream_item_id() -> None:
    item = {"id": "item-123", "name": "Chaos Orb", "typeLine": "Chaos Orb"}

    assert lineage_key_for_item(item) == "item:item-123"


def test_content_signature_ignores_position_changes() -> None:
    a = {
        "name": "Grim Bane",
        "typeLine": "Hubris Circlet",
        "x": 1,
        "y": 1,
        "explicitMods": ["+93 to maximum Life"],
    }
    b = {
        "name": "Grim Bane",
        "typeLine": "Hubris Circlet",
        "x": 4,
        "y": 7,
        "explicitMods": ["+93 to maximum Life"],
    }

    assert content_signature_for_item(a) == content_signature_for_item(b)


def test_lineage_key_uses_prior_signature_match_before_position_tie_break() -> None:
    assert (
        lineage_key_from_previous_scan(
            signature="sig-123",
            prior_signature_matches={"sig-123": "sig:existing-lineage"},
            prior_position_matches={"tab-1:4:7:1:1": "sig:position-lineage"},
            position_key="tab-1:4:7:1:1",
        )
        == "sig:existing-lineage"
    )


def test_normalize_stash_prediction_keeps_interval_and_trust_fields() -> None:
    result = normalize_stash_prediction(
        {
            "predictedValue": 42.0,
            "currency": "chaos",
            "confidence": 78.0,
            "interval": {"p10": 35.0, "p90": 55.0},
            "priceRecommendationEligible": True,
            "estimateTrust": "normal",
            "estimateWarning": "fallback used",
            "fallbackReason": "no_model",
        }
    )

    assert result.predicted_price == 42.0
    assert result.price_p10 == 35.0
    assert result.price_p90 == 55.0
    assert result.price_recommendation_eligible is True
    assert result.estimate_trust == "normal"
    assert result.estimate_warning == "fallback used"
    assert result.fallback_reason == "no_model"


def test_price_band_for_delta_pct_uses_absolute_thresholds() -> None:
    assert price_band_for_delta_pct(5.0) == "good"
    assert price_band_for_delta_pct(-12.5) == "mediocre"
    assert price_band_for_delta_pct(26.0) == "bad"


@pytest.mark.parametrize(
    ("currency", "fx_rate", "expected"),
    [
        ("chaos", None, 2.0),
        ("divine orb", 150, 300.0),
        ("exalted orb", None, None),
    ],
)
def test_normalize_chaos_price_handles_common_currency_labels(
    currency: str,
    fx_rate: float | None,
    expected: float | None,
) -> None:
    assert (
        normalize_chaos_price(
            2,
            currency=currency,
            fx_chaos_per_divine=fx_rate,
        )
        == expected
    )


def test_serialize_item_to_clipboard_keeps_name_base_and_mod_lines() -> None:
    item = {
        "name": "Grim Bane",
        "typeLine": "Hubris Circlet",
        "explicitMods": ["+93 to maximum Life"],
    }

    clipboard = serialize_stash_item_to_clipboard(item)

    assert "Grim Bane" in clipboard
    assert "Hubris Circlet" in clipboard
    assert "+93 to maximum Life" in clipboard


def test_fetch_published_scan_id_returns_none_for_empty_payload() -> None:
    client = _StubClickHouse(payload="")

    assert (
        fetch_published_scan_id(
            client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )
        is None
    )


def test_fetch_active_scan_returns_latest_active_row() -> None:
    client = _StubClickHouse(
        payload='{"scan_id":"scan-1","is_active":1,"started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:00:01Z"}\n'
    )

    result = fetch_active_scan(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
    )

    assert result == {
        "scanId": "scan-1",
        "isActive": True,
        "startedAt": "2026-03-21T10:00:00Z",
        "updatedAt": "2026-03-21T10:00:01Z",
    }


def test_fetch_active_valuation_refresh_filters_by_kind_and_source_scan_id() -> None:
    client = _StubClickHouse(
        payload='{"scan_id":"scan-2","is_active":1,"started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:00:01Z"}\n'
    )

    result = fetch_active_valuation_refresh(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-1",
    )

    assert result == {
        "scanId": "scan-2",
        "isActive": True,
        "startedAt": "2026-03-21T10:00:00Z",
        "updatedAt": "2026-03-21T10:00:01Z",
    }
    query = client.queries[0]
    assert "scan_kind = 'valuation_refresh'" in query
    assert "source_scan_id = 'scan-1'" in query


def test_fetch_latest_scan_run_prefers_terminal_rows_on_ties() -> None:
    client = _StubClickHouse(payload="")

    _ = fetch_latest_scan_run(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
    )

    query = client.queries[0]
    assert (
        "ORDER BY updated_at DESC, published_at DESC, completed_at DESC, failed_at DESC"
        in query
    )


def test_fetch_latest_valuation_refresh_run_filters_to_current_source_scan() -> None:
    client = _StubClickHouse(payload="")

    _ = fetch_latest_valuation_refresh_run(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-1",
        scan_id="scan-2",
    )

    query = client.queries[0]
    assert "scan_kind = 'valuation_refresh'" in query
    assert "source_scan_id = 'scan-1'" in query
    assert "AND scan_id = 'scan-2'" in query


def test_fetch_latest_published_valuation_refresh_run_filters_to_current_published_scan() -> None:
    client = _StubClickHouse(payload="")

    _ = fetch_latest_published_valuation_refresh_run(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-2",
    )

    query = client.queries[0]
    assert "scan_kind = 'valuation_refresh'" in query
    assert "AND scan_id = 'scan-2'" in query
    assert "source_scan_id" not in query


def test_fetch_valuation_refresh_status_payload_uses_current_published_scan() -> None:
    client = _SequentialStubClickHouse(
        payloads=[
            '{"scan_id":"scan-2","is_active":1,"started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:00:01Z"}\n',
            '{"scan_id":"scan-2","status":"running","started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:00:01Z","published_at":"","tabs_total":2,"tabs_processed":1,"items_total":5,"items_processed":3,"error_message":""}\n',
        ]
    )

    result = fetch_valuation_refresh_status_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-1",
    )

    assert result["status"] == "running"
    assert result["activeScanId"] == "scan-2"
    assert result["publishedScanId"] == "scan-1"
    assert result["progress"] == {
        "tabsTotal": 2,
        "tabsProcessed": 1,
        "itemsTotal": 5,
        "itemsProcessed": 3,
    }
    assert "scan_kind = 'valuation_refresh'" in client.queries[0]
    assert "source_scan_id = 'scan-1'" in client.queries[0]
    assert "scan_kind = 'valuation_refresh'" in client.queries[1]
    assert "source_scan_id = 'scan-1'" in client.queries[1]


def test_fetch_valuation_refresh_status_payload_recovers_published_refresh_after_restart() -> None:
    client = _SequentialStubClickHouse(
        payloads=[
            '{"scan_id":"scan-2","is_active":0,"started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:10:00Z"}\n',
            "",
            '{"scan_id":"scan-2","status":"published","started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:10:00Z","published_at":"2026-03-21T10:10:00Z","tabs_total":2,"tabs_processed":2,"items_total":5,"items_processed":5,"error_message":""}\n',
        ]
    )

    result = fetch_valuation_refresh_status_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-2",
    )

    assert result["status"] == "published"
    assert result["activeScanId"] is None
    assert result["publishedScanId"] == "scan-2"
    assert result["publishedAt"] == "2026-03-21T10:10:00Z"
    assert "scan_kind = 'valuation_refresh'" in client.queries[0]
    assert "source_scan_id = 'scan-2'" in client.queries[0]
    assert "scan_kind = 'valuation_refresh'" in client.queries[1]
    assert "source_scan_id = 'scan-2'" in client.queries[1]
    assert "scan_kind = 'valuation_refresh'" in client.queries[2]
    assert "AND scan_id = 'scan-2'" in client.queries[2]


def test_fetch_item_history_returns_header_and_entries() -> None:
    payload = "\n".join(
        [
            json.dumps(
                {
                    "lineage_key": "sig:item-1",
                    "item_id": "item-1",
                    "item_name": "Grim Bane",
                    "base_type": "Hubris Circlet",
                    "item_class": "Helmet",
                    "rarity": "rare",
                    "icon_url": "https://web.poecdn.com/item.png",
                    "scan_id": "scan-2",
                    "priced_at": "2026-03-21T11:00:00Z",
                    "listed_price": 40.0,
                    "listed_currency": "chaos",
                    "listed_price_chaos": 40.0,
                    "estimated_price_chaos": 45.0,
                    "price_p10_chaos": 39.0,
                    "price_p90_chaos": 51.0,
                    "price_delta_chaos": -5.0,
                    "price_delta_pct": -11.1111111111,
                    "price_band": "good",
                    "price_band_version": 1,
                    "confidence": 82.0,
                    "estimate_trust": "normal",
                    "estimate_warning": "",
                    "fallback_reason": "",
                }
            )
        ]
    )
    client = _StubClickHouse(payload=payload)

    result = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert result["fingerprint"] == "sig:item-1"
    assert result["item"]["name"] == "Grim Bane"
    assert result["item"]["itemClass"] == "Helmet"
    assert result["history"][0]["scanId"] == "scan-2"
    assert result["history"][0]["interval"] == {"p10": 39.0, "p90": 51.0}
    assert result["history"][0]["priceBand"] == "good"
    assert result["history"][0]["priceEvaluation"] == "well_priced"


def test_fetch_item_history_reads_v2_history_with_90_day_retention() -> None:
    class _V2HistoryClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_item_history_v2" in query:
                return (
                    '{"lineage_key":"sig:item-1","item_id":"item-1","item_name":"Grim Bane","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare","icon_url":"https://web.poecdn.com/item.png","scan_id":"scan-2","priced_at":"2026-03-21T11:00:00Z","listed_price":40.0,"listed_currency":"chaos","listed_price_chaos":40.0,"estimated_price_chaos":45.0,"price_p10_chaos":39.0,"price_p90_chaos":51.0,"price_delta_chaos":-5.0,"price_delta_pct":-11.1111111111,"price_band":"good","price_band_version":1,"confidence":82.0,"estimate_trust":"normal","estimate_warning":"","fallback_reason":""}\n'
                )
            raise AssertionError("legacy fallback should not be used when v2 has rows")

    client = _V2HistoryClickHouse()

    result = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert result["fingerprint"] == "sig:item-1"
    assert result["history"][0]["priceBand"] == "good"
    assert result["history"][0]["priceEvaluation"] == "well_priced"
    assert "priced_at >= now() - INTERVAL 90 DAY" in client.queries[0]
    assert "FROM poe_trade.account_stash_item_history_v2" in client.queries[0]
    assert all(
        "account_stash_item_valuations" not in query for query in client.queries
    )


def test_fetch_item_history_preserves_stored_chaos_values_for_non_computable_currency() -> None:
    payload = "\n".join(
        [
            json.dumps(
                {
                    "lineage_key": "sig:item-1",
                    "item_id": "item-1",
                    "item_name": "Grim Bane",
                    "base_type": "Hubris Circlet",
                    "item_class": "Helmet",
                    "rarity": "rare",
                    "icon_url": "https://web.poecdn.com/item.png",
                    "scan_id": "scan-2",
                    "priced_at": "2026-03-21T11:00:00Z",
                    "listed_price": 2.0,
                    "listed_currency": "exalted orb",
                    "listed_price_chaos": 24.0,
                    "estimated_price_chaos": 24.0,
                    "price_p10_chaos": 22.0,
                    "price_p90_chaos": 26.0,
                    "price_delta_chaos": 0.0,
                    "price_delta_pct": 0.0,
                    "price_band": "good",
                    "price_band_version": 1,
                    "confidence": 82.0,
                    "estimate_trust": "normal",
                    "estimate_warning": "",
                    "fallback_reason": "",
                }
            )
        ]
    )
    client = _StubClickHouse(payload=payload)

    result = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert result["history"][0]["listedPrice"] == 2.0
    assert result["history"][0]["listedPriceChaos"] == 24.0
    assert result["history"][0]["predictedValue"] is None
    assert result["history"][0]["predictedValueChaos"] == 24.0
    assert result["history"][0]["interval"] == {"p10": None, "p90": None}
    assert result["history"][0]["priceDeltaChaos"] == 0.0
    assert result["history"][0]["priceDeltaPercent"] == 0.0
    assert result["history"][0]["priceBand"] == "good"
    assert result["history"][0]["priceEvaluation"] == "well_priced"
    assert result["history"][0]["priceRecommendationEligible"] is True


def test_fetch_item_history_falls_back_to_legacy_valuation_rows() -> None:
    legacy_row = json.dumps(
        {
            "lineage_key": "sig:item-1",
            "item_id": "item-1",
            "item_name": "Grim Bane",
            "item_class": "Helmet",
            "rarity": "rare",
            "icon_url": "https://web.poecdn.com/item.png",
            "scan_id": "scan-2",
            "priced_at": "2026-03-21T11:00:00Z",
            "listed_price": 2.0,
            "currency": "divine orb",
            "predicted_price": 2.0,
            "price_p10": 1.95,
            "price_p90": 2.05,
            "confidence": 82.0,
            "estimate_trust": "normal",
            "estimate_warning": "",
            "fallback_reason": "",
            "payload_json": json.dumps(
                {
                    "typeLine": "Hubris Circlet",
                    "note": "~price 2 divine orb",
                }
            ),
        }
    )
    client = _SequentialStubClickHouse(payloads=["", legacy_row + "\n"])

    result = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert result["history"][0]["listedPriceChaos"] == 400.0
    assert result["history"][0]["predictedValueChaos"] == 400.0
    assert result["history"][0]["predictedValue"] == 2.0
    assert result["history"][0]["interval"] == {"p10": 1.95, "p90": 2.05}
    assert result["item"]["baseType"] == "Hubris Circlet"
    assert result["history"][0]["priceBand"] == "good"
    assert result["history"][0]["priceEvaluation"] == "well_priced"
    assert any("account_stash_item_valuations" in query for query in client.queries)


def test_fetch_item_history_handles_mixed_currency_legacy_rows() -> None:
    legacy_row = json.dumps(
        {
            "lineage_key": "sig:item-1",
            "item_id": "item-1",
            "item_name": "Divine Orb",
            "item_class": "Currency",
            "rarity": "normal",
            "icon_url": "https://web.poecdn.com/item.png",
            "scan_id": "scan-2",
            "priced_at": "2026-03-21T11:00:00Z",
            "listed_price": 2.0,
            "currency": "chaos",
            "predicted_price": 24.0,
            "price_p10": 22.0,
            "price_p90": 26.0,
            "confidence": 82.0,
            "estimate_trust": "normal",
            "estimate_warning": "",
            "fallback_reason": "",
            "payload_json": json.dumps(
                {
                    "typeLine": "Divine Orb",
                    "note": "~price 2 divine orb",
                }
            ),
        }
    )
    client = _SequentialStubClickHouse(payloads=["", legacy_row + "\n"])

    result = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert result["history"][0]["listedPriceChaos"] == 400.0
    assert result["history"][0]["predictedValueChaos"] == 24.0
    assert result["history"][0]["predictedValue"] == 0.12
    assert result["history"][0]["interval"] == {"p10": 0.11, "p90": 0.13}
    assert result["history"][0]["priceBand"] == "bad"
    assert result["history"][0]["priceEvaluation"] == "mispriced"


def test_fetch_item_history_prefers_v2_rows_after_backfill() -> None:
    class _BackfilledClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_item_history_v2" in query:
                return (
                    '{"lineage_key":"sig:item-1","item_id":"item-1","item_name":"Grim Bane","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare","icon_url":"https://web.poecdn.com/item.png","scan_id":"scan-2","priced_at":"2026-03-21T11:00:00Z","listed_price":2.0,"listed_currency":"divine orb","listed_price_chaos":400.0,"estimated_price_chaos":400.0,"price_p10_chaos":380.0,"price_p90_chaos":420.0,"price_delta_chaos":0.0,"price_delta_pct":0.0,"price_band":"good","price_band_version":1,"confidence":82.0,"estimate_trust":"normal","estimate_warning":"","fallback_reason":""}\n'
                )
            raise AssertionError("legacy fallback should not be used after backfill")

    client = _BackfilledClickHouse()

    result = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert result["fingerprint"] == "sig:item-1"
    assert result["history"][0]["listedPrice"] == 2.0
    assert result["history"][0]["listedPriceChaos"] == 400.0
    assert result["history"][0]["predictedValueChaos"] == 400.0
    assert result["history"][0]["priceBand"] == "good"
    assert result["history"][0]["priceBandVersion"] == 1
    assert result["history"][0]["priceEvaluation"] == "well_priced"
    assert len(client.queries) == 1
    assert all(
        "account_stash_item_valuations" not in query for query in client.queries
    )


def test_fetch_item_history_filters_to_90_day_window() -> None:
    client = _StubClickHouse(payload="")

    _ = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert "priced_at >= now() - INTERVAL 90 DAY" in client.queries[0]


def test_fetch_item_history_defaults_to_50_rows() -> None:
    client = _StubClickHouse(payload="")

    _ = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
    )

    assert "ORDER BY priced_at DESC LIMIT 50 FORMAT JSONEachRow" in client.queries[0]


def test_fetch_item_history_explicit_limit_overrides_default() -> None:
    client = _StubClickHouse(payload="")

    _ = fetch_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        lineage_key="sig:item-1",
        limit=12,
    )

    assert "ORDER BY priced_at DESC LIMIT 12 FORMAT JSONEachRow" in client.queries[0]


def test_fetch_published_tabs_maps_real_poe_tab_types_to_frontend_types() -> None:
    client = _SequentialStubClickHouse(
        payloads=[
            '{"scan_id":"scan-1","is_active":0,"started_at":"2026-03-21T09:00:00Z","updated_at":"2026-03-21T09:00:00Z"}\n',
            '{"scan_id":"scan-1"}\n',
            '{"scan_id":"scan-1","status":"published","started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:10:00Z","published_at":"2026-03-21T10:10:00Z","tabs_total":3,"tabs_processed":3,"items_total":3,"items_processed":3,"error_message":""}\n',
            '{"published_at":"2026-03-21T10:10:00Z"}\n',
            "\n".join(
                [
                    '{"tab_id":"tab-c","tab_index":0,"tab_name":"Currency","tab_type":"CurrencyStash"}',
                    '{"tab_id":"tab-f","tab_index":1,"tab_name":"Fragments","tab_type":"FragmentStash"}',
                    '{"tab_id":"tab-q","tab_index":2,"tab_name":"Dump","tab_type":"QuadStash"}',
                ]
            )
            + "\n",
            "\n".join(
                [
                    '{"tab_id":"tab-c","tab_index":0,"lineage_key":"sig:c1","item_id":"c1","item_name":"Chaos Orb","base_type":"Chaos Orb","item_class":"Currency","rarity":"normal","x":0,"y":0,"w":1,"h":1,"listed_price":1,"listed_currency":"chaos","listed_price_chaos":1,"estimated_price_chaos":1,"price_p10_chaos":1,"price_p90_chaos":1,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":100,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/c.png","priced_at":"2026-03-21T10:10:00Z"}',
                    '{"tab_id":"tab-f","tab_index":1,"lineage_key":"sig:f1","item_id":"f1","item_name":"Mortal Grief","base_type":"Mortal Grief","item_class":"Fragment","rarity":"normal","x":7,"y":0,"w":1,"h":1,"listed_price":2,"listed_currency":"chaos","listed_price_chaos":2,"estimated_price_chaos":2,"price_p10_chaos":2,"price_p90_chaos":2,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":100,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/f.png","priced_at":"2026-03-21T10:10:00Z"}',
                    '{"tab_id":"tab-q","tab_index":2,"lineage_key":"sig:q1","item_id":"q1","item_name":"Hubris Circlet","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare","x":20,"y":20,"w":2,"h":2,"listed_price":3,"listed_currency":"chaos","listed_price_chaos":3,"estimated_price_chaos":3,"price_p10_chaos":3,"price_p90_chaos":3,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":100,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/q.png","priced_at":"2026-03-21T10:10:00Z"}',
                ]
            )
            + "\n",
        ]
    )

    result = fetch_published_tabs(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        stale_timeout_seconds=60,
    )

    assert [tab["type"] for tab in result["stashTabs"]] == [
        "currency",
        "fragment",
        "quad",
    ]
    assert result["stashTabs"][0]["items"][0]["priceBand"] == "good"
    assert result["stashTabs"][0]["items"][0]["priceEvaluation"] == "well_priced"
    assert result["stashTabs"][0]["items"][0]["priceDeltaChaos"] == 0.0
    assert any("v_account_stash_latest_scan_items" in query for query in client.queries)


def test_fetch_published_tabs_preserves_stored_chaos_values_for_non_computable_currency() -> None:
    client = _SequentialStubClickHouse(
        payloads=[
            '{"scan_id":"scan-1","is_active":0,"started_at":"2026-03-21T09:00:00Z","updated_at":"2026-03-21T09:00:00Z"}\n',
            '{"scan_id":"scan-1"}\n',
            '{"scan_id":"scan-1","status":"published","started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:10:00Z","published_at":"2026-03-21T10:10:00Z","tabs_total":1,"tabs_processed":1,"items_total":1,"items_processed":1,"error_message":""}\n',
            '{"published_at":"2026-03-21T10:10:00Z"}\n',
            '{"tab_id":"tab-c","tab_index":0,"tab_name":"Currency","tab_type":"CurrencyStash"}\n',
            '{"tab_id":"tab-c","tab_index":0,"lineage_key":"sig:c1","item_id":"c1","item_name":"Divine Orb","base_type":"Divine Orb","item_class":"Currency","rarity":"normal","x":0,"y":0,"w":1,"h":1,"listed_price":2,"listed_currency":"exalted orb","listed_price_chaos":24,"estimated_price_chaos":24,"price_p10_chaos":22,"price_p90_chaos":26,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":100,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/c.png","priced_at":"2026-03-21T10:10:00Z"}\n',
        ]
    )

    result = fetch_published_tabs(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        stale_timeout_seconds=60,
    )

    item = result["stashTabs"][0]["items"][0]
    assert item["listedPrice"] == 2.0
    assert item["currency"] == "exalted orb"
    assert item["listedPriceChaos"] == 24.0
    assert item["estimatedPrice"] is None
    assert item["estimatedPriceChaos"] == 24.0
    assert item["interval"] == {"p10": None, "p90": None}
    assert item["priceDeltaChaos"] == 0.0
    assert item["priceDeltaPercent"] == 0.0
    assert item["priceBand"] == "good"
    assert item["priceEvaluation"] == "well_priced"
    assert item["priceRecommendationEligible"] is True


def test_fetch_published_tabs_ignores_valuation_refresh_scan_status_rows() -> None:
    class _LifecycleKindAwareClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "FROM poe_trade.account_stash_active_scans" in query:
                if "scan_kind = 'stash_scan'" in query:
                    return ""
                return (
                    '{"scan_id":"vr-1","is_active":1,'
                    '"started_at":"2026-03-21T12:01:00Z",'
                    '"updated_at":"2026-03-21T12:02:00Z"}\n'
                )
            if "FROM poe_trade.account_stash_scan_runs" in query:
                if "scan_kind = 'stash_scan'" in query:
                    return ""
                return (
                    '{"scan_id":"vr-1","source_scan_id":"stash-1","status":"running",'
                    '"started_at":"2026-03-21T12:01:00Z",'
                    '"updated_at":"2026-03-21T12:02:00Z","published_at":null,'
                    '"tabs_total":2,"tabs_processed":1,"items_total":5,"items_processed":3,'
                    '"error_message":""}\n'
                )
            if "argMax(scan_id, published_at) AS scan_id" in query:
                return '{"scan_id":"stash-1"}\n'
            if "argMax(published_at, published_at) AS published_at" in query:
                return '{"published_at":"2026-03-21T12:05:00Z"}\n'
            return ""

    client = _LifecycleKindAwareClickHouse()

    result = fetch_published_tabs(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
    )

    assert result["scanId"] == "stash-1"
    assert result["publishedAt"] == "2026-03-21T12:05:00Z"
    assert result["scanStatus"] is None
    assert result["stashTabs"] == []


def test_fetch_published_tabs_falls_back_to_legacy_valuation_rows() -> None:
    client = _SequentialStubClickHouse(
        payloads=[
            '{"scan_id":"scan-1","is_active":0,"started_at":"2026-03-21T09:00:00Z","updated_at":"2026-03-21T09:00:00Z"}\n',
            '{"scan_id":"scan-1"}\n',
            '{"scan_id":"scan-1","status":"published","started_at":"2026-03-21T10:00:00Z","updated_at":"2026-03-21T10:10:00Z","published_at":"2026-03-21T10:10:00Z","tabs_total":1,"tabs_processed":1,"items_total":1,"items_processed":1,"error_message":""}\n',
            '{"published_at":"2026-03-21T10:10:00Z"}\n',
            '{"tab_id":"tab-c","tab_index":0,"tab_name":"Currency","tab_type":"CurrencyStash"}\n',
            "",
            '{"tab_id":"tab-c","tab_index":0,"lineage_key":"sig:c1","item_id":"c1","item_name":"Divine Orb","item_class":"Currency","rarity":"normal","x":0,"y":0,"w":1,"h":1,"listed_price":2,"currency":"divine orb","predicted_price":2,"confidence":100,"price_p10":1.9,"price_p90":2.1,"icon_url":"https://example.invalid/c.png","priced_at":"2026-03-21T10:10:00Z","payload_json":"{\\"typeLine\\": \\"Divine Orb\\", \\"note\\": \\"~price 2 divine orb\\"}"}\n',
        ]
    )

    result = fetch_published_tabs(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        stale_timeout_seconds=60,
    )

    assert result["stashTabs"][0]["items"][0]["priceBand"] == "good"
    assert result["stashTabs"][0]["items"][0]["priceEvaluation"] == "well_priced"
    assert result["stashTabs"][0]["items"][0]["baseType"] == "Divine Orb"
    assert result["stashTabs"][0]["items"][0]["listedPriceChaos"] == 400.0
    assert result["stashTabs"][0]["items"][0]["estimatedPriceChaos"] == 400.0
    assert result["stashTabs"][0]["items"][0]["estimatedPrice"] == 2.0
    assert result["stashTabs"][0]["items"][0]["interval"] == {"p10": 1.9, "p90": 2.1}
    assert any("account_stash_item_valuations" in query for query in client.queries)
