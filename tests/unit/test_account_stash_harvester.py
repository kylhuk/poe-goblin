from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from poe_trade.db import ClickHouseClient
from poe_trade.ingestion.account_stash_harvester import AccountStashHarvester
from poe_trade.ingestion.account_stash_harvester import parse_listed_price
from poe_trade.ingestion.account_stash_harvester import run_persisted_valuation_refresh
from poe_trade.ingestion.poe_client import PoeClient
from poe_trade.ingestion.rate_limit import RateLimitPolicy
from poe_trade.ingestion.status import StatusReporter


class _FakePoeClient(PoeClient):
    def __init__(self) -> None:
        super().__init__(
            base_url="http://poe.invalid",
            policy=RateLimitPolicy(0, 0.0, 0.0, 0.0),
            user_agent="ua",
            timeout=1.0,
        )
        self.bearer_token: str | None = None

    def set_bearer_token(self, token: str | None) -> None:
        self.bearer_token = token

    def request(
        self,
        method: str,
        path: str,
        params: Mapping[str, str] | None = None,
        data: object | None = None,
        headers: Mapping[str, str] | None = None,
    ):
        del method, path, data, headers
        params = dict(params or {})
        if params.get("tabs") == "1":
            return {
                "tabs": [{"id": "tab-1", "i": 0, "n": "Currency", "type": "currency"}]
            }
        return {
            "stash": {
                "id": str(params.get("tabIndex") or "tab-1"),
                "items": [
                    {
                        "id": "item-1",
                        "name": "Mirror Shard",
                        "typeLine": "Mirror Shard",
                        "frameType": 0,
                        "itemClass": "Currency",
                        "icon": "https://example.invalid/icon.png",
                        "x": 1,
                        "y": 2,
                        "w": 1,
                        "h": 1,
                        "note": "~price 3 chaos",
                    }
                ],
            }
        }


class _FailingPoeClient(_FakePoeClient):
    def __init__(self) -> None:
        super().__init__()
        self.request_count = 0

    def request(
        self,
        method: str,
        path: str,
        params: Mapping[str, str] | None = None,
        data: object | None = None,
        headers: Mapping[str, str] | None = None,
    ):
        self.request_count += 1
        if self.request_count >= 2:
            raise RuntimeError("upstream unavailable")
        return super().request(method, path, params=params, data=data, headers=headers)


class _UnsupportedCurrencyPoeClient(_FakePoeClient):
    def request(
        self,
        method: str,
        path: str,
        params: Mapping[str, str] | None = None,
        data: object | None = None,
        headers: Mapping[str, str] | None = None,
    ):
        del method, path, data, headers
        params = dict(params or {})
        if params.get("tabs") == "1":
            return {
                "tabs": [{"id": "tab-1", "i": 0, "n": "Currency", "type": "currency"}]
            }
        return {
            "stash": {
                "id": str(params.get("tabIndex") or "tab-1"),
                "items": [
                    {
                        "id": "item-1",
                        "name": "Mirror Shard",
                        "typeLine": "Mirror Shard",
                        "frameType": 0,
                        "itemClass": "Currency",
                        "icon": "https://example.invalid/icon.png",
                        "x": 1,
                        "y": 2,
                        "w": 1,
                        "h": 1,
                        "note": "~price 3 mystery",
                    }
                ],
            }
        }


class _FakeClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        del settings
        self.queries.append(query)
        return ""


def _published_scan_run_row(
    *,
    scan_id: str = "scan-1",
    source_scan_id: str = "",
    tabs_total: int = 1,
    items_total: int = 1,
) -> str:
    return (
        "{"
        f'"scan_id":"{scan_id}",'
        f'"source_scan_id":"{source_scan_id}",'
        '"status":"published",'
        '"started_at":"2026-03-21T12:00:00Z",'
        '"updated_at":"2026-03-21T12:05:00Z",'
        '"published_at":"2026-03-21T12:05:00Z",'
        f'"tabs_total":{tabs_total},'
        '"tabs_processed":1,'
        f'"items_total":{items_total},'
        '"items_processed":1,'
        '"error_message":""'
        "}\n"
    )


class _PersistedRefreshClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        del settings
        self.queries.append(query)
        if "FROM poe_trade.account_stash_scan_runs" in query:
            return _published_scan_run_row()
        if "account_stash_scan_tabs" in query:
            return (
                '{"scan_id":"scan-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"captured_at":"2026-03-21T12:00:00Z","tab_meta_json":"{}","payload_json":"{}"}\n'
            )
        if "account_stash_scan_items_v2" in query:
            return (
                '{"scan_id":"scan-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"lineage_key":"sig:item-1","content_signature":"sig-1","item_position_key":"tab-1:1:2:1:1",'
                '"item_id":"item-1","item_name":"Hubris Circlet","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare",'
                '"x":1,"y":2,"w":1,"h":1,"listed_price":2,"listed_currency":"exalted orb","listed_price_chaos":24,'
                '"estimated_price_chaos":24,"price_p10_chaos":22,"price_p90_chaos":26,"price_delta_chaos":0,'
                '"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":82,"estimate_trust":"normal",'
                '"estimate_warning":"","fallback_reason":"","explicit_mods_json":"[]","icon_url":"https://example.invalid/icon.png",'
                '"priced_at":"2026-03-21T12:00:00Z","payload_json":"{\\"id\\":\\"item-1\\",\\"name\\":\\"Grim Bane\\",\\"typeLine\\":\\"Hubris Circlet\\",\\"frameType\\":2,\\"itemClass\\":\\"Helmet\\",\\"icon\\":\\"https://example.invalid/icon.png\\",\\"x\\":1,\\"y\\":2,\\"w\\":1,\\"h\\":1,\\"note\\":\\"~price 2 exalted orb\\",\\"explicitMods\\":[\\"+93 to maximum Life\\"]}"}\n'
            )
        if "account_stash_item_valuations" in query:
            return ""
        if "account_stash_published_scans" in query:
            return '{"published_at":"2026-03-21T12:05:00Z"}\n'
        return ""


class _MixedCurrencyPersistedRefreshClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        del settings
        self.queries.append(query)
        if "FROM poe_trade.account_stash_scan_runs" in query:
            return _published_scan_run_row()
        if "account_stash_scan_tabs" in query:
            return (
                '{"scan_id":"scan-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"captured_at":"2026-03-21T12:00:00Z","tab_meta_json":"{}","payload_json":"{}"}\n'
            )
        if "account_stash_scan_items_v2" in query:
            return (
                '{"scan_id":"scan-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"lineage_key":"sig:item-1","content_signature":"sig-1","item_position_key":"tab-1:1:2:1:1",'
                '"item_id":"item-1","item_name":"Divine Orb","base_type":"Divine Orb","item_class":"Currency","rarity":"normal",'
                '"x":1,"y":2,"w":1,"h":1,"listed_price":2,"listed_currency":"divine orb","listed_price_chaos":400,'
                '"estimated_price_chaos":24,"price_p10_chaos":22,"price_p90_chaos":26,"price_delta_chaos":376,'
                '"price_delta_pct":1566.6666666667,"price_band":"bad","price_band_version":1,"confidence":82,"estimate_trust":"normal",'
                '"estimate_warning":"","fallback_reason":"","explicit_mods_json":"[]","icon_url":"https://example.invalid/icon.png",'
                '"priced_at":"2026-03-21T12:00:00Z","payload_json":"{\\"id\\":\\"item-1\\",\\"name\\":\\"Divine Orb\\",\\"typeLine\\":\\"Divine Orb\\",\\"frameType\\":0,\\"itemClass\\":\\"Currency\\",\\"icon\\":\\"https://example.invalid/icon.png\\",\\"x\\":1,\\"y\\":2,\\"w\\":1,\\"h\\":1,\\"note\\":\\"~price 2 divine orb\\"}"}\n'
            )
        if "account_stash_item_valuations" in query:
            return ""
        if "account_stash_published_scans" in query:
            return '{"published_at":"2026-03-21T12:05:00Z"}\n'
        return ""


class _EmptyPersistedRefreshClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        del settings
        self.queries.append(query)
        if "FROM poe_trade.account_stash_scan_runs" in query:
            return _published_scan_run_row(tabs_total=1, items_total=1)
        return ""


class _EmptyPublishedPersistedRefreshClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        del settings
        self.queries.append(query)
        if "FROM poe_trade.account_stash_scan_runs" in query:
            return _published_scan_run_row(tabs_total=1, items_total=0)
        if "account_stash_scan_tabs" in query:
            return (
                '{"scan_id":"scan-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"captured_at":"2026-03-21T12:00:00Z","tab_meta_json":"{}","payload_json":"{}"}\n'
            )
        if "account_stash_scan_items_v2" in query:
            return ""
        if "account_stash_item_valuations" in query:
            return ""
        if "account_stash_published_scans" in query:
            return '{"published_at":"2026-03-21T12:05:00Z"}\n'
        return ""


class _PartialPersistedRefreshClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        del settings
        self.queries.append(query)
        if "FROM poe_trade.account_stash_scan_runs" in query:
            return _published_scan_run_row(tabs_total=1, items_total=1)
        if "account_stash_scan_tabs" in query:
            return (
                '{"scan_id":"scan-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"captured_at":"2026-03-21T12:00:00Z","tab_meta_json":"{}","payload_json":"{}"}\n'
            )
        return ""


class _ChainedPublishedRefreshClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        del settings
        self.queries.append(query)
        if "FROM poe_trade.account_stash_scan_runs" in query:
            if "scan_id = 'refresh-1'" in query and "scan_kind = 'valuation_refresh'" in query:
                return _published_scan_run_row(
                    scan_id="refresh-1",
                    source_scan_id="scan-1",
                )
            if "scan_id = 'scan-1'" in query and "scan_kind = 'stash_scan'" in query:
                return _published_scan_run_row(scan_id="scan-1")
            return ""
        if "account_stash_scan_tabs" in query:
            return (
                '{"scan_id":"refresh-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"captured_at":"2026-03-21T12:10:00Z","tab_meta_json":"{}","payload_json":"{}"}\n'
            )
        if "account_stash_scan_items_v2" in query:
            return (
                '{"scan_id":"refresh-1","account_name":"qa-exile","league":"Mirage","realm":"pc",'
                '"tab_id":"tab-1","tab_index":0,"tab_name":"Currency","tab_type":"currency",'
                '"lineage_key":"sig:item-1","content_signature":"sig-refresh-1","item_position_key":"tab-1:1:2:1:1",'
                '"item_id":"item-1","item_name":"Hubris Circlet","base_type":"Hubris Circlet","item_class":"Helmet","rarity":"rare",'
                '"x":1,"y":2,"w":1,"h":1,"listed_price":2,"listed_currency":"exalted orb","listed_price_chaos":24,'
                '"estimated_price_chaos":24,"price_p10_chaos":22,"price_p90_chaos":26,"price_delta_chaos":0,'
                '"price_delta_pct":0,"price_band":"good","price_band_version":1,"confidence":82,"estimate_trust":"normal",'
                '"estimate_warning":"","fallback_reason":"","explicit_mods_json":"[]","icon_url":"https://example.invalid/icon.png",'
                '"priced_at":"2026-03-21T12:10:00Z","payload_json":"{\\"id\\":\\"item-1\\",\\"name\\":\\"Grim Bane\\",\\"typeLine\\":\\"Hubris Circlet\\",\\"frameType\\":2,\\"itemClass\\":\\"Helmet\\",\\"icon\\":\\"https://example.invalid/icon.png\\",\\"x\\":1,\\"y\\":2,\\"w\\":1,\\"h\\":1,\\"note\\":\\"~price 2 exalted orb\\",\\"explicitMods\\":[\\"+93 to maximum Life\\"]}"}\n'
            )
        if "account_stash_item_valuations" in query:
            return ""
        if "account_stash_published_scans" in query:
            return '{"published_at":"2026-03-21T12:15:00Z"}\n'
        return ""


def test_run_persisted_valuation_refresh_revalues_published_rows_without_poe_calls() -> None:
    clickhouse = _PersistedRefreshClickHouse()

    result = run_persisted_valuation_refresh(
        clickhouse,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-1",
        scan_id="scan-2",
        started_at="2026-03-21T12:10:00Z",
        price_item=lambda _item: {
            "predictedValue": 24.0,
            "currency": "chaos",
            "confidence": 81.0,
            "interval": {"p10": 22.0, "p90": 26.0},
            "priceRecommendationEligible": True,
            "estimateTrust": "normal",
            "estimateWarning": "",
            "fallbackReason": "",
        },
    )

    assert result["status"] == "published"
    assert result["scanId"] == "scan-2"
    scan_items_query = next(
        query
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_scan_items_v2" in query
    )
    history_query = next(
        query
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_item_history_v2" in query
    )
    scan_rows = [
        json.loads(line)
        for line in scan_items_query.split("FORMAT JSONEachRow\n", 1)[1].splitlines()
    ]
    history_rows = [
        json.loads(line)
        for line in history_query.split("FORMAT JSONEachRow\n", 1)[1].splitlines()
    ]

    assert scan_rows[0]["listed_price_chaos"] == 24.0
    assert scan_rows[0]["estimated_price_chaos"] == 24.0
    assert scan_rows[0]["price_band"] == "good"
    assert history_rows[0]["listed_price_chaos"] == 24.0
    assert history_rows[0]["estimated_price_chaos"] == 24.0
    assert history_rows[0]["price_band"] == "good"
    assert any("account_stash_published_scans" in query for query in clickhouse.queries)


def test_run_persisted_valuation_refresh_fails_closed_when_source_rows_are_missing() -> None:
    clickhouse = _EmptyPersistedRefreshClickHouse()

    result = run_persisted_valuation_refresh(
        clickhouse,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-1",
        scan_id="scan-2",
        started_at="2026-03-21T12:10:00Z",
    )

    assert result["status"] == "failed"
    assert result["error"] == "persisted_source_incomplete"
    assert not any(
        "INSERT INTO poe_trade.account_stash_scan_tabs" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_scan_items_v2" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_item_history_v2" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_item_valuations" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_published_scans" in query
        for query in clickhouse.queries
    )
    failed_run_queries = [
        query
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_scan_runs" in query
        and '"status": "failed"' in query
    ]
    assert len(failed_run_queries) == 1


def test_run_persisted_valuation_refresh_republishes_empty_published_rows() -> None:
    clickhouse = _EmptyPublishedPersistedRefreshClickHouse()

    result = run_persisted_valuation_refresh(
        clickhouse,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-1",
        scan_id="scan-2",
        started_at="2026-03-21T12:10:00Z",
        price_item=lambda _item: {
            "predictedValue": 24.0,
            "currency": "chaos",
            "confidence": 81.0,
            "interval": {"p10": 22.0, "p90": 26.0},
            "priceRecommendationEligible": True,
            "estimateTrust": "normal",
            "estimateWarning": "",
            "fallbackReason": "",
        },
    )

    assert result["status"] == "published"
    assert result["scanId"] == "scan-2"
    assert any(
        "INSERT INTO poe_trade.account_stash_scan_tabs" in query
        for query in clickhouse.queries
    )
    assert any(
        "INSERT INTO poe_trade.account_stash_published_scans" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_scan_runs" in query
        and '"status": "failed"' in query
        for query in clickhouse.queries
    )


def test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh() -> None:
    clickhouse = _ChainedPublishedRefreshClickHouse()

    result = run_persisted_valuation_refresh(
        clickhouse,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="refresh-1",
        scan_id="refresh-2",
        started_at="2026-03-21T12:20:00Z",
        price_item=lambda _item: {
            "predictedValue": 24.0,
            "currency": "chaos",
            "confidence": 81.0,
            "interval": {"p10": 22.0, "p90": 26.0},
            "priceRecommendationEligible": True,
            "estimateTrust": "normal",
            "estimateWarning": "",
            "fallbackReason": "",
        },
    )

    assert result["status"] == "published"
    assert result["scanId"] == "refresh-2"
    assert any(
        "INSERT INTO poe_trade.account_stash_scan_items_v2" in query
        for query in clickhouse.queries
    )
    assert any(
        "INSERT INTO poe_trade.account_stash_published_scans" in query
        for query in clickhouse.queries
    )


def test_run_persisted_valuation_refresh_fails_closed_when_recovered_rows_are_partial() -> None:
    clickhouse = _PartialPersistedRefreshClickHouse()

    result = run_persisted_valuation_refresh(
        clickhouse,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        published_scan_id="scan-1",
        scan_id="scan-2",
        started_at="2026-03-21T12:10:00Z",
    )

    assert result["status"] == "failed"
    assert result["error"] == "persisted_source_incomplete"
    assert not any(
        "INSERT INTO poe_trade.account_stash_scan_tabs" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_scan_items_v2" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_item_history_v2" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_item_valuations" in query
        for query in clickhouse.queries
    )
    assert not any(
        "INSERT INTO poe_trade.account_stash_published_scans" in query
        for query in clickhouse.queries
    )
    failed_run_queries = [
        query
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_scan_runs" in query
        and '"status": "failed"' in query
    ]
    assert len(failed_run_queries) == 1


def test_run_persisted_valuation_refresh_escapes_scope_literals_and_preserves_estimate_currency() -> None:
    clickhouse = _MixedCurrencyPersistedRefreshClickHouse()

    result = run_persisted_valuation_refresh(
        clickhouse,
        account_name="qa'exile",
        league="Mirage's",
        realm="p'c",
        published_scan_id="scan-'1",
        scan_id="scan-2",
        started_at="2026-03-21T12:10:00Z",
        price_item=lambda _item: {
            "predictedValue": 24.0,
            "currency": "chaos",
            "confidence": 81.0,
            "interval": {"p10": 22.0, "p90": 26.0},
            "priceRecommendationEligible": True,
            "estimateTrust": "normal",
            "estimateWarning": "",
            "fallbackReason": "",
        },
    )

    assert result["status"] == "published"
    scan_items_query = next(
        query
        for query in clickhouse.queries
        if "account_stash_scan_items_v2" in query
    )
    legacy_query = next(
        query
        for query in clickhouse.queries
        if "account_stash_item_valuations" in query
    )

    assert "qa''exile" in scan_items_query
    assert "Mirage''s" in scan_items_query
    assert "p''c" in scan_items_query
    assert "scan-''1" in scan_items_query

    legacy_row = json.loads(legacy_query.split("FORMAT JSONEachRow\n", 1)[1])
    assert legacy_row["listed_price"] == 2.0
    assert legacy_row["currency"] == "chaos"
    assert legacy_row["predicted_price"] == 24.0
    assert legacy_row["price_p10"] == 22.0
    assert legacy_row["price_p90"] == 26.0


def test_run_private_scan_publishes_items_without_valuation_callback() -> None:
    clickhouse = _FakeClickHouse()
    harvester = AccountStashHarvester(
        _FakePoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "published"
    valuations_query = next(
        query
        for query in clickhouse.queries
        if "account_stash_item_valuations" in query
    )
    scan_items_query = next(
        query for query in clickhouse.queries if "account_stash_scan_items_v2" in query
    )
    history_query = next(
        query
        for query in clickhouse.queries
        if "account_stash_item_history_v2" in query
    )
    valuations_payload = valuations_query.split("FORMAT JSONEachRow\n", 1)[1]
    row = json.loads(valuations_payload)
    assert row["predicted_price"] == 0.0
    assert row["fallback_reason"] == "valuation_unavailable"
    assert row["price_recommendation_eligible"] == 0
    history_payload = history_query.split("FORMAT JSONEachRow\n", 1)[1]
    history_row = json.loads(history_payload)
    assert history_row["listed_price_chaos"] == 3.0
    assert history_row["estimated_price_chaos"] == 0.0
    assert history_row["price_band"] == "bad"
    scan_item_row = json.loads(scan_items_query.split("FORMAT JSONEachRow\n", 1)[1])
    assert scan_item_row["listed_price_chaos"] == 3.0
    assert scan_item_row["estimated_price_chaos"] == 0.0
    assert scan_item_row["price_band"] == "bad"
    scan_run_rows = [
        json.loads(query.split("FORMAT JSONEachRow\n", 1)[1])
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_scan_runs" in query
    ]
    active_scan_rows = [
        json.loads(query.split("FORMAT JSONEachRow\n", 1)[1])
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_active_scans" in query
    ]
    assert scan_run_rows
    assert active_scan_rows
    assert all(row["scan_kind"] == "stash_scan" for row in scan_run_rows)
    assert all(row["source_scan_id"] == "" for row in scan_run_rows)
    assert all(row["scan_kind"] == "stash_scan" for row in active_scan_rows)
    assert all(row["source_scan_id"] == "" for row in active_scan_rows)


def test_run_private_scan_uses_valuation_callback_when_available() -> None:
    clickhouse = _FakeClickHouse()
    harvester = AccountStashHarvester(
        _FakePoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(
        realm="pc",
        league="Mirage",
        price_item=lambda _item: {
            "predictedValue": 42.0,
            "currency": "chaos",
            "confidence": 88.0,
            "interval": {"p10": 35.0, "p90": 55.0},
            "priceRecommendationEligible": True,
            "estimateTrust": "normal",
            "estimateWarning": "",
            "fallbackReason": "",
        },
    )

    assert result["status"] == "published"
    valuations_query = next(
        query
        for query in clickhouse.queries
        if "account_stash_item_valuations" in query
    )
    scan_items_query = next(
        query for query in clickhouse.queries if "account_stash_scan_items_v2" in query
    )
    valuations_payload = valuations_query.split("FORMAT JSONEachRow\n", 1)[1]
    row = json.loads(valuations_payload)
    assert row["predicted_price"] == 42.0
    assert row["confidence"] == 88.0
    assert row["price_p10"] == 35.0
    assert row["price_p90"] == 55.0
    assert row["fallback_reason"] == ""
    assert row["price_recommendation_eligible"] == 1
    history_query = next(
        query
        for query in clickhouse.queries
        if "account_stash_item_history_v2" in query
    )
    history_row = json.loads(history_query.split("FORMAT JSONEachRow\n", 1)[1])
    assert history_row["estimated_price_chaos"] == 42.0
    assert history_row["price_band"] == "bad"
    scan_item_row = json.loads(scan_items_query.split("FORMAT JSONEachRow\n", 1)[1])
    assert scan_item_row["estimated_price_chaos"] == 42.0
    assert scan_item_row["price_band"] == "bad"
    scan_run_rows = [
        json.loads(query.split("FORMAT JSONEachRow\n", 1)[1])
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_scan_runs" in query
    ]
    active_scan_rows = [
        json.loads(query.split("FORMAT JSONEachRow\n", 1)[1])
        for query in clickhouse.queries
        if "INSERT INTO poe_trade.account_stash_active_scans" in query
    ]
    assert scan_run_rows
    assert active_scan_rows
    assert all(row["scan_kind"] == "stash_scan" for row in scan_run_rows)
    assert all(row["source_scan_id"] == "" for row in scan_run_rows)
    assert all(row["scan_kind"] == "stash_scan" for row in active_scan_rows)
    assert all(row["source_scan_id"] == "" for row in active_scan_rows)


def test_run_private_scan_keeps_published_status_when_valuations_fail() -> None:
    class _FailingValuationsClickHouse(_FakeClickHouse):
        def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
            if "account_stash_item_valuations" in query:
                self.queries.append(query)
                raise RuntimeError("insert failed")
            return super().execute(query, settings=settings)

    clickhouse = _FailingValuationsClickHouse()
    harvester = AccountStashHarvester(
        _FakePoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "published"
    assert any('"status": "published"' in query for query in clickhouse.queries)


def test_run_private_scan_publish_marker_failure_marks_failed() -> None:
    class _FailingPublishMarkerClickHouse(_FakeClickHouse):
        def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
            if "account_stash_published_scans" in query:
                self.queries.append(query)
                raise RuntimeError("insert failed")
            return super().execute(query, settings=settings)

    clickhouse = _FailingPublishMarkerClickHouse()
    harvester = AccountStashHarvester(
        _FakePoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "failed"
    scan_run_queries = [
        query for query in clickhouse.queries if "account_stash_scan_runs" in query
    ]
    assert scan_run_queries
    assert '"status": "failed"' in scan_run_queries[-1]


def test_run_private_scan_publishes_after_v2_rows_before_legacy_valuations() -> None:
    clickhouse = _FakeClickHouse()
    harvester = AccountStashHarvester(
        _FakePoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    _ = harvester.run_private_scan(realm="pc", league="Mirage")

    published_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_scan_runs" in query and '"status": "published"' in query
    )
    scan_items_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_scan_items_v2" in query
    )
    history_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_item_history_v2" in query
    )
    valuations_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_item_valuations" in query
    )

    assert scan_items_query_index < published_query_index
    assert history_query_index < published_query_index
    assert published_query_index < valuations_query_index


def test_run_private_scan_writes_v2_scan_and_history_rows_for_every_item() -> None:
    class _MultiItemPoeClient(_FakePoeClient):
        def request(
            self,
            method: str,
            path: str,
            params: Mapping[str, str] | None = None,
            data: object | None = None,
            headers: Mapping[str, str] | None = None,
        ):
            del method, path, data, headers
            params = dict(params or {})
            if params.get("tabs") == "1":
                return {
                    "tabs": [
                        {"id": "tab-1", "i": 0, "n": "Currency", "type": "currency"},
                        {"id": "tab-2", "i": 1, "n": "Gear", "type": "normal"},
                    ]
                }
            if params.get("tabIndex") == "0":
                return {
                    "stash": {
                        "id": "tab-1",
                        "items": [
                            {
                                "id": "item-1",
                                "name": "Mirror Shard",
                                "typeLine": "Mirror Shard",
                                "frameType": 0,
                                "itemClass": "Currency",
                                "icon": "https://example.invalid/icon-1.png",
                                "x": 1,
                                "y": 2,
                                "w": 1,
                                "h": 1,
                                "note": "~price 3 chaos",
                            },
                            {
                                "id": "item-2",
                                "name": "Chromatic Orb",
                                "typeLine": "Chromatic Orb",
                                "frameType": 0,
                                "itemClass": "Currency",
                                "icon": "https://example.invalid/icon-2.png",
                                "x": 2,
                                "y": 2,
                                "w": 1,
                                "h": 1,
                                "note": "~price 1 chaos",
                            },
                        ],
                    }
                }
            return {
                "stash": {
                    "id": "tab-2",
                    "items": [
                        {
                            "id": "item-3",
                            "name": "Hubris Circlet",
                            "typeLine": "Hubris Circlet",
                            "frameType": 2,
                            "itemClass": "Helmet",
                            "icon": "https://example.invalid/icon-3.png",
                            "x": 4,
                            "y": 6,
                            "w": 2,
                            "h": 2,
                            "note": "~price 40 chaos",
                        }
                    ],
                }
            }

    clickhouse = _FakeClickHouse()
    price_map = {
        "item-1": 3.0,
        "item-2": 1.0,
        "item-3": 40.0,
    }
    harvester = AccountStashHarvester(
        _MultiItemPoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
        price_item=lambda raw_item: {
            "predictedValue": price_map[str(raw_item.get("id") or "")],
            "currency": "chaos",
            "confidence": 91.0,
            "interval": {
                "p10": price_map[str(raw_item.get("id") or "")] * 0.9,
                "p90": price_map[str(raw_item.get("id") or "")] * 1.1,
            },
            "priceRecommendationEligible": True,
            "estimateTrust": "normal",
            "estimateWarning": "",
            "fallbackReason": "",
        },
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "published"
    scan_items_query = next(
        query for query in clickhouse.queries if "account_stash_scan_items_v2" in query
    )
    history_query = next(
        query for query in clickhouse.queries if "account_stash_item_history_v2" in query
    )
    scan_rows = [
        json.loads(line)
        for line in scan_items_query.split("FORMAT JSONEachRow\n", 1)[1].splitlines()
    ]
    history_rows = [
        json.loads(line)
        for line in history_query.split("FORMAT JSONEachRow\n", 1)[1].splitlines()
    ]

    assert [row["item_id"] for row in scan_rows] == ["item-1", "item-2", "item-3"]
    assert [row["item_id"] for row in history_rows] == ["item-1", "item-2", "item-3"]
    assert all(row["price_band"] == "good" for row in scan_rows)
    assert all("price_band_version" in row for row in scan_rows)
    assert all("estimate_trust" in row for row in history_rows)
    assert all("estimate_warning" in row for row in history_rows)
    assert all("fallback_reason" in row for row in history_rows)
    assert all(row["price_evaluation"] == "well_priced" for row in scan_rows)

    published_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_scan_runs" in query and '"status": "published"' in query
    )
    scan_items_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_scan_items_v2" in query
    )
    history_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_item_history_v2" in query
    )
    valuations_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_item_valuations" in query
    )

    assert scan_items_query_index < published_query_index
    assert history_query_index < published_query_index
    assert published_query_index < valuations_query_index


def test_publishes_all_scanned_items_to_v2_rows_and_history() -> None:
    class _MultiItemPoeClient(_FakePoeClient):
        def request(
            self,
            method: str,
            path: str,
            params: Mapping[str, str] | None = None,
            data: object | None = None,
            headers: Mapping[str, str] | None = None,
        ):
            del method, path, data, headers
            params = dict(params or {})
            if params.get("tabs") == "1":
                return {
                    "tabs": [
                        {"id": "tab-1", "i": 0, "n": "Currency", "type": "currency"},
                        {"id": "tab-2", "i": 1, "n": "Gear", "type": "normal"},
                    ]
                }
            if params.get("tabIndex") == "0":
                return {
                    "stash": {
                        "id": "tab-1",
                        "items": [
                            {
                                "id": "item-1",
                                "name": "Mirror Shard",
                                "typeLine": "Mirror Shard",
                                "frameType": 0,
                                "itemClass": "Currency",
                                "icon": "https://example.invalid/icon-1.png",
                                "x": 1,
                                "y": 2,
                                "w": 1,
                                "h": 1,
                                "note": "~price 3 chaos",
                            },
                            {
                                "id": "item-2",
                                "name": "Chromatic Orb",
                                "typeLine": "Chromatic Orb",
                                "frameType": 0,
                                "itemClass": "Currency",
                                "icon": "https://example.invalid/icon-2.png",
                                "x": 2,
                                "y": 2,
                                "w": 1,
                                "h": 1,
                                "note": "~price 1 chaos",
                            },
                        ],
                    }
                }
            return {
                "stash": {
                    "id": "tab-2",
                    "items": [
                        {
                            "id": "item-3",
                            "name": "Hubris Circlet",
                            "typeLine": "Hubris Circlet",
                            "frameType": 2,
                            "itemClass": "Helmet",
                            "icon": "https://example.invalid/icon-3.png",
                            "x": 4,
                            "y": 6,
                            "w": 2,
                            "h": 2,
                            "note": "~price 40 chaos",
                        }
                    ],
                }
            }

    clickhouse = _FakeClickHouse()
    harvester = AccountStashHarvester(
        _MultiItemPoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "published"
    scan_items_query = next(
        query for query in clickhouse.queries if "account_stash_scan_items_v2" in query
    )
    history_query = next(
        query for query in clickhouse.queries if "account_stash_item_history_v2" in query
    )
    scan_rows = [
        json.loads(line)
        for line in scan_items_query.split("FORMAT JSONEachRow\n", 1)[1].splitlines()
    ]
    history_rows = [
        json.loads(line)
        for line in history_query.split("FORMAT JSONEachRow\n", 1)[1].splitlines()
    ]

    assert [row["item_id"] for row in scan_rows] == ["item-1", "item-2", "item-3"]
    assert [row["item_id"] for row in history_rows] == ["item-1", "item-2", "item-3"]
    assert all("price_band" in row for row in scan_rows)
    assert all("lineage_key" in row for row in history_rows)
    published_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_scan_runs" in query and '"status": "published"' in query
    )
    scan_items_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_scan_items_v2" in query
    )
    history_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_item_history_v2" in query
    )
    valuations_query_index = next(
        index
        for index, query in enumerate(clickhouse.queries)
        if "account_stash_item_valuations" in query
    )

    assert scan_items_query_index < published_query_index
    assert history_query_index < published_query_index
    assert published_query_index < valuations_query_index


def test_run_private_scan_v2_write_failure_marks_failed_without_publish() -> None:
    class _FailingHistoryClickHouse(_FakeClickHouse):
        def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
            if "account_stash_item_history_v2" in query:
                self.queries.append(query)
                raise RuntimeError("insert failed")
            return super().execute(query, settings=settings)

    clickhouse = _FailingHistoryClickHouse()
    harvester = AccountStashHarvester(
        _FakePoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "failed"
    assert sum('"status": "published"' in query for query in clickhouse.queries) == 0


def test_run_private_scan_failure_finalizes_once() -> None:
    clickhouse = _FakeClickHouse()
    harvester = AccountStashHarvester(
        _FailingPoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "failed"
    assert sum('"status": "failed"' in query for query in clickhouse.queries) == 1
    assert sum('"status": "published"' in query for query in clickhouse.queries) == 0


def test_run_private_scan_does_not_coerce_unknown_currency_to_chaos() -> None:
    clickhouse = _FakeClickHouse()
    harvester = AccountStashHarvester(
        _UnsupportedCurrencyPoeClient(),
        clickhouse,
        StatusReporter(clickhouse, "account_stash_harvester"),
        account_name="qa-exile",
        access_token="access-token",
    )

    result = harvester.run_private_scan(realm="pc", league="Mirage")

    assert result["status"] == "published"
    scan_items_query = next(
        query for query in clickhouse.queries if "account_stash_scan_items_v2" in query
    )
    history_query = next(
        query for query in clickhouse.queries if "account_stash_item_history_v2" in query
    )
    scan_item_row = json.loads(scan_items_query.split("FORMAT JSONEachRow\n", 1)[1])
    history_row = json.loads(history_query.split("FORMAT JSONEachRow\n", 1)[1])
    assert scan_item_row["listed_price_chaos"] is None
    assert scan_item_row["estimated_price_chaos"] is None
    assert scan_item_row["price_delta_pct"] is None
    assert scan_item_row["price_band"] == "bad"
    assert history_row["listed_price_chaos"] is None
    assert history_row["estimated_price_chaos"] is None
    assert history_row["price_band"] == "bad"


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("~price 2 divine orb", (2.0, "divine orb")),
        ("~b/o 3 exalted orbs", (3.0, "exalted orbs")),
    ],
)
def test_parse_listed_price_handles_multi_word_currency_labels(
    note: str,
    expected: tuple[float, str],
) -> None:
    assert parse_listed_price(note) == expected
