from types import SimpleNamespace

import pytest

from poe_trade.db import ClickHouseClientError
from poe_trade.services import scanner_worker


class _DummyClickHouseClient:
    @classmethod
    def from_env(cls, _url: str):
        return cls()

    def execute(self, _query: str) -> str:
        raise AssertionError(
            "scanner_worker should not write status directly via execute"
        )


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        api_league_allowlist=("Mirage",),
        scan_minutes=0.01,
        clickhouse_url="http://clickhouse",
    )


def test_main_returns_retryable_failure_in_once_mode(monkeypatch) -> None:
    monkeypatch.setattr(scanner_worker.config_settings, "get_settings", _settings)
    monkeypatch.setattr(scanner_worker, "ClickHouseClient", _DummyClickHouseClient)
    monkeypatch.setattr(
        scanner_worker,
        "StatusReporter",
        lambda *_args, **_kwargs: SimpleNamespace(report=lambda **_kw: None),
    )

    def _raise_transient(_client, *, league, dry_run=False):
        raise ClickHouseClientError("timeout", retryable=True)

    monkeypatch.setattr(scanner_worker.scanner, "run_scan_once", _raise_transient)

    result = scanner_worker.main(["--once"])

    assert result == 1


def test_main_raises_non_retryable_clickhouse_error(monkeypatch) -> None:
    monkeypatch.setattr(scanner_worker.config_settings, "get_settings", _settings)
    monkeypatch.setattr(scanner_worker, "ClickHouseClient", _DummyClickHouseClient)
    monkeypatch.setattr(
        scanner_worker,
        "StatusReporter",
        lambda *_args, **_kwargs: SimpleNamespace(report=lambda **_kw: None),
    )

    def _raise_non_retryable(_client, *, league, dry_run=False):
        raise ClickHouseClientError("bad query", retryable=False, status_code=400)

    monkeypatch.setattr(scanner_worker.scanner, "run_scan_once", _raise_non_retryable)

    with pytest.raises(ClickHouseClientError, match="bad query"):
        scanner_worker.main(["--once"])


def test_main_uses_status_reporter_for_heartbeat(monkeypatch) -> None:
    reports: list[dict[str, object]] = []

    class _RecordingStatusReporter:
        def __init__(self, _client, _source: str) -> None:
            pass

        def report(self, **kwargs) -> None:
            reports.append(kwargs)

    monkeypatch.setattr(scanner_worker.config_settings, "get_settings", _settings)
    monkeypatch.setattr(scanner_worker, "ClickHouseClient", _DummyClickHouseClient)
    monkeypatch.setattr(scanner_worker, "StatusReporter", _RecordingStatusReporter)
    monkeypatch.setattr(
        scanner_worker.scanner,
        "run_scan_once",
        lambda _client, *, league, dry_run=False: "scan-123",
    )

    result = scanner_worker.main(["--once", "--league", "Mirage", "--dry-run"])

    assert result == 0
    assert len(reports) == 1
    assert reports[0]["queue_key"] == "scanner:worker"
    assert reports[0]["next_change_id"] == "scan-123"
