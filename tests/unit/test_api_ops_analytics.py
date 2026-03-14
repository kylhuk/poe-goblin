from __future__ import annotations

from collections.abc import Mapping

from poe_trade.api.ops import analytics_backtests, analytics_report, analytics_scanner
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
