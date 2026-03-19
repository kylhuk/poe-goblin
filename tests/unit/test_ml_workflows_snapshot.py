from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from poe_trade.db.clickhouse import ClickHouseClient
from poe_trade.ingestion.poeninja_snapshot import PoeNinjaClient
from poe_trade.ml import workflows


class _DummyClient(ClickHouseClient):
    def __init__(self) -> None:
        super().__init__(endpoint="http://localhost:8123")

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        return ""


@pytest.fixture(autouse=True)
def noop_ensures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(
        workflows, "_ensure_raw_poeninja_table", lambda _client, _table: None
    )


class _FixedDatetime(datetime):
    _value: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls._value


def _fake_response() -> SimpleNamespace:
    return SimpleNamespace(
        payload={
            "lines": [
                {
                    "detailsId": "Currency",
                    "currencyTypeName": "Mirror of Kalandra",
                    "chaosEquivalent": 100.0,
                    "count": 1,
                }
            ]
        },
        stale=False,
        reason="test",
    )


def test_snapshot_poeninja_emits_clickhouse_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        workflows,
        "_insert_json_rows",
        lambda _client, _table, rows: captured.extend(rows),
    )
    monkeypatch.setattr(
        PoeNinjaClient,
        "fetch_currency_overview",
        lambda *_args, **_kwargs: _fake_response(),
    )
    fake_dt = datetime(2026, 3, 19, 12, 34, 56, 123456, tzinfo=UTC)
    _FixedDatetime._value = fake_dt
    monkeypatch.setattr(workflows, "datetime", _FixedDatetime)

    workflows.snapshot_poeninja(
        cast(ClickHouseClient, _DummyClient()),
        league="Mirage",
        output_table="tmp",
        max_iterations=1,
    )

    assert captured, "snapshot_poeninja should emit at least one row"
    timestamp = str(captured[0]["sample_time_utc"])
    assert timestamp == "2026-03-19 12:34:56.123"
    assert "+" not in timestamp
    assert "T" not in timestamp


def test_clickhouse_datetime_removes_timezone_suffix() -> None:
    dt = datetime(2026, 3, 19, 14, 15, 16, 654321, tzinfo=UTC)
    formatted = workflows._clickhouse_datetime(dt)
    assert formatted == "2026-03-19 14:15:16.654"
    assert "+" not in formatted
    assert "T" not in formatted
