from __future__ import annotations

from collections.abc import Mapping

from poe_trade.api.stash import (
    fetch_stash_tabs,
    stash_item_history_payload,
    stash_status_payload,
)
from poe_trade.db import ClickHouseClient


class _StubClickHouse(ClickHouseClient):
    def __init__(self, responses: dict[str, str]) -> None:
        super().__init__(endpoint="http://clickhouse")
        self._responses = responses
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        self.queries.append(query)
        for key, value in self._responses.items():
            if key in query:
                return value
        return ""


def test_fetch_stash_tabs_empty() -> None:
    client = _StubClickHouse(responses={})
    assert fetch_stash_tabs(client, league="Mirage", realm="pc") == {"stashTabs": []}


def test_fetch_stash_tabs_maps_item_shape_from_published_snapshot() -> None:
    line = (
        '{"tab_id":"1","tab_name":"Trade 1","tab_type":"normal","item_fingerprint":"fp:1",'
        '"item_id":"item-1","item_name":"Chaos Orb","item_class":"Currency","rarity":"normal",'
        '"x":0,"y":0,"w":1,"h":1,"listed_price":10.0,"currency":"chaos","icon_url":"https://web.poecdn.com/test.png",'
        '"predicted_price":12.0,"confidence":80.0,"price_p10":9.0,"price_p90":14.0,"priced_at":"2026-03-20T10:00:00Z","scan_id":"scan-1"}'
    )
    client = _StubClickHouse(
        responses={"FROM poe_trade.account_stash_active_scans": f"{line}\n"}
    )

    result = fetch_stash_tabs(
        client,
        league="Mirage",
        realm="pc",
        account_name="qa-exile",
    )
    assert result["valuationScanId"] == "scan-1"
    tab = result["stashTabs"][0]
    item = tab["items"][0]
    assert tab["id"] == "1"
    assert item["id"] == "fp:1"
    assert item["itemFingerprint"] == "fp:1"
    assert item["estimatedPrice"] == 12.0
    assert item["priceP10"] == 9.0
    assert item["priceP90"] == 14.0


def test_fetch_stash_tabs_query_is_account_scoped() -> None:
    client = _StubClickHouse(responses={})
    _ = fetch_stash_tabs(client, league="Mirage", realm="pc", account_name="qa-exile")
    assert len(client.queries) == 1
    assert "active.account_name = 'qa-exile'" in client.queries[0]


def test_stash_status_query_is_account_scoped() -> None:
    client = _StubClickHouse(
        responses={
            "LEFT JOIN poe_trade.account_stash_scan_items": '{"scan_id":"scan-1","published_at":"2026-03-20T10:00:00Z","tabs":1,"items":2}\n',
            "FROM poe_trade.account_stash_valuation_runs": '{"scan_id":"scan-2","status":"running","tabs_total":10,"tabs_processed":3,"items_total":100,"items_processed":45}\n',
        }
    )
    _ = stash_status_payload(
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
    assert len(client.queries) == 2
    assert "qa-exile" in client.queries[0]
    assert "qa-exile" in client.queries[1]


def test_stash_status_connected_empty_when_scoped_rows_missing() -> None:
    client = _StubClickHouse(responses={})
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
    assert payload["valuation"]["status"] == "idle"


def test_stash_status_connected_populated_when_scoped_rows_exist() -> None:
    client = _StubClickHouse(
        responses={
            "LEFT JOIN poe_trade.account_stash_scan_items": '{"scan_id":"scan-1","published_at":"2026-03-20T10:00:00Z","tabs":2,"items":5}\n',
            "FROM poe_trade.account_stash_valuation_runs": '{"scan_id":"scan-2","status":"running","tabs_total":10,"tabs_processed":3,"items_total":100,"items_processed":45}\n',
        }
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
    assert payload["itemCount"] == 5
    assert payload["valuation"]["status"] == "running"
    assert payload["valuation"]["lastSuccessfulScanId"] == "scan-1"


def test_stash_item_history_payload_returns_ordered_band_points() -> None:
    client = _StubClickHouse(
        responses={
            "FROM poe_trade.account_stash_item_valuations": (
                '{"scan_id":"scan-1","predicted_price":10.0,"confidence":70.0,"price_p10":8.0,"price_p90":12.0,"priced_at":"2026-03-20T10:00:00Z"}\n'
                '{"scan_id":"scan-2","predicted_price":12.0,"confidence":75.0,"price_p10":9.0,"price_p90":14.0,"priced_at":"2026-03-20T11:00:00Z"}\n'
            )
        }
    )
    payload = stash_item_history_payload(
        client,
        league="Mirage",
        realm="pc",
        account_name="qa-exile",
        item_fingerprint="fp:1",
    )
    assert payload["itemFingerprint"] == "fp:1"
    assert len(payload["history"]) == 2
    assert (
        payload["history"][0]["priceP10"]
        <= payload["history"][0]["predictedPrice"]
        <= payload["history"][0]["priceP90"]
    )


def test_stash_status_disconnected_for_disconnected_session() -> None:
    client = _StubClickHouse(responses={})
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


def test_stash_status_feature_unavailable_explains_flag() -> None:
    client = _StubClickHouse(responses={})
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
