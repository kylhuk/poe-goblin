"""Tests for PoeNinjaClient and PoeNinjaSnapshotScheduler."""

from __future__ import annotations

import json
import logging
import urllib.error
from email.message import Message
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock

import pytest

from poe_trade.ingestion.poeninja_snapshot import (
    PoeNinjaClient,
    PoeNinjaResponse,
    PoeNinjaSnapshotScheduler,
)


class FakeResponse:
    """Mock HTTP response."""

    def __init__(self, body: str, code: int = 200) -> None:
        self._body = body.encode("utf-8")
        self._code = code

    def read(self) -> bytes:
        if self._code >= 400:
            raise urllib.error.HTTPError(
                "url", self._code, "error", Message(), BytesIO(self._body)
            )
        return self._body

    def getcode(self) -> int:
        return self._code

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def _make_payload(lines: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if lines is None:
        lines = [{"currencyTypeName": "Chaos Orb", "chaosEquivalent": 1.0}]
    return {"lines": lines, "currencyDetails": []}


class TestPoeNinjaClient:
    def test_fetch_success_returns_payload(self) -> None:
        payload = _make_payload()
        opener = lambda url, timeout: FakeResponse(json.dumps(payload))
        client = PoeNinjaClient(opener=opener)
        resp = client.fetch_currency_overview("Mirage")
        assert resp.status_code == 200
        assert resp.payload is not None
        assert resp.payload["lines"][0]["currencyTypeName"] == "Chaos Orb"

    def test_fetch_429_returns_fallback(self) -> None:
        opener = lambda url, timeout: FakeResponse("rate limited", code=429)
        client = PoeNinjaClient(opener=opener)
        resp = client.fetch_currency_overview("Mirage")
        assert resp.status_code == 429
        assert resp.reason == "http_429"

    def test_fetch_network_error_returns_empty(self) -> None:
        def failing_opener(url: str, timeout: float) -> FakeResponse:
            raise urllib.error.URLError("connection refused")

        client = PoeNinjaClient(opener=failing_opener)
        resp = client.fetch_currency_overview("Mirage")
        assert resp.status_code == 0
        assert resp.payload is None

    def test_fetch_empty_payload_returns_fallback(self) -> None:
        payload = {"lines": [], "currencyDetails": []}
        opener = lambda url, timeout: FakeResponse(json.dumps(payload))
        client = PoeNinjaClient(opener=opener)
        resp = client.fetch_currency_overview("Mirage")
        assert resp.status_code == 200
        assert resp.reason == "empty"

    def test_cache_hit_on_429(self) -> None:
        payload = _make_payload()
        responses = [
            FakeResponse(json.dumps(payload)),
            FakeResponse("rate limited", code=429),
        ]
        call_count = [0]

        def opener(url: str, timeout: float) -> FakeResponse:
            resp = responses[call_count[0]]
            call_count[0] += 1
            return resp

        client = PoeNinjaClient(opener=opener, cache_ttl=180.0)
        # First call succeeds and caches
        resp1 = client.fetch_currency_overview("Mirage")
        assert resp1.status_code == 200
        # Second call gets 429 but returns cached
        resp2 = client.fetch_currency_overview("Mirage")
        assert resp2.status_code == 429
        assert resp2.stale is True
        assert resp2.payload is not None

    def test_fetch_http_error_logs_warning(self, caplog) -> None:
        """Test that HTTP errors are logged at WARNING level."""
        opener = lambda url, timeout: FakeResponse("not found", code=404)
        client = PoeNinjaClient(opener=opener)
        with caplog.at_level(logging.WARNING):
            resp = client.fetch_currency_overview("Mirage")
            assert resp.status_code == 404
            # Check that a WARNING was logged
            assert any(
                "poe.ninja request failed" in record.message and record.levelno == logging.WARNING
                for record in caplog.records
            )

    def test_fetch_network_error_logs_error(self, caplog) -> None:
        """Test that network errors are logged at ERROR level."""
        def failing_opener(url: str, timeout: float) -> FakeResponse:
            raise urllib.error.URLError("connection refused")

        client = PoeNinjaClient(opener=failing_opener)
        with caplog.at_level(logging.ERROR):
            resp = client.fetch_currency_overview("Mirage")
            assert resp.status_code == 0
            # Check that an ERROR was logged
            assert any(
                "poe.ninja request failed" in record.message and record.levelno == logging.ERROR
                for record in caplog.records
            )

    def test_fetch_invalid_json_logs_warning(self, caplog) -> None:
        """Test that invalid JSON responses are logged at WARNING level."""
        opener = lambda url, timeout: FakeResponse("invalid json", code=200)
        client = PoeNinjaClient(opener=opener)
        with caplog.at_level(logging.WARNING):
            resp = client.fetch_currency_overview("Mirage")
            assert resp.status_code == 200
            assert resp.reason == "empty"
            # Check that a WARNING was logged
            assert any(
                "poe.ninja league=" in record.message and "returned invalid JSON" in record.message and record.levelno == logging.WARNING
                for record in caplog.records
            )


class TestPoeNinjaSnapshotScheduler:
    def test_init_deduplicates_leagues(self) -> None:
        client = PoeNinjaClient(opener=lambda url, timeout: FakeResponse("{}"))
        scheduler = PoeNinjaSnapshotScheduler(client, ["Mirage", "Mirage", "Standard"])
        assert scheduler._leagues == ("Mirage", "Standard")

    def test_next_due_returns_first_league(self) -> None:
        client = PoeNinjaClient(opener=lambda url, timeout: FakeResponse("{}"))
        clock_time = [1000.0]
        scheduler = PoeNinjaSnapshotScheduler(
            client, ["Mirage", "Standard"], clock=lambda: clock_time[0]
        )
        league, due = scheduler.next_due()
        assert league == "Mirage"
        assert due == 0.0  # Relative time from now

    def test_empty_leagues_raises(self) -> None:
        client = PoeNinjaClient(opener=lambda url, timeout: FakeResponse("{}"))
        scheduler = PoeNinjaSnapshotScheduler(client, [])
        with pytest.raises(RuntimeError, match="no leagues configured"):
            scheduler.next_due()
