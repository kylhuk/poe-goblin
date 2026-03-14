from datetime import datetime, timezone
from collections.abc import Mapping

from poe_trade.db import ClickHouseClient, ClickHouseClientError
from poe_trade.ingestion.status import StatusReporter


class _FailingClient(ClickHouseClient):
    def __init__(self, error: Exception):
        super().__init__(endpoint="http://clickhouse")
        self._error = error

    def execute(self, query: str, settings: Mapping[str, str] | None = None) -> str:
        _ = query
        _ = settings
        raise self._error


def _report(reporter: StatusReporter) -> None:
    reporter.report(
        queue_key="psapi:pc",
        feed_kind="psapi",
        contract_version=1,
        league="Synthesis",
        realm="pc",
        cursor="cursor-1",
        next_change_id="cursor-2",
        last_ingest_at=datetime.now(timezone.utc),
        request_rate=1.0,
        status="running",
    )


def test_report_swallows_retryable_clickhouse_errors() -> None:
    reporter = StatusReporter(
        _FailingClient(ClickHouseClientError("timed out", retryable=True)),
        "test",
    )

    _report(reporter)


def test_report_swallows_unexpected_errors() -> None:
    reporter = StatusReporter(
        _FailingClient(RuntimeError("boom")),
        "test",
    )

    _report(reporter)
