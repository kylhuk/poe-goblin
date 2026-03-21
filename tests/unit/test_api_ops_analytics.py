from __future__ import annotations

import json
import re
from collections.abc import Mapping

import pytest

from poe_trade.api.ops import (
    analytics_backtests,
    analytics_gold_diagnostics,
    analytics_pricing_outliers,
    analytics_search_history,
    analytics_search_suggestions,
    analytics_report,
    analytics_scanner,
    dashboard_payload,
    scanner_recommendations_payload,
    scanner_summary_payload,
)
from poe_trade.api.service_control import ServiceSnapshot
from poe_trade.db import ClickHouseClient


class _RecordingClickHouse(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        self.queries.append(query)
        return ""


class _FixtureClickHouse(ClickHouseClient):
    def __init__(self, responses: dict[str, str]) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.responses: dict[str, str] = responses
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        del settings
        self.queries.append(query)
        for needle, response in self.responses.items():
            if needle in query:
                return response
        return ""


class _SequentialFixtureClickHouse(ClickHouseClient):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.responses = list(responses)
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        del settings
        self.queries.append(query)
        if self.responses:
            return self.responses.pop(0)
        return ""


class _SearchOrderingClickHouse(ClickHouseClient):
    def __init__(
        self,
        *,
        suggestion_rows: list[dict[str, object]] | None = None,
        history_rows: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.suggestion_rows = suggestion_rows or []
        self.history_rows = history_rows or []
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        del settings
        self.queries.append(query)
        if "GROUP BY item_name, item_kind, relevance_rank" in query:
            return self._suggestion_payload(query)
        if (
            "normalized_price_chaos AS listed_price," in query
            and "AS relevance_rank" in query
        ):
            return self._history_payload(query)
        return ""

    def _suggestion_payload(self, query: str) -> str:
        query_text = self._extract_query_text(query)
        filtered = [
            row
            for row in self.suggestion_rows
            if query_text.lower() in str(row["item_name"]).lower()
        ]
        if "ORDER BY relevance_rank ASC, match_count DESC, item_name ASC" in query:
            filtered.sort(
                key=lambda row: (
                    self._relevance_rank(str(row["item_name"]), query_text),
                    -int(str(row["match_count"])),
                    str(row["item_name"]),
                )
            )
        elif "ORDER BY match_count DESC, item_name ASC" in query:
            filtered.sort(
                key=lambda row: (-int(str(row["match_count"])), str(row["item_name"]))
            )
        return "\n".join(json.dumps(row) for row in filtered)

    def _history_payload(self, query: str) -> str:
        query_text = self._extract_query_text(query)
        filtered = self.history_rows
        if query_text:
            filtered = [
                row
                for row in filtered
                if query_text.lower() in str(row["item_name"]).lower()
            ]

        order_key = self._history_sort_key(query, query_text)
        if order_key is not None:
            filtered = sorted(filtered, key=order_key)
        return "\n".join(json.dumps(row) for row in filtered)

    def _history_sort_key(self, query: str, query_text: str):
        if "ORDER BY relevance_rank ASC, item_name ASC, added_on DESC" in query:
            return lambda row: (
                self._relevance_rank(str(row["item_name"]), query_text),
                str(row["item_name"]),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY relevance_rank ASC, item_name DESC, added_on DESC" in query:
            return lambda row: (
                self._relevance_rank(str(row["item_name"]), query_text),
                self._descending_text(str(row["item_name"])),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY item_name ASC, added_on DESC" in query:
            return lambda row: (
                str(row["item_name"]),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY item_name DESC, added_on DESC" in query:
            return lambda row: (
                self._descending_text(str(row["item_name"])),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY listed_price ASC, added_on DESC" in query:
            return lambda row: (
                float(row["listed_price"]),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY listed_price DESC, added_on DESC" in query:
            return lambda row: (
                -float(row["listed_price"]),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY league ASC, added_on DESC" in query:
            return lambda row: (
                str(row["league"]),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY league DESC, added_on DESC" in query:
            return lambda row: (
                self._descending_text(str(row["league"])),
                -self._sortable_timestamp(str(row["added_on"])),
            )
        if "ORDER BY added_on ASC" in query:
            return lambda row: self._sortable_timestamp(str(row["added_on"]))
        if "ORDER BY added_on DESC" in query:
            return lambda row: -self._sortable_timestamp(str(row["added_on"]))
        return None

    @staticmethod
    def _extract_query_text(query: str) -> str:
        match = re.search(r"positionCaseInsensitiveUTF8\(.*?, '([^']*)'\) > 0", query)
        if not match:
            return ""
        return match.group(1).replace("\\'", "'").replace("\\\\", "\\")

    @staticmethod
    def _relevance_rank(item_name: str, query_text: str) -> int:
        if not query_text:
            return 3
        lowered_name = item_name.lower()
        lowered_query = query_text.lower()
        if lowered_name == lowered_query:
            return 0
        if lowered_name.startswith(lowered_query):
            return 1
        if lowered_query in lowered_name:
            return 2
        return 3

    @staticmethod
    def _sortable_timestamp(value: str) -> int:
        return int(value.replace("-", "").replace(" ", "").replace(":", ""))

    @staticmethod
    def _descending_text(value: str) -> tuple[int, ...]:
        return tuple(-ord(char) for char in value)


def test_analytics_scanner_query_does_not_require_status_column() -> None:
    client = _RecordingClickHouse()

    result = analytics_scanner(client)

    assert result == {"rows": []}
    assert len(client.queries) == 1
    assert "scanner_recommendations.status" not in client.queries[0]
    assert "GROUP BY status" not in client.queries[0]
    assert "GROUP BY strategy_id" in client.queries[0]
    assert "recommendation_count" in client.queries[0]


def test_analytics_backtests_returns_truthful_empty_payload() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.research_backtest_summary": "",
            "FROM poe_trade.research_backtest_detail": "",
        }
    )

    result = analytics_backtests(client)

    assert result == {
        "rows": [],
        "summaryRows": [],
        "detailRows": [],
        "totals": {"summary": 0, "detail": 0},
    }
    assert any(
        "FROM poe_trade.research_backtest_summary" in query for query in client.queries
    )
    assert any(
        "FROM poe_trade.research_backtest_detail" in query for query in client.queries
    )


def test_analytics_backtests_returns_summary_and_detail_counts() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.research_backtest_summary": (
                '{"status":"completed","count":2}\n{"status":"no_data","count":1}\n'
            ),
            "FROM poe_trade.research_backtest_detail": (
                '{"status":"completed","count":5}\n'
            ),
        }
    )

    result = analytics_backtests(client)

    assert result["rows"] == [
        {"status": "completed", "count": 2},
        {"status": "no_data", "count": 1},
    ]
    assert result["summaryRows"] == result["rows"]
    assert result["detailRows"] == [{"status": "completed", "count": 5}]
    assert result["totals"] == {"summary": 3, "detail": 5}


def test_analytics_report_returns_empty_status_when_all_counts_are_zero() -> None:
    client = _FixtureClickHouse(
        {
            "FORMAT JSONEachRow": (
                '{"league":"Mirage","recommendations":0,"alerts":0,'
                '"journal_events":0,"journal_positions":0,'
                '"backtest_summary_rows":0,"backtest_detail_rows":0,'
                '"gold_currency_ref_hour_rows":0,"gold_listing_ref_hour_rows":0,'
                '"gold_liquidity_ref_hour_rows":0,"gold_bulk_premium_hour_rows":0,'
                '"gold_set_ref_hour_rows":0,"realized_pnl_chaos":0.0}\n'
            )
        }
    )

    result = analytics_report(client, league="Mirage")

    assert result["status"] == "empty"
    assert result["report"]["league"] == "Mirage"
    assert result["report"]["gold_set_ref_hour_rows"] == 0
    assert result["report"]["backtest_detail_rows"] == 0


def test_analytics_gold_diagnostics_distinguishes_stale_empty_and_league_gap() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.v_gold_mart_diagnostics": (
                '{"mart_name":"gold_bulk_premium_hour","source_name":"v_ps_items_enriched",'
                '"source_row_count":220,"source_latest_at":"2026-03-15 12:00:00",'
                '"source_distinct_league_count":2,"source_blank_or_null_league_rows":0,'
                '"gold_row_count":40,"gold_latest_at":"2026-03-15 09:00:00",'
                '"gold_distinct_league_count":2,"gold_blank_or_null_league_rows":0,'
                '"gold_freshness_minutes":180,"source_to_gold_lag_minutes":180,'
                '"diagnostic_state":"gold_stale_vs_source"}\n'
                '{"mart_name":"gold_currency_ref_hour","source_name":"v_cx_markets_enriched",'
                '"source_row_count":0,"source_latest_at":null,'
                '"source_distinct_league_count":0,"source_blank_or_null_league_rows":0,'
                '"gold_row_count":0,"gold_latest_at":null,'
                '"gold_distinct_league_count":0,"gold_blank_or_null_league_rows":0,'
                '"gold_freshness_minutes":null,"source_to_gold_lag_minutes":null,'
                '"diagnostic_state":"source_empty"}\n'
                '{"mart_name":"gold_listing_ref_hour","source_name":"v_ps_items_enriched",'
                '"source_row_count":300,"source_latest_at":"2026-03-15 12:00:00",'
                '"source_distinct_league_count":2,"source_blank_or_null_league_rows":0,'
                '"gold_row_count":0,"gold_latest_at":null,'
                '"gold_distinct_league_count":0,"gold_blank_or_null_league_rows":0,'
                '"gold_freshness_minutes":null,"source_to_gold_lag_minutes":null,'
                '"diagnostic_state":"gold_empty"}\n'
            ),
            "source_league_rows": (
                '{"mart_name":"gold_bulk_premium_hour","source_league_rows":120,"gold_league_rows":30}\n'
                '{"mart_name":"gold_currency_ref_hour","source_league_rows":0,"gold_league_rows":0}\n'
                '{"mart_name":"gold_listing_ref_hour","source_league_rows":150,"gold_league_rows":0}\n'
            ),
        }
    )

    result = analytics_gold_diagnostics(client, league="Mirage")

    assert result["league"] == "Mirage"
    assert result["summary"]["status"] == "league_gap"
    assert result["summary"]["martCount"] == 3
    assert result["summary"]["problemMarts"] == 3
    assert result["summary"]["goldEmptyMarts"] == 1
    assert result["summary"]["staleMarts"] == 1
    assert result["summary"]["missingLeagueMarts"] == 1
    assert result["marts"][0]["martName"] == "gold_bulk_premium_hour"
    assert result["marts"][0]["diagnosticState"] == "gold_stale_vs_source"
    assert result["marts"][0]["leagueVisibility"] == "visible"
    assert result["marts"][1]["leagueVisibility"] == "absent_upstream"
    assert result["marts"][2]["leagueVisibility"] == "missing_in_gold"


def test_analytics_report_includes_gold_diagnostics_payload() -> None:
    client = _FixtureClickHouse(
        {
            "SELECT 'Mirage' AS league": (
                '{"league":"Mirage","recommendations":0,"alerts":0,'
                '"journal_events":0,"journal_positions":0,'
                '"backtest_summary_rows":0,"backtest_detail_rows":0,'
                '"gold_currency_ref_hour_rows":0,"gold_listing_ref_hour_rows":0,'
                '"gold_liquidity_ref_hour_rows":0,"gold_bulk_premium_hour_rows":0,'
                '"gold_set_ref_hour_rows":0,"realized_pnl_chaos":0.0}\n'
            ),
            "FROM poe_trade.v_gold_mart_diagnostics": (
                '{"mart_name":"gold_listing_ref_hour","source_name":"v_ps_items_enriched",'
                '"source_row_count":100,"source_latest_at":"2026-03-15 12:00:00",'
                '"source_distinct_league_count":1,"source_blank_or_null_league_rows":0,'
                '"gold_row_count":0,"gold_latest_at":null,'
                '"gold_distinct_league_count":0,"gold_blank_or_null_league_rows":0,'
                '"gold_freshness_minutes":null,"source_to_gold_lag_minutes":null,'
                '"diagnostic_state":"gold_empty"}\n'
            ),
            "source_league_rows": (
                '{"mart_name":"gold_listing_ref_hour","source_league_rows":100,"gold_league_rows":0}\n'
            ),
        }
    )

    result = analytics_report(client, league="Mirage")

    assert result["status"] == "empty"
    assert result["goldDiagnostics"]["summary"]["status"] == "league_gap"
    assert result["goldDiagnostics"]["marts"][0]["martName"] == "gold_listing_ref_hour"


def test_analytics_report_returns_ok_status_when_any_count_is_present() -> None:
    client = _FixtureClickHouse(
        {
            "FORMAT JSONEachRow": (
                '{"league":"Mirage","recommendations":4,"alerts":1,'
                '"journal_events":9,"journal_positions":2,'
                '"backtest_summary_rows":3,"backtest_detail_rows":11,'
                '"gold_currency_ref_hour_rows":7,"gold_listing_ref_hour_rows":6,'
                '"gold_liquidity_ref_hour_rows":5,"gold_bulk_premium_hour_rows":4,'
                '"gold_set_ref_hour_rows":3,"realized_pnl_chaos":42.5}\n'
            )
        }
    )

    result = analytics_report(client, league="Mirage")

    assert result["status"] == "ok"
    assert result["report"]["backtest_summary_rows"] == 3
    assert result["report"]["gold_currency_ref_hour_rows"] == 7
    assert result["report"]["realized_pnl_chaos"] == 42.5


def test_analytics_search_suggestions_orders_exact_before_prefix_and_substring() -> (
    None
):
    client = _SearchOrderingClickHouse(
        suggestion_rows=[
            {
                "item_name": "The Mageblood Map",
                "item_kind": "base_type",
                "match_count": 30,
            },
            {
                "item_name": "Mageblood Replica",
                "item_kind": "unique_name",
                "match_count": 20,
            },
            {"item_name": "Mageblood", "item_kind": "unique_name", "match_count": 5},
        ]
    )

    payload = analytics_search_suggestions(client, query="Mageblood")

    assert [row["itemName"] for row in payload["suggestions"]] == [
        "Mageblood",
        "Mageblood Replica",
        "The Mageblood Map",
    ]


def test_analytics_search_suggestions_breaks_same_rank_ties_by_match_count_then_name() -> (
    None
):
    client = _SearchOrderingClickHouse(
        suggestion_rows=[
            {
                "item_name": "Mageblood Reliquary",
                "item_kind": "unique_name",
                "match_count": 10,
            },
            {
                "item_name": "Mageblood Reserve",
                "item_kind": "unique_name",
                "match_count": 20,
            },
            {
                "item_name": "Mageblood Replica",
                "item_kind": "unique_name",
                "match_count": 20,
            },
        ]
    )

    payload = analytics_search_suggestions(client, query="Mageblood R")

    assert [row["itemName"] for row in payload["suggestions"]] == [
        "Mageblood Replica",
        "Mageblood Reserve",
        "Mageblood Reliquary",
    ]


def test_analytics_search_history_returns_nested_query_object_and_name_first_default() -> (
    None
):
    client = _SearchOrderingClickHouse(
        history_rows=[
            {
                "item_name": "The Mageblood Map",
                "league": "Mirage",
                "listed_price": 80.0,
                "added_on": "2026-03-15 10:00:00",
            },
            {
                "item_name": "Mageblood Replica",
                "league": "Mirage",
                "listed_price": 90.0,
                "added_on": "2026-03-15 11:00:00",
            },
            {
                "item_name": "Mageblood",
                "league": "Mirage",
                "listed_price": 95.0,
                "added_on": "2026-03-15 12:00:00",
            },
        ]
    )

    payload = analytics_search_history(
        client,
        query_params={"query": ["Mageblood"]},
        default_league="Mirage",
    )

    assert payload["query"] == {
        "text": "Mageblood",
        "league": "Mirage",
        "sort": "item_name",
        "order": "asc",
    }
    assert [row["itemName"] for row in payload["rows"]] == [
        "Mageblood",
        "Mageblood Replica",
        "The Mageblood Map",
    ]


def test_analytics_search_history_orders_exact_prefix_then_substring_for_item_name_sort() -> (
    None
):
    client = _SearchOrderingClickHouse(
        history_rows=[
            {
                "item_name": "The Mageblood Map",
                "league": "Mirage",
                "listed_price": 80.0,
                "added_on": "2026-03-15 10:00:00",
            },
            {
                "item_name": "Mageblood Replica",
                "league": "Mirage",
                "listed_price": 90.0,
                "added_on": "2026-03-15 11:00:00",
            },
            {
                "item_name": "Mageblood",
                "league": "Mirage",
                "listed_price": 95.0,
                "added_on": "2026-03-15 12:00:00",
            },
        ]
    )

    payload = analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": ["item_name"], "order": ["asc"]},
        default_league="Mirage",
    )

    assert [row["itemName"] for row in payload["rows"][:3]] == [
        "Mageblood",
        "Mageblood Replica",
        "The Mageblood Map",
    ]


def test_analytics_search_history_item_name_desc_still_applies_without_query_text() -> (
    None
):
    client = _SearchOrderingClickHouse(
        history_rows=[
            {
                "item_name": "Mageblood",
                "league": "Mirage",
                "listed_price": 95.0,
                "added_on": "2026-03-15 12:00:00",
            },
            {
                "item_name": "Aegis Aurora",
                "league": "Mirage",
                "listed_price": 70.0,
                "added_on": "2026-03-15 11:00:00",
            },
            {
                "item_name": "The Squire",
                "league": "Mirage",
                "listed_price": 120.0,
                "added_on": "2026-03-15 10:00:00",
            },
        ]
    )

    payload = analytics_search_history(
        client,
        query_params={"sort": ["item_name"], "order": ["desc"]},
        default_league="Mirage",
    )

    assert [row["itemName"] for row in payload["rows"]] == [
        "The Squire",
        "Mageblood",
        "Aegis Aurora",
    ]


@pytest.mark.parametrize(
    ("sort", "order", "expected_names"),
    [
        ("added_on", "desc", ["Mageblood", "The Mageblood Map", "Mageblood Replica"]),
        (
            "listed_price",
            "asc",
            ["Mageblood Replica", "The Mageblood Map", "Mageblood"],
        ),
        ("league", "asc", ["Mageblood Replica", "The Mageblood Map", "Mageblood"]),
    ],
)
def test_analytics_search_history_keeps_non_name_sorts_primary(
    sort: str,
    order: str,
    expected_names: list[str],
) -> None:
    client = _SearchOrderingClickHouse(
        history_rows=[
            {
                "item_name": "The Mageblood Map",
                "league": "Mirage",
                "listed_price": 80.0,
                "added_on": "2026-03-15 11:00:00",
            },
            {
                "item_name": "Mageblood Replica",
                "league": "Ancestor",
                "listed_price": 70.0,
                "added_on": "2026-03-15 10:00:00",
            },
            {
                "item_name": "Mageblood",
                "league": "Necropolis",
                "listed_price": 90.0,
                "added_on": "2026-03-15 12:00:00",
            },
        ]
    )

    payload = analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": [sort], "order": [order]},
        default_league="Mirage",
    )

    assert [row["itemName"] for row in payload["rows"]] == expected_names


def test_analytics_pricing_outliers_defaults_to_100c_buy_in_and_expected_profit_sort() -> (
    None
):
    client = _SequentialFixtureClickHouse(
        [
            '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":1.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.4}\n',
            '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
        ]
    )

    payload = analytics_pricing_outliers(
        client, query_params={}, default_league="Mirage"
    )

    assert payload["query"] == {
        "query": "",
        "text": "",
        "league": "Mirage",
        "sort": "expected_profit",
        "order": "desc",
        "minTotal": 20,
        "maxBuyIn": 100,
        "limit": 100,
        "weeklyAggregation": {
            "level": "item_name",
            "scope": "deduped_filtered_rows",
        },
    }
    assert payload["rows"][0]["entryPrice"] == pytest.approx(90.0)
    assert payload["rows"][0]["expectedProfit"] == pytest.approx(60.0)
    assert payload["rows"][0]["roi"] == pytest.approx(60.0 / 90.0)


def test_analytics_pricing_outliers_keeps_negative_expected_profit_when_median_is_below_entry() -> (
    None
):
    client = _SequentialFixtureClickHouse(
        [
            '{"item_name":"Bad Deal","affix_analyzed":"","p10":120.0,"median":100.0,"p90":140.0,"items_per_week":1.0,"items_total":30,"analysis_level":"item","underpriced_rate":0.125}\n',
            '{"week_start":"2026-03-10 00:00:00","too_cheap_count":1}\n',
        ]
    )

    payload = analytics_pricing_outliers(
        client, query_params={}, default_league="Mirage"
    )

    assert payload["rows"][0]["expectedProfit"] == pytest.approx(-20.0)
    assert payload["rows"][0]["roi"] == pytest.approx(-20.0 / 120.0)


def test_analytics_pricing_outliers_rounds_underpriced_rate_to_four_decimals() -> None:
    client = _SequentialFixtureClickHouse(
        [
            '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":1.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.428571}\n',
            '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
        ]
    )

    payload = analytics_pricing_outliers(
        client, query_params={}, default_league="Mirage"
    )

    assert payload["rows"][0]["underpricedRate"] == pytest.approx(0.4286)


def test_analytics_pricing_outliers_preserves_items_per_week_as_listing_frequency() -> (
    None
):
    client = _SequentialFixtureClickHouse(
        [
            '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":3.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.25}\n',
            '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
        ]
    )

    payload = analytics_pricing_outliers(
        client, query_params={}, default_league="Mirage"
    )

    assert payload["rows"][0]["itemsPerWeek"] == pytest.approx(3.5)
    assert payload["rows"][0]["underpricedRate"] == pytest.approx(0.25)


def test_analytics_pricing_outliers_weekly_query_reuses_effective_filters() -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(
        client,
        query_params={
            "query": ["Mageblood"],
            "league": ["Mirage"],
            "min_total": ["25"],
            "max_buy_in": ["100"],
            "sort": ["roi"],
            "limit": ["5"],
        },
        default_league="Mirage",
    )

    weekly_query = next(query for query in client.queries if "weekly_input AS" in query)

    assert any("league = 'Mirage'" in query for query in client.queries)
    assert any("HAVING items_total >= 25" in query for query in client.queries)
    assert any("<= 100" in query for query in client.queries)
    assert any(
        "positionCaseInsensitiveUTF8(item_name" in query for query in client.queries
    )
    assert "countIf(b.listed_price <= f.p10)" in weekly_query
    assert "min(p10) AS p10" in weekly_query
    assert "max(items_total) AS items_total" in weekly_query
    assert "GROUP BY item_name" in weekly_query
    assert "ORDER BY roi" not in weekly_query
    assert "LIMIT 5" not in weekly_query


def test_analytics_pricing_outliers_weekly_query_dedupes_by_item_name_only() -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(
        client,
        query_params={"query": ["Mageblood"]},
        default_league="Mirage",
    )

    weekly_query = next(query for query in client.queries if "weekly_input AS" in query)

    assert (
        "SELECT DISTINCT item_name, p10, items_total FROM item_rows" not in weekly_query
    )
    assert "GROUP BY item_name" in weekly_query


def test_analytics_pricing_outliers_affix_only_query_reuses_effective_item_names() -> (
    None
):
    client = _RecordingClickHouse()

    analytics_pricing_outliers(
        client,
        query_params={"query": ["Fractured"]},
        default_league="Mirage",
    )

    weekly_query = next(query for query in client.queries if "weekly_input AS" in query)

    assert "table_rows AS (" in weekly_query
    assert (
        "positionCaseInsensitiveUTF8(affix_analyzed, 'Fractured') > 0" in weekly_query
    )
    assert (
        "SELECT item_name, min(p10) AS p10, max(items_total) AS items_total FROM table_rows"
        in weekly_query
    )
    assert "GROUP BY item_name" in weekly_query


def test_analytics_pricing_outliers_clamps_non_numeric_and_out_of_range_buy_in() -> (
    None
):
    default_payload = analytics_pricing_outliers(
        _RecordingClickHouse(),
        query_params={"max_buy_in": ["nope"]},
        default_league="Mirage",
    )
    minimum_payload = analytics_pricing_outliers(
        _RecordingClickHouse(),
        query_params={"max_buy_in": ["0"]},
        default_league="Mirage",
    )
    maximum_payload = analytics_pricing_outliers(
        _RecordingClickHouse(),
        query_params={"max_buy_in": ["5001"]},
        default_league="Mirage",
    )

    assert default_payload["query"]["maxBuyIn"] == 100
    assert minimum_payload["query"]["maxBuyIn"] == 1
    assert maximum_payload["query"]["maxBuyIn"] == 1000


def test_analytics_pricing_outliers_accepts_camel_case_max_buy_in() -> None:
    client = _RecordingClickHouse()

    payload = analytics_pricing_outliers(
        client, query_params={"maxBuyIn": ["77"]}, default_league="Mirage"
    )

    assert payload["query"]["maxBuyIn"] == 77


def test_analytics_pricing_outliers_accepts_new_and_legacy_sort_values() -> None:
    fair_value_client = _SequentialFixtureClickHouse(
        [
            '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":1.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.4}\n',
            '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
        ]
    )
    fair_value_payload = analytics_pricing_outliers(
        fair_value_client,
        query_params={"sort": ["fair_value"]},
        default_league="Mirage",
    )
    assert fair_value_payload["query"]["sort"] == "fair_value"

    client = _SequentialFixtureClickHouse(
        [
            '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":1.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.4}\n',
            '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
            '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":1.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.4}\n',
            '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
        ]
    )
    median_payload = analytics_pricing_outliers(
        client, query_params={"sort": ["median"]}, default_league="Mirage"
    )
    p10_payload = analytics_pricing_outliers(
        client, query_params={"sort": ["p10"]}, default_league="Mirage"
    )

    assert median_payload["query"]["sort"] == "median"
    assert p10_payload["query"]["sort"] == "p10"


@pytest.mark.parametrize(
    ("sort", "expected_fragment"),
    [
        (
            "roi",
            "ORDER BY roi DESC, expected_profit DESC, underpriced_rate DESC, items_total DESC, item_name ASC, affix_analyzed ASC, analysis_level ASC, base_type ASC, rarity ASC",
        ),
        (
            "underpriced_rate",
            "ORDER BY underpriced_rate DESC, expected_profit DESC, roi DESC, items_total DESC, item_name ASC, affix_analyzed ASC, analysis_level ASC, base_type ASC, rarity ASC",
        ),
        (
            "entry_price",
            "ORDER BY entry_price DESC, expected_profit DESC, roi DESC, underpriced_rate DESC, items_total DESC, item_name ASC, affix_analyzed ASC, analysis_level ASC, base_type ASC, rarity ASC",
        ),
        (
            "items_total",
            "ORDER BY items_total DESC, expected_profit DESC, roi DESC, underpriced_rate DESC, item_name ASC, affix_analyzed ASC, analysis_level ASC, base_type ASC, rarity ASC",
        ),
    ],
)
def test_analytics_pricing_outliers_secondary_sorts_append_default_chain(
    sort: str, expected_fragment: str
) -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(
        client,
        query_params={"sort": [sort], "order": ["desc"]},
        default_league="Mirage",
    )

    assert any(expected_fragment in query for query in client.queries)


def test_analytics_pricing_outliers_uses_specified_tie_break_order() -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(client, query_params={}, default_league="Mirage")

    assert any(
        "ORDER BY expected_profit DESC, roi DESC, underpriced_rate DESC, items_total DESC, item_name ASC, affix_analyzed ASC, analysis_level ASC, base_type ASC, rarity ASC"
        in query
        for query in client.queries
    )


@pytest.mark.parametrize(
    ("order", "expected_fragment"),
    [
        (
            "desc",
            "ORDER BY expected_profit DESC, roi DESC, underpriced_rate DESC, items_total DESC, item_name ASC, affix_analyzed ASC, analysis_level ASC, base_type ASC, rarity ASC",
        ),
        (
            "asc",
            "ORDER BY expected_profit ASC, roi ASC, underpriced_rate ASC, items_total ASC, item_name ASC, affix_analyzed ASC, analysis_level ASC, base_type ASC, rarity ASC",
        ),
    ],
)
def test_analytics_pricing_outliers_expected_profit_honors_sort_direction(
    order: str, expected_fragment: str
) -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(
        client,
        query_params={"sort": ["expected_profit"], "order": [order]},
        default_league="Mirage",
    )

    assert any(expected_fragment in query for query in client.queries)


def test_scanner_recommendations_payload_exposes_contract_fields() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"scanner_run_id":"scan-1","strategy_id":"bulk_essence","league":"Mirage",'
                '"recommendation_source":"ml_anomaly","recommendation_contract_version":2,'
                '"producer_version":"mirage-model-v2","producer_run_id":"train-42",'
                '"item_or_market_key":"legacy-key","why_it_fired":"spread>10",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 15c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":5.0,"expected_roi":0.5,"expected_hold_time":"~20m",'
                '"expected_hold_minutes":20.0,"expected_profit_per_minute_chaos":0.25,'
                '"confidence":0.7,"evidence_snapshot":"{\\"search_hint\\":\\"Screaming Essence of Greed\\",\\"item_name\\":\\"Screaming Essence of Greed\\",\\"expected_hold_minutes\\":20,\\"liquidity_score\\":0.8,\\"freshness_minutes\\":3,\\"gold_cost\\":12.5}",'
                '"recorded_at":"2026-03-14 10:00:00"}\n'
            )
        }
    )

    payload = scanner_recommendations_payload(
        client,
        limit=10,
        sort_by="expected_profit_chaos",
        min_confidence=0.65,
        league="Mirage",
        strategy_id="bulk_essence",
    )

    recommendation = payload["recommendations"][0]
    assert payload["meta"]["source"] == "scanner_recommendations"
    assert recommendation["semanticKey"] == (
        "mirage|bulk_essence|manual_trade|screaming essence of greed|"
        "screaming essence of greed|buy <= 10c|10.0|none|list @ 15c"
    )
    assert recommendation["searchHint"] == "Screaming Essence of Greed"
    assert recommendation["itemName"] == "Screaming Essence of Greed"
    assert recommendation["recommendationSource"] == "ml_anomaly"
    assert recommendation["contractVersion"] == 2
    assert recommendation["producerVersion"] == "mirage-model-v2"
    assert recommendation["producerRunId"] == "train-42"
    assert recommendation["expectedHoldMinutes"] == 20
    assert recommendation["expectedProfitChaos"] == 5.0
    assert recommendation["expectedProfitPerMinuteChaos"] == 0.25
    assert recommendation["liquidityScore"] == 0.8
    assert recommendation["freshnessMinutes"] == 3
    assert recommendation["goldCost"] == 12.5
    assert (
        recommendation["evidenceSnapshot"]["search_hint"]
        == "Screaming Essence of Greed"
    )
    assert recommendation["expectedHoldTime"] == "~20m"
    assert recommendation["effectiveConfidence"] == recommendation["confidence"]
    assert recommendation["mlInfluenceScore"] is None
    assert recommendation["mlInfluenceReason"] is None


def test_scanner_recommendations_payload_keeps_legacy_rows_readable() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"scanner_run_id":"scan-legacy","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"legacy-key","why_it_fired":"spread>10",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 15c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":5.0,"expected_roi":0.5,"expected_hold_time":"~20m",'
                '"confidence":0.7,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-14 10:00:00"}\n'
            )
        }
    )

    payload = scanner_recommendations_payload(client)

    recommendation = payload["recommendations"][0]
    assert recommendation["recommendationSource"] == "strategy_pack"
    assert recommendation["contractVersion"] == 1
    assert recommendation["producerVersion"] is None
    assert recommendation["producerRunId"] == "scan-legacy"


def test_scanner_recommendations_payload_nulls_invalid_hold_minutes() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"scanner_run_id":"scan-invalid","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"legacy-invalid","why_it_fired":"spread>10",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 15c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":5.0,"expected_roi":0.5,"expected_hold_time":"soon",'
                '"expected_hold_minutes":null,"expected_profit_per_minute_chaos":null,'
                '"confidence":0.7,"evidence_snapshot":"{\\"expected_hold_minutes\\":0}",'
                '"recorded_at":"2026-03-14 10:00:00"}\n'
            )
        }
    )

    payload = scanner_recommendations_payload(client)

    recommendation = payload["recommendations"][0]
    assert recommendation["expectedHoldTime"] == "soon"
    assert recommendation["expectedHoldMinutes"] is None
    assert recommendation["expectedProfitPerMinuteChaos"] is None


def test_scanner_recommendations_payload_carries_ml_influence_when_present() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"scanner_run_id":"scan-2","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"legacy-key-2","why_it_fired":"spread>10",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 15c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":5.0,"expected_roi":0.5,"expected_hold_time":"~20m",'
                '"confidence":0.4,"evidence_snapshot":"{\\"ml_influence_score\\":0.8,\\"ml_influence_reason\\":\\"mirage_model_v1\\"}",'
                '"recorded_at":"2026-03-14 10:00:00"}\n'
            )
        }
    )

    payload = scanner_recommendations_payload(client)

    recommendation = payload["recommendations"][0]
    assert recommendation["confidence"] == 0.4
    assert recommendation["mlInfluenceScore"] == 0.8
    assert recommendation["mlInfluenceReason"] == "mirage_model_v1"
    assert recommendation["effectiveConfidence"] == 0.6


def test_scanner_recommendations_payload_rejects_invalid_sort() -> None:
    client = _FixtureClickHouse({})

    with pytest.raises(ValueError, match="sort"):
        scanner_recommendations_payload(client, sort_by="not_a_field")


def test_scanner_recommendations_global_top_uses_sql_sort_not_recent_window() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"scanner_run_id":"old-top","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"legacy-old","why_it_fired":"spread",'
                '"buy_plan":"buy <= 20c","max_buy":20.0,"transform_plan":"none",'
                '"exit_plan":"list @ 100c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":80.0,"expected_roi":4.0,"expected_hold_time":"~30m",'
                '"confidence":0.9,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-10 10:00:00"}\n'
                '{"scanner_run_id":"newer-low","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"legacy-new","why_it_fired":"spread",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 12c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":2.0,"expected_roi":0.2,"expected_hold_time":"~5m",'
                '"confidence":0.95,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 10:00:00"}\n'
            )
        }
    )

    payload = scanner_recommendations_payload(
        client,
        sort_by="expected_profit_chaos",
        league="Mirage",
        limit=10,
    )

    assert payload["recommendations"][0]["scannerRunId"] == "old-top"
    assert payload["recommendations"][1]["scannerRunId"] == "newer-low"
    assert "ORDER BY if(isNull(expected_profit_chaos), 0, 1) DESC" in client.queries[0]
    assert "expected_profit_chaos DESC" in client.queries[0]


def test_scanner_recommendations_per_minute_sort_nulls_last() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"scanner_run_id":"fast-win","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"ppm-fast","why_it_fired":"spread",'
                '"buy_plan":"buy <= 5c","max_buy":5.0,"transform_plan":"none",'
                '"exit_plan":"list @ 35c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":30.0,"expected_roi":6.0,"expected_hold_time":"~30m",'
                '"expected_hold_minutes":30.0,"expected_profit_per_minute_chaos":1.0,'
                '"confidence":0.9,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 10:00:00"}\n'
                '{"scanner_run_id":"slow-win","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"ppm-slow","why_it_fired":"spread",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 22c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":12.0,"expected_roi":1.2,"expected_hold_time":"2h",'
                '"expected_hold_minutes":120.0,"expected_profit_per_minute_chaos":0.1,'
                '"confidence":0.8,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 09:00:00"}\n'
                '{"scanner_run_id":"unknown-hold","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"ppm-null","why_it_fired":"spread",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 18c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":8.0,"expected_roi":0.8,"expected_hold_time":"soon",'
                '"expected_hold_minutes":null,"expected_profit_per_minute_chaos":null,'
                '"confidence":0.7,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 08:00:00"}\n'
            )
        }
    )

    payload = scanner_recommendations_payload(
        client,
        sort_by="expected_profit_per_minute_chaos",
        league="Mirage",
        limit=10,
    )

    assert [row["scannerRunId"] for row in payload["recommendations"]] == [
        "fast-win",
        "slow-win",
        "unknown-hold",
    ]
    assert payload["recommendations"][2]["expectedProfitPerMinuteChaos"] is None
    assert (
        "ORDER BY if(isNull(expected_profit_per_minute_chaos), 0, 1) DESC"
        in client.queries[0]
    )
    assert "expected_profit_per_minute_chaos DESC" in client.queries[0]
    assert "AS expected_hold_minutes" in client.queries[0]
    assert "AS expected_profit_per_minute_chaos" in client.queries[0]


def test_scanner_recommendations_filters_are_applied_in_sql_before_limit() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"scanner_run_id":"scan-1","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"legacy-key","why_it_fired":"spread",'
                '"buy_plan":"buy <= 10c","max_buy":10.0,"transform_plan":"none",'
                '"exit_plan":"list @ 15c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":5.0,"expected_roi":0.5,"expected_hold_time":"~20m",'
                '"confidence":0.8,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-14 10:00:00"}\n'
            )
        }
    )

    scanner_recommendations_payload(
        client,
        limit=2,
        sort_by="expected_profit_chaos",
        min_confidence=0.75,
        league="Mirage",
        strategy_id="bulk_essence",
    )

    query = client.queries[0]
    assert "WHERE" in query
    assert "league = 'Mirage'" in query
    assert "strategy_id = 'bulk_essence'" in query
    assert "isNotNull(confidence) AND confidence >= 0.75" in query
    assert "LIMIT 3 FORMAT JSONEachRow" in query


def test_scanner_recommendations_cursor_pagination_has_more_and_next_cursor() -> None:
    client = _SequentialFixtureClickHouse(
        responses=[
            (
                '{"scanner_run_id":"scan-1","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"k1","why_it_fired":"spread",'
                '"buy_plan":"buy <= 1c","max_buy":1.0,"transform_plan":"none",'
                '"exit_plan":"list @ 11c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":11.0,"expected_roi":1.1,"expected_hold_time":"~10m",'
                '"confidence":0.9,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 12:00:00"}\n'
                '{"scanner_run_id":"scan-2","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"k2","why_it_fired":"spread",'
                '"buy_plan":"buy <= 2c","max_buy":2.0,"transform_plan":"none",'
                '"exit_plan":"list @ 10c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":10.0,"expected_roi":1.0,"expected_hold_time":"~10m",'
                '"confidence":0.8,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 11:00:00"}\n'
                '{"scanner_run_id":"scan-3","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"k3","why_it_fired":"spread",'
                '"buy_plan":"buy <= 3c","max_buy":3.0,"transform_plan":"none",'
                '"exit_plan":"list @ 9c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":9.0,"expected_roi":0.9,"expected_hold_time":"~10m",'
                '"confidence":0.7,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 10:00:00"}\n'
            ),
            (
                '{"scanner_run_id":"scan-3","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"k3","why_it_fired":"spread",'
                '"buy_plan":"buy <= 3c","max_buy":3.0,"transform_plan":"none",'
                '"exit_plan":"list @ 9c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":9.0,"expected_roi":0.9,"expected_hold_time":"~10m",'
                '"confidence":0.7,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 10:00:00"}\n'
            ),
        ]
    )

    first_payload = scanner_recommendations_payload(
        client,
        limit=2,
        sort_by="expected_profit_chaos",
        league="Mirage",
    )

    assert first_payload["meta"]["hasMore"] is True
    assert isinstance(first_payload["meta"]["nextCursor"], str)
    assert [row["scannerRunId"] for row in first_payload["recommendations"]] == [
        "scan-1",
        "scan-2",
    ]

    second_payload = scanner_recommendations_payload(
        client,
        limit=2,
        sort_by="expected_profit_chaos",
        league="Mirage",
        cursor=first_payload["meta"]["nextCursor"],
    )

    assert second_payload["meta"]["hasMore"] is False
    assert second_payload["meta"]["nextCursor"] is None
    assert [row["scannerRunId"] for row in second_payload["recommendations"]] == [
        "scan-3"
    ]
    assert "< (" in client.queries[1]


def test_scanner_recommendations_rejects_malformed_cursor() -> None:
    client = _FixtureClickHouse({})

    with pytest.raises(ValueError, match="invalid scanner cursor"):
        scanner_recommendations_payload(
            client,
            sort_by="expected_profit_chaos",
            cursor="not-a-cursor",
        )


def test_scanner_recommendations_rejects_cursor_with_signature_mismatch() -> None:
    client = _SequentialFixtureClickHouse(
        responses=[
            (
                '{"scanner_run_id":"scan-1","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"k1","why_it_fired":"spread",'
                '"buy_plan":"buy <= 1c","max_buy":1.0,"transform_plan":"none",'
                '"exit_plan":"list @ 11c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":11.0,"expected_roi":1.1,"expected_hold_time":"~10m",'
                '"confidence":0.9,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 12:00:00"}\n'
                '{"scanner_run_id":"scan-2","strategy_id":"bulk_essence","league":"Mirage",'
                '"item_or_market_key":"k2","why_it_fired":"spread",'
                '"buy_plan":"buy <= 2c","max_buy":2.0,"transform_plan":"none",'
                '"exit_plan":"list @ 10c","execution_venue":"manual_trade",'
                '"expected_profit_chaos":10.0,"expected_roi":1.0,"expected_hold_time":"~10m",'
                '"confidence":0.8,"evidence_snapshot":"{}",'
                '"recorded_at":"2026-03-15 11:00:00"}\n'
            )
        ]
    )

    first_payload = scanner_recommendations_payload(
        client,
        limit=1,
        sort_by="expected_profit_chaos",
        league="Mirage",
    )

    with pytest.raises(ValueError, match="does not match"):
        scanner_recommendations_payload(
            client,
            limit=2,
            sort_by="expected_profit_chaos",
            league="Mirage",
            cursor=first_payload["meta"]["nextCursor"],
        )


def test_dashboard_payload_sources_from_scanner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FixtureClickHouse({})

    captured_kwargs: dict[str, object] = {}
    mock_opportunities = [{"itemName": "Scanner Item 1"}]
    mock_messages = [{"message": "Message Alert", "severity": "critical"}]

    def _mock_scanner_recommendations(
        _client: ClickHouseClient, **kwargs: object
    ) -> dict[str, object]:
        captured_kwargs.update(kwargs)
        return {
            "recommendations": mock_opportunities,
            "meta": {"hasMore": False, "nextCursor": None},
        }

    monkeypatch.setattr(
        "poe_trade.api.ops.scanner_recommendations_payload",
        _mock_scanner_recommendations,
    )
    monkeypatch.setattr(
        "poe_trade.api.ops.messages_payload",
        lambda _client: mock_messages,
    )

    result = dashboard_payload(client, snapshots=[])

    assert result["topOpportunities"] == mock_opportunities
    assert result["deployment"] == {
        "backendVersion": "0.1.0",
        "backendSha": None,
        "frontendBuildSha": None,
        "recommendationContractVersion": 2,
        "contractMatchState": "unknown",
    }
    assert result["summary"]["criticalAlerts"] == 1
    assert all("message" not in opt for opt in result["topOpportunities"])
    assert captured_kwargs == {
        "limit": 3,
        "sort_by": "expected_profit_per_minute_chaos",
    }


def test_dashboard_payload_summary_excludes_optional_and_oneshot_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FixtureClickHouse({})
    monkeypatch.setattr(
        "poe_trade.api.ops.scanner_recommendations_payload",
        lambda _client, **kwargs: {"recommendations": []},
    )
    monkeypatch.setattr("poe_trade.api.ops.messages_payload", lambda _client: [])
    snapshots = [
        ServiceSnapshot(
            id="clickhouse",
            name="ClickHouse",
            description="",
            status="running",
            uptime=None,
            last_crawl=None,
            rows_in_db=None,
            container_info="clickhouse",
            type="docker",
            allowed_actions=(),
        ),
        ServiceSnapshot(
            id="market_harvester",
            name="Market Harvester",
            description="",
            status="running",
            uptime=None,
            last_crawl=None,
            rows_in_db=None,
            container_info="market_harvester",
            type="crawler",
            allowed_actions=("start", "stop", "restart"),
        ),
        ServiceSnapshot(
            id="scanner_worker",
            name="Scanner Worker",
            description="",
            status="error",
            uptime=None,
            last_crawl=None,
            rows_in_db=None,
            container_info="scanner_worker",
            type="worker",
            allowed_actions=("start", "stop", "restart"),
        ),
        ServiceSnapshot(
            id="ml_trainer",
            name="ML Trainer",
            description="",
            status="running",
            uptime=None,
            last_crawl=None,
            rows_in_db=None,
            container_info="ml_trainer",
            type="worker",
            allowed_actions=("start", "stop", "restart"),
        ),
        ServiceSnapshot(
            id="api",
            name="API",
            description="",
            status="running",
            uptime=None,
            last_crawl=None,
            rows_in_db=None,
            container_info="api",
            type="analytics",
            allowed_actions=(),
        ),
        ServiceSnapshot(
            id="schema_migrator",
            name="Schema Migrator",
            description="",
            status="stopped",
            uptime=None,
            last_crawl=None,
            rows_in_db=None,
            container_info="schema_migrator",
            type="worker",
            allowed_actions=(),
        ),
        ServiceSnapshot(
            id="account_stash_harvester",
            name="Account Stash Harvester",
            description="",
            status="stopped",
            uptime=None,
            last_crawl=None,
            rows_in_db=None,
            container_info="account_stash_harvester",
            type="crawler",
            allowed_actions=("start", "stop", "restart"),
        ),
    ]

    result = dashboard_payload(client, snapshots=snapshots)

    assert result["summary"]["total"] == 5
    assert result["summary"]["running"] == 4
    assert result["summary"]["errors"] == 1


def test_scanner_summary_payload_marks_recent_scan_ok() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"last_run_at":"2099-01-01 00:00:00","recommendation_count":3}\n'
            )
        }
    )

    payload = scanner_summary_payload(client)

    assert payload["status"] == "ok"
    assert payload["lastRunAt"] == "2099-01-01T00:00:00Z"
    assert payload["recommendationCount"] == 3
    assert payload["freshnessMinutes"] == 0.0


def test_scanner_summary_payload_marks_old_scan_stale() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"last_run_at":"2020-01-01 00:00:00","recommendation_count":3}\n'
            )
        }
    )

    payload = scanner_summary_payload(client)

    assert payload["status"] == "stale"
    assert payload["lastRunAt"] == "2020-01-01T00:00:00Z"
    assert payload["recommendationCount"] == 3
    assert isinstance(payload["freshnessMinutes"], float)


def test_scanner_summary_payload_keeps_empty_when_no_runs() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.scanner_recommendations": (
                '{"last_run_at":null,"recommendation_count":0}\n'
            )
        }
    )

    payload = scanner_summary_payload(client)

    assert payload == {
        "status": "empty",
        "lastRunAt": None,
        "recommendationCount": 0,
        "freshnessMinutes": None,
    }
