from __future__ import annotations

from collections.abc import Mapping

from poe_trade.analytics.reports import daily_report
from poe_trade.db import ClickHouseClient


class _RecordingClickHouse(ClickHouseClient):
    def __init__(self, payload: str) -> None:
        super().__init__(endpoint="http://clickhouse")
        self.payload: str = payload
        self.queries: list[str] = []

    def execute(  # pyright: ignore[reportImplicitOverride]
        self, query: str, settings: Mapping[str, str] | None = None
    ) -> str:
        del settings
        self.queries.append(query)
        return self.payload


def test_daily_report_queries_backtest_and_gold_reference_totals() -> None:
    client = _RecordingClickHouse(
        "".join(
            [
                '{"league":"Mirage","recommendations":1,"alerts":2,',
                '"journal_events":3,"journal_positions":4,',
                '"backtest_summary_rows":5,"backtest_detail_rows":6,',
                '"gold_currency_ref_hour_rows":7,"gold_listing_ref_hour_rows":8,',
                '"gold_liquidity_ref_hour_rows":9,"gold_bulk_premium_hour_rows":10,',
                '"gold_set_ref_hour_rows":11,"realized_pnl_chaos":12.5}\n',
            ]
        )
    )

    report = daily_report(client, league="Mirage")

    assert report["league"] == "Mirage"
    assert report["backtest_summary_rows"] == 5
    assert report["backtest_detail_rows"] == 6
    assert report["gold_currency_ref_hour_rows"] == 7
    assert report["gold_set_ref_hour_rows"] == 11
    assert report["realized_pnl_chaos"] == 12.5

    assert len(client.queries) == 1
    query = client.queries[0]
    assert "poe_trade.research_backtest_summary" in query
    assert "poe_trade.research_backtest_detail" in query
    assert "poe_trade.gold_currency_ref_hour" in query
    assert "poe_trade.gold_listing_ref_hour" in query
    assert "poe_trade.gold_liquidity_ref_hour" in query
    assert "poe_trade.gold_bulk_premium_hour" in query
    assert "poe_trade.gold_set_ref_hour" in query


def test_daily_report_returns_zeroed_contract_when_backend_payload_is_empty() -> None:
    client = _RecordingClickHouse("")

    report = daily_report(client, league="Mirage")

    assert report == {
        "league": "Mirage",
        "recommendations": 0,
        "alerts": 0,
        "journal_events": 0,
        "journal_positions": 0,
        "backtest_summary_rows": 0,
        "backtest_detail_rows": 0,
        "gold_currency_ref_hour_rows": 0,
        "gold_listing_ref_hour_rows": 0,
        "gold_liquidity_ref_hour_rows": 0,
        "gold_bulk_premium_hour_rows": 0,
        "gold_set_ref_hour_rows": 0,
        "realized_pnl_chaos": 0.0,
    }


def test_daily_report_escapes_league_literal_in_query() -> None:
    client = _RecordingClickHouse(
        """{"league":"Mirage' OR 1=1","recommendations":0,"alerts":0,"journal_events":0,"journal_positions":0,"backtest_summary_rows":0,"backtest_detail_rows":0,"gold_currency_ref_hour_rows":0,"gold_listing_ref_hour_rows":0,"gold_liquidity_ref_hour_rows":0,"gold_bulk_premium_hour_rows":0,"gold_set_ref_hour_rows":0,"realized_pnl_chaos":0.0}\n"""
    )

    report = daily_report(client, league="Mirage' OR 1=1")

    assert report["league"] == "Mirage' OR 1=1"
    assert "Mirage'' OR 1=1" in client.queries[0]
