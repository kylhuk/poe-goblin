from __future__ import annotations

from collections.abc import Mapping

import pytest

import poe_trade.api.stash as stash_api
import poe_trade.stash_scan as stash_scan
from poe_trade.api.stash import (
    fetch_stash_item_history,
    fetch_stash_tabs,
    stash_scan_status_payload,
    stash_status_payload,
)
from poe_trade.db import ClickHouseClient


class _StubClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        self.queries.append(query)
        return ""


def test_fetch_stash_tabs_returns_empty_metadata_when_no_published_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    monkeypatch.setattr(
        stash_api,
        "fetch_published_tabs",
        lambda _client, *, account_name, league, realm, stale_timeout_seconds=0: {
            "scanId": None,
            "publishedAt": None,
            "isStale": False,
            "scanStatus": None,
            "stashTabs": [],
        },
    )

    assert fetch_stash_tabs(
        client, league="Mirage", realm="pc", account_name="qa-exile"
    ) == {
        "scanId": None,
        "publishedAt": None,
        "isStale": False,
        "scanStatus": None,
        "stashTabs": [],
    }


def test_fetch_stash_tabs_delegates_account_scope_to_published_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        stash_api,
        "fetch_published_tabs",
        lambda _client, *, account_name, league, realm, stale_timeout_seconds=0: (
            captured.update(
                {
                    "account_name": account_name,
                    "league": league,
                    "realm": realm,
                }
            )
            or {
                "scanId": "scan-1",
                "publishedAt": "2026-03-21T12:00:00Z",
                "isStale": False,
                "scanStatus": None,
                "stashTabs": [],
            }
        ),
    )

    _ = fetch_stash_tabs(client, league="Mirage", realm="pc", account_name="qa-exile")

    assert captured == {
        "account_name": "qa-exile",
        "league": "Mirage",
        "realm": "pc",
    }


def test_published_tabs_return_v2_price_fields_for_every_item() -> None:
    class _V2ClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_active_scans" in query:
                return ""
            if "account_stash_published_scans" in query:
                return '{"scan_id":"scan-1"}\n'
            if "account_stash_scan_runs" in query:
                return '{"scan_id":"scan-1","status":"published","started_at":"2026-03-21T12:00:00Z","updated_at":"2026-03-21T12:05:00Z","published_at":"2026-03-21T12:05:00Z","tabs_total":1,"tabs_processed":1,"items_total":2,"items_processed":2,"error_message":""}\n'
            if "account_stash_scan_tabs" in query:
                return '\n'.join(
                    [
                        '{"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency"}',
                    ]
                ) + '\n'
            if "v_account_stash_latest_scan_items" in query:
                return '\n'.join(
                    [
                        '{"tab_id":"tab-1","tab_index":0,"lineage_key":"sig:item-1","item_id":"item-1","item_name":"Grim Bane","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare","x":0,"y":0,"w":2,"h":2,"listed_price":40,"listed_currency":"chaos","listed_price_chaos":40,"estimated_price_chaos":45,"price_p10_chaos":39,"price_p90_chaos":51,"price_delta_chaos":-5,"price_delta_pct":-11.1111111111,"price_band":"good","price_band_version":1,"confidence":82,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/icon-1.png","priced_at":"2026-03-21T12:00:00Z"}',
                        '{"tab_id":"tab-1","tab_index":0,"lineage_key":"sig:item-2","item_id":"item-2","item_name":"Vaal Regalia","base_type":"Vaal Regalia","item_class":"Body Armour","rarity":"rare","x":2,"y":0,"w":2,"h":2,"listed_price":55,"listed_currency":"chaos","listed_price_chaos":55,"estimated_price_chaos":44,"price_p10_chaos":40,"price_p90_chaos":48,"price_delta_chaos":11,"price_delta_pct":25,"price_band":"mediocre","price_band_version":1,"confidence":73,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/icon-2.png","priced_at":"2026-03-21T12:00:00Z"}',
                    ]
                ) + '\n'
            if "account_stash_item_valuations" in query:
                return ""
            if "account_stash_published_scans" in query:
                return '{"published_at":"2026-03-21T12:05:00Z"}\n'
            return ""

    client = _V2ClickHouse()

    payload = fetch_stash_tabs(
        client,
        league="Mirage",
        realm="pc",
        account_name="qa-exile",
    )

    assert payload["scanId"] == "scan-1"
    assert payload["stashTabs"][0]["items"][0]["priceBand"] == "good"
    assert payload["stashTabs"][0]["items"][0]["priceEvaluation"] == "well_priced"
    assert payload["stashTabs"][0]["items"][1]["priceBand"] == "mediocre"
    assert payload["stashTabs"][0]["items"][1]["priceEvaluation"] == "could_be_better"
    assert all(
        item.get("priceBand") and item.get("priceEvaluation")
        for item in payload["stashTabs"][0]["items"]
    )
    assert any("v_account_stash_latest_scan_items" in query for query in client.queries)
    assert not any(
        "account_stash_item_valuations" in query and "v_account_stash_latest_scan_items" not in query
        for query in client.queries
    )


def test_fetch_stash_tabs_returns_every_published_tab_and_item_for_latest_scan() -> None:
    class _CompleteV2ClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_active_scans" in query:
                return ""
            if "account_stash_published_scans" in query:
                return '{"scan_id":"scan-2"}\n'
            if "account_stash_scan_runs" in query:
                return '{"scan_id":"scan-2","status":"published","started_at":"2026-03-21T12:00:00Z","updated_at":"2026-03-21T12:05:00Z","published_at":"2026-03-21T12:05:00Z","tabs_total":2,"tabs_processed":2,"items_total":3,"items_processed":3,"error_message":""}\n'
            if "account_stash_scan_tabs" in query:
                return "\n".join(
                    [
                        '{"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency"}',
                        '{"tab_id":"tab-2","tab_index":1,"tab_name":"Dump","tab_type":"quad"}',
                    ]
                ) + "\n"
            if "v_account_stash_latest_scan_items" in query:
                return "\n".join(
                    [
                        '{"tab_id":"tab-1","tab_index":0,"lineage_key":"sig:item-1","item_id":"item-1","item_name":"Chaos Orb","base_type":"Chaos Orb","item_class":"Currency","rarity":"normal","x":0,"y":0,"w":1,"h":1,"listed_price":1,"listed_currency":"chaos","listed_price_chaos":1,"estimated_price_chaos":1,"price_p10_chaos":1,"price_p90_chaos":1,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":100,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/c1.png","priced_at":"2026-03-21T12:00:00Z"}',
                        '{"tab_id":"tab-1","tab_index":0,"lineage_key":"sig:item-2","item_id":"item-2","item_name":"Divine Orb","base_type":"Divine Orb","item_class":"Currency","rarity":"normal","x":1,"y":0,"w":1,"h":1,"listed_price":2,"listed_currency":"chaos","listed_price_chaos":2,"estimated_price_chaos":2,"price_p10_chaos":2,"price_p90_chaos":2,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":100,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/c2.png","priced_at":"2026-03-21T12:00:00Z"}',
                        '{"tab_id":"tab-2","tab_index":1,"lineage_key":"sig:item-3","item_id":"item-3","item_name":"Grim Bane","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare","x":4,"y":6,"w":2,"h":2,"listed_price":40,"listed_currency":"chaos","listed_price_chaos":40,"estimated_price_chaos":40,"price_p10_chaos":38,"price_p90_chaos":42,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":82,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/h1.png","priced_at":"2026-03-21T12:00:00Z"}',
                    ]
                ) + "\n"
            if "account_stash_item_valuations" in query:
                return ""
            return ""

    client = _CompleteV2ClickHouse()

    payload = fetch_stash_tabs(
        client,
        league="Mirage",
        realm="pc",
        account_name="qa-exile",
    )

    assert payload["scanId"] == "scan-2"
    assert [tab["id"] for tab in payload["stashTabs"]] == ["tab-1", "tab-2"]
    assert [item["id"] for item in payload["stashTabs"][0]["items"]] == ["item-1", "item-2"]
    assert [item["id"] for item in payload["stashTabs"][1]["items"]] == ["item-3"]
    assert sum(len(tab["items"]) for tab in payload["stashTabs"]) == 3
    assert payload["stashTabs"][1]["items"][0]["name"] == "Grim Bane"
    assert any("v_account_stash_latest_scan_items" in query for query in client.queries)
    assert not any(
        "account_stash_item_valuations" in query and "v_account_stash_latest_scan_items" not in query
        for query in client.queries
    )


def test_fetch_stash_tabs_prefers_v2_latest_scan_items_for_latest_published_scan() -> None:
    class _V2LatestScanClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_active_scans" in query:
                return ""
            if "account_stash_published_scans" in query:
                return '{"scan_id":"scan-1"}\n'
            if "account_stash_scan_runs" in query:
                return '{"scan_id":"scan-1","status":"published","started_at":"2026-03-21T12:00:00Z","updated_at":"2026-03-21T12:05:00Z","published_at":"2026-03-21T12:05:00Z","tabs_total":1,"tabs_processed":1,"items_total":2,"items_processed":2,"error_message":""}\n'
            if "account_stash_scan_tabs" in query:
                return (
                    '{"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency"}\n'
                )
            if "v_account_stash_latest_scan_items" in query:
                return (
                    '{"tab_id":"tab-1","tab_index":0,"lineage_key":"sig:item-1","item_id":"item-1","item_name":"Grim Bane","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare","x":0,"y":0,"w":2,"h":2,"listed_price":40,"listed_currency":"chaos","listed_price_chaos":40,"estimated_price_chaos":45,"price_p10_chaos":39,"price_p90_chaos":51,"price_delta_chaos":-5,"price_delta_pct":-11.1111111111,"price_band":"good","price_band_version":1,"confidence":82,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/icon-1.png","priced_at":"2026-03-21T12:00:00Z"}\n'
                )
            if "account_stash_item_valuations" in query:
                return ""
            return ""

    client = _V2LatestScanClickHouse()

    payload = fetch_stash_tabs(
        client,
        league="Mirage",
        realm="pc",
        account_name="qa-exile",
    )

    item = payload["stashTabs"][0]["items"][0]
    assert item["priceBand"] == "good"
    assert item["priceEvaluation"] == "well_priced"
    assert item["priceBandVersion"] == 1
    assert item["estimatedPriceConfidence"] == 82.0
    assert item["estimateTrust"] == "normal"
    assert item["estimateWarning"] == ""
    assert item["fallbackReason"] == ""
    assert any("v_account_stash_latest_scan_items" in query for query in client.queries)
    assert not any(
        "account_stash_item_valuations" in query and "v_account_stash_latest_scan_items" not in query
        for query in client.queries
    )


def test_published_tabs_preserve_stored_chaos_values_for_non_computable_currency() -> None:
    class _V2ClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_active_scans" in query:
                return ""
            if "account_stash_published_scans" in query:
                return '{"scan_id":"scan-1"}\n'
            if "account_stash_scan_runs" in query:
                return '{"scan_id":"scan-1","status":"published","started_at":"2026-03-21T12:00:00Z","updated_at":"2026-03-21T12:05:00Z","published_at":"2026-03-21T12:05:00Z","tabs_total":1,"tabs_processed":1,"items_total":1,"items_processed":1,"error_message":""}\n'
            if "account_stash_scan_tabs" in query:
                return '{"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency"}\n'
            if "v_account_stash_latest_scan_items" in query:
                return '{"tab_id":"tab-1","tab_index":0,"lineage_key":"sig:item-1","item_id":"item-1","item_name":"Grim Bane","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare","x":0,"y":0,"w":2,"h":2,"listed_price":2,"listed_currency":"exalted orb","listed_price_chaos":24,"estimated_price_chaos":24,"price_p10_chaos":22,"price_p90_chaos":26,"price_delta_chaos":0,"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":82,"estimate_trust":"normal","estimate_warning":"","fallback_reason":"","icon_url":"https://example.invalid/icon-1.png","priced_at":"2026-03-21T12:00:00Z"}\n'
            if "account_stash_item_valuations" in query:
                return ""
            if "account_stash_published_scans" in query:
                return '{"published_at":"2026-03-21T12:05:00Z"}\n'
            return ""

    client = _V2ClickHouse()

    payload = fetch_stash_tabs(
        client,
        league="Mirage",
        realm="pc",
        account_name="qa-exile",
    )

    item = payload["stashTabs"][0]["items"][0]
    assert item["listedPrice"] == 2.0
    assert item["currency"] == "exalted orb"
    assert item["listedPriceChaos"] == 24.0
    assert item["estimatedPrice"] is None
    assert item["estimatedPriceChaos"] == 24.0
    assert item["priceBand"] == "good"
    assert item["priceEvaluation"] == "well_priced"
    assert item["priceRecommendationEligible"] is True
    assert any("v_account_stash_latest_scan_items" in query for query in client.queries)


def test_stash_status_reconciles_stale_running_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    captured: dict[str, object] = {}

    def _published(_client, *, account_name, league, realm, stale_timeout_seconds=0):
        captured["stale_timeout_seconds"] = stale_timeout_seconds
        return {
            "scanId": "scan-1",
            "publishedAt": "2026-03-21T12:00:00Z",
            "isStale": False,
            "scanStatus": {
                "scanId": "scan-1",
                "status": "failed",
                "startedAt": "2026-03-21T11:55:00Z",
                "updatedAt": "2026-03-21T12:05:00Z",
                "publishedAt": None,
                "progress": {
                    "tabsTotal": 19,
                    "tabsProcessed": 6,
                    "itemsTotal": 543,
                    "itemsProcessed": 543,
                },
                "error": "stale active scan timed out",
            },
            "stashTabs": [
                {"id": "tab-1", "name": "Currency", "type": "currency", "items": []}
            ],
        }

    monkeypatch.setattr(
        stash_api,
        "fetch_published_tabs",
        _published,
    )

    payload = stash_status_payload(
        client,
        league="Mirage",
        realm="pc",
        stale_timeout_seconds=120,
        enable_account_stash=True,
        session={
            "status": "connected",
            "account_name": "qa-exile",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )

    assert captured["stale_timeout_seconds"] == 120
    assert payload["scanStatus"]["status"] == "failed"
    assert payload["status"] == "connected_populated"


def test_stash_status_connected_empty_when_no_published_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    monkeypatch.setattr(
        stash_api,
        "fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: None,
    )
    monkeypatch.setattr(
        stash_api,
        "fetch_active_scan",
        lambda _client, *, account_name, league, realm: None,
    )

    payload = stash_status_payload(
        client,
        league="Mirage",
        realm="pc",
        enable_account_stash=True,
        session={
            "status": "connected",
            "account_name": "qa-exile",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )

    assert payload["status"] == "connected_empty"
    assert payload["connected"] is True
    assert payload["tabCount"] == 0
    assert payload["itemCount"] == 0
    assert payload["publishedScanId"] is None


def test_stash_status_connected_populated_when_published_scan_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    monkeypatch.setattr(
        stash_api,
        "fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        stash_api,
        "fetch_active_scan",
        lambda _client, *, account_name, league, realm: None,
    )
    monkeypatch.setattr(
        stash_api,
        "fetch_published_tabs",
        lambda _client, *, account_name, league, realm, stale_timeout_seconds=0: {
            "scanId": "scan-1",
            "publishedAt": "2026-03-21T12:00:00Z",
            "isStale": False,
            "scanStatus": None,
            "stashTabs": [
                {
                    "id": "tab-2",
                    "name": "Currency",
                    "type": "currency",
                    "items": [{"id": "item-1"}],
                },
                {"id": "tab-9", "name": "Dump", "type": "quad", "items": []},
            ],
        },
    )

    payload = stash_status_payload(
        client,
        league="Mirage",
        realm="pc",
        enable_account_stash=True,
        session={
            "status": "connected",
            "account_name": "qa-exile",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )

    assert payload["status"] == "connected_populated"
    assert payload["connected"] is True
    assert payload["tabCount"] == 2
    assert payload["itemCount"] == 1
    assert payload["publishedScanId"] == "scan-1"
    assert payload["publishedAt"] == "2026-03-21T12:00:00Z"


def test_stash_scan_status_reports_running_progress_and_current_published_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    monkeypatch.setattr(
        stash_api,
        "fetch_active_scan",
        lambda _client, *, account_name, league, realm, stale_timeout_seconds=0: {
            "scanId": "scan-2",
            "isActive": True,
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:02:00Z",
        },
    )
    monkeypatch.setattr(
        stash_api,
        "fetch_latest_scan_run",
        lambda _client, *, account_name, league, realm: {
            "scanId": "scan-2",
            "status": "running",
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:02:00Z",
            "publishedAt": None,
            "progress": {
                "tabsTotal": 8,
                "tabsProcessed": 3,
                "itemsTotal": 120,
                "itemsProcessed": 44,
            },
            "error": None,
        },
    )
    monkeypatch.setattr(
        stash_api,
        "fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )

    payload = stash_scan_status_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
    )

    assert payload == {
        "status": "running",
        "activeScanId": "scan-2",
        "publishedScanId": "scan-1",
        "startedAt": "2026-03-21T12:01:00Z",
        "updatedAt": "2026-03-21T12:02:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 8,
            "tabsProcessed": 3,
            "itemsTotal": 120,
            "itemsProcessed": 44,
        },
        "error": None,
    }


def test_stash_scan_status_uses_reconciled_latest_run_after_active_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    active_calls = {"count": 0}

    def _active(_client, *, account_name, league, realm, stale_timeout_seconds=0):
        active_calls["count"] += 1
        return {
            "scanId": "scan-2",
            "isActive": False,
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:05:00Z",
        }

    def _latest(_client, *, account_name, league, realm):
        if active_calls["count"] == 0:
            return {
                "scanId": "scan-2",
                "status": "running",
                "startedAt": "2026-03-21T12:01:00Z",
                "updatedAt": "2026-03-21T12:02:00Z",
                "publishedAt": None,
                "progress": {
                    "tabsTotal": 8,
                    "tabsProcessed": 3,
                    "itemsTotal": 120,
                    "itemsProcessed": 44,
                },
                "error": None,
            }
        return {
            "scanId": "scan-2",
            "status": "failed",
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:05:00Z",
            "publishedAt": None,
            "progress": {
                "tabsTotal": 8,
                "tabsProcessed": 3,
                "itemsTotal": 120,
                "itemsProcessed": 44,
            },
            "error": "stale active scan timed out",
        }

    monkeypatch.setattr(stash_api, "fetch_active_scan", _active)
    monkeypatch.setattr(stash_api, "fetch_latest_scan_run", _latest)
    monkeypatch.setattr(
        stash_api,
        "fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: None,
    )

    payload = stash_scan_status_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        stale_timeout_seconds=60,
    )

    assert payload["status"] == "failed"
    assert payload["activeScanId"] is None
    assert payload["updatedAt"] == "2026-03-21T12:05:00Z"
    assert payload["error"] == "stale active scan timed out"


def test_stash_scan_status_ignores_valuation_refresh_rows() -> None:
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
            if "FROM poe_trade.account_stash_published_scans" in query:
                return '{"scan_id":"stash-1"}\n'
            return ""

    client = _LifecycleKindAwareClickHouse()

    payload = stash_scan_status_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
    )

    assert payload == {
        "status": "idle",
        "activeScanId": None,
        "publishedScanId": "stash-1",
        "startedAt": None,
        "updatedAt": None,
        "publishedAt": None,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }


def test_fetch_stash_item_history_returns_header_and_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    monkeypatch.setattr(
        stash_api,
        "fetch_item_history",
        lambda _client, *, account_name, league, realm, lineage_key, limit=None: {
            "fingerprint": lineage_key,
            "item": {
                "name": "Grim Bane",
                "itemClass": "Helmet",
                "rarity": "rare",
                "iconUrl": "https://web.poecdn.com/item.png",
            },
            "history": [
                {
                    "scanId": "scan-2",
                    "pricedAt": "2026-03-21T12:00:00Z",
                    "predictedValue": 45.0,
                    "listedPrice": 40.0,
                    "currency": "chaos",
                    "confidence": 82.0,
                    "interval": {"p10": 39.0, "p90": 51.0},
                    "priceRecommendationEligible": True,
                    "estimateTrust": "normal",
                    "estimateWarning": "",
                    "fallbackReason": "",
                }
            ],
        },
    )

    payload = fetch_stash_item_history(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        fingerprint="sig:item-1",
    )

    assert payload["item"]["name"] == "Grim Bane"
    assert payload["history"][0]["interval"] == {"p10": 39.0, "p90": 51.0}


def test_fetch_active_scan_reconciles_stale_rows() -> None:
    class _ReconcileStubClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://clickhouse")
            self.queries: list[str] = []

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            self.queries.append(query)
            if "FROM poe_trade.account_stash_active_scans" in query:
                return '{"scan_id":"scan-1","is_active":1,"started_at":"1970-01-01 00:00:00","updated_at":"1970-01-01 00:00:00"}\n'
            if "FROM poe_trade.account_stash_scan_runs" in query:
                return '{"scan_id":"scan-1","status":"running","started_at":"1970-01-01 00:00:00","updated_at":"1970-01-01 00:00:00","published_at":null,"tabs_total":8,"tabs_processed":3,"items_total":120,"items_processed":44,"error_message":""}\n'
            return ""

    client = _ReconcileStubClickHouse()

    result = stash_scan.fetch_active_scan(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        stale_timeout_seconds=60,
    )

    assert result is not None
    assert result["isActive"] is False
    assert any(
        "INSERT INTO poe_trade.account_stash_active_scans" in q for q in client.queries
    )
    assert any(
        "INSERT INTO poe_trade.account_stash_scan_runs" in q for q in client.queries
    )


def test_stash_status_disconnected_for_disconnected_session() -> None:
    client = _StubClickHouse()

    payload = stash_status_payload(
        client,
        league="Mirage",
        realm="pc",
        enable_account_stash=True,
        session={
            "status": "disconnected",
            "account_name": "qa-exile",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )

    assert payload["status"] == "disconnected"
    assert payload["connected"] is False


def test_stash_status_session_expired_for_expired_session() -> None:
    client = _StubClickHouse()

    payload = stash_status_payload(
        client,
        league="Mirage",
        realm="pc",
        enable_account_stash=True,
        session={
            "status": "session_expired",
            "account_name": "qa-exile",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )

    assert payload["status"] == "session_expired"
    assert payload["connected"] is False


def test_stash_status_feature_unavailable_explains_flag() -> None:
    client = _StubClickHouse()

    payload = stash_status_payload(
        client,
        league="Mirage",
        realm="pc",
        enable_account_stash=False,
        session=None,
    )

    assert payload["status"] == "feature_unavailable"
    assert payload["connected"] is False
    assert payload["reason"] == "set POE_ENABLE_ACCOUNT_STASH=true to enable stash APIs"
    assert payload["featureFlag"] == "POE_ENABLE_ACCOUNT_STASH"
