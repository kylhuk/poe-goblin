import io
import urllib.error
from email.message import Message

import pytest

from poe_trade.db.clickhouse import ClickHouseClient, ClickHouseClientError


def test_execute_wraps_timeout_as_retryable_clickhouse_error(monkeypatch) -> None:
    client = ClickHouseClient(endpoint="http://clickhouse")

    def _raise_timeout(_request, timeout):
        raise TimeoutError(f"timed out after {timeout}")

    monkeypatch.setattr("urllib.request.urlopen", _raise_timeout)

    with pytest.raises(ClickHouseClientError) as exc_info:
        client.execute("SELECT 1")

    assert exc_info.value.retryable is True
    assert exc_info.value.status_code is None


def test_execute_marks_503_as_retryable(monkeypatch) -> None:
    client = ClickHouseClient(endpoint="http://clickhouse")

    def _raise_http_error(_request, timeout):
        raise urllib.error.HTTPError(
            url="http://clickhouse/",
            code=503,
            msg="service unavailable",
            hdrs=Message(),
            fp=io.BytesIO(b"temporary outage"),
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    with pytest.raises(ClickHouseClientError) as exc_info:
        client.execute("SELECT 1")

    assert exc_info.value.retryable is True
    assert exc_info.value.status_code == 503


def test_execute_marks_400_as_non_retryable(monkeypatch) -> None:
    client = ClickHouseClient(endpoint="http://clickhouse")

    def _raise_http_error(_request, timeout):
        raise urllib.error.HTTPError(
            url="http://clickhouse/",
            code=400,
            msg="bad request",
            hdrs=Message(),
            fp=io.BytesIO(b"syntax error"),
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    with pytest.raises(ClickHouseClientError) as exc_info:
        client.execute("SELECT bad")

    assert exc_info.value.retryable is False
    assert exc_info.value.status_code == 400
