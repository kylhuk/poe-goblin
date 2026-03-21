from __future__ import annotations

from collections.abc import Mapping

import pytest

import poe_trade.api.stash as stash_api
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
        lambda _client, *, account_name, league, realm: {
            "scanId": None,
            "publishedAt": None,
            "isStale": False,
            "scanStatus": None,
            "stashTabs": [],
        },
    )

    assert fetch_stash_tabs(client, league="Mirage", realm="pc", account_name="qa-exile") == {
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
        lambda _client, *, account_name, league, realm: (
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
        lambda _client, *, account_name, league, realm: {
            "scanId": "scan-1",
            "publishedAt": "2026-03-21T12:00:00Z",
            "isStale": False,
            "scanStatus": None,
            "stashTabs": [
                {"id": "tab-2", "name": "Currency", "type": "currency", "items": [{"id": "item-1"}]},
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


def test_fetch_stash_item_history_returns_header_and_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClickHouse()
    monkeypatch.setattr(
        stash_api,
        "fetch_item_history",
        lambda _client, *, account_name, league, realm, lineage_key, limit=20: {
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
