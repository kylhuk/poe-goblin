from __future__ import annotations

import json
import os
from io import BytesIO
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

import pytest

from poe_trade.api import app as app_module
from poe_trade.api.app import ApiApp
from poe_trade.api.app import start_stash_valuations_refresh
from poe_trade.api.responses import ApiError
from poe_trade.api.valuation import (
    _build_stash_item_valuation,
    build_stash_scan_valuations_payload,
)
from poe_trade.config.settings import Settings
from poe_trade.db import ClickHouseClient


def _settings_with_stash_enabled() -> Settings:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_API_CORS_ORIGINS": "https://app.example.com",
        "POE_API_MAX_BODY_BYTES": "32768",
        "POE_API_LEAGUE_ALLOWLIST": "Mirage",
        "POE_ENABLE_ACCOUNT_STASH": "true",
        "POE_ML_AUTOMATION_ENABLED": "true",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        return Settings.from_env()


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer phase1-token",
        "Origin": "https://app.example.com",
    }


def _connected_session(session_id: str) -> dict[str, str]:
    return {
        "session_id": session_id,
        "status": "connected",
        "account_name": "qa-exile",
        "expires_at": "2099-01-01T00:00:00Z",
    }


def _request_body(**overrides: object) -> bytes:
    body: dict[str, object] = {
        "scanId": "scan-1",
        "itemId": "item-1",
        "structuredMode": False,
        "minThreshold": 10,
        "maxThreshold": 50,
        "maxAgeDays": 30,
    }
    for key, value in overrides.items():
        body[key] = value
    return json.dumps(body).encode("utf-8")


def _request_headers(body: bytes) -> dict[str, str]:
    return {
        **_auth_headers(),
        "Cookie": "poe_session=test-session",
        "Content-Length": str(len(body)),
    }


@pytest.fixture(autouse=True)
def _neutralize_persisted_active_scan_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("poe_trade.api.app.fetch_active_scan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_valuation_refresh",
        lambda *_args, **_kwargs: None,
    )


def test_stash_scan_valuations_route_returns_single_item_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update(kwargs)
            or {
                "structuredMode": False,
                "stashId": "scan-1",
                "itemId": "item-1",
                "scanDatetime": "2026-03-21T12:00:00Z",
                "chaosMedian": 42.0,
                "daySeries": [
                    {"date": "2026-03-12", "chaosMedian": None},
                    {"date": "2026-03-13", "chaosMedian": 42.0},
                ],
                "priceBand": "good",
                "priceEvaluation": "well_priced",
                "items": [
                    {
                        "stashId": "scan-1",
                        "itemId": "item-1",
                        "scanDatetime": "2026-03-21T12:00:00Z",
                        "chaosMedian": 42.0,
                        "daySeries": [
                            {"date": "2026-03-12", "chaosMedian": None},
                            {"date": "2026-03-13", "chaosMedian": 42.0},
                        ],
                    }
                ],
            }
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    body = _request_body()
    response = app.handle(
        method="POST",
        raw_path="/api/v1/stash/scan/valuations?league=Mirage&realm=pc",
        headers=_request_headers(body),
        body_reader=BytesIO(body),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["structuredMode"] is False
    assert body["items"][0]["itemId"] == "item-1"
    assert body["priceBand"] == "good"
    assert body["priceEvaluation"] == "well_priced"
    assert captured == {
        "account_name": "qa-exile",
        "league": "Mirage",
        "realm": "pc",
        "scan_id": "scan-1",
        "item_id": "item-1",
        "structured_mode": False,
        "min_threshold": 10.0,
        "max_threshold": 50.0,
        "max_age_days": 30,
    }


def test_stash_scan_valuations_route_accepts_stash_id_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update(kwargs)
            or {
                "structuredMode": False,
                "scanId": "scan-1",
                "stashId": "scan-1",
                "itemId": "item-1",
                "scanDatetime": "2026-03-21T12:00:00Z",
                "chaosMedian": 42.0,
                "daySeries": [],
                "items": [],
                "priceBand": "good",
            }
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    body = json.dumps(
        {
            "stashId": "scan-1",
            "itemId": "item-1",
            "structuredMode": False,
            "minThreshold": 10,
            "maxThreshold": 50,
            "maxAgeDays": 30,
        }
    ).encode("utf-8")
    response = app.handle(
        method="POST",
        raw_path="/api/v1/stash/scan/valuations?league=Mirage&realm=pc",
        headers=_request_headers(body),
        body_reader=BytesIO(body),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["scanId"] == "scan-1"
    assert body["stashId"] == "scan-1"
    assert captured["scan_id"] == "scan-1"


def test_stash_scan_valuations_latest_result_route_uses_latest_published_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update(kwargs)
            or {
                "structuredMode": True,
                "scanId": "scan-1",
                "stashId": "scan-1",
                "itemId": None,
                "scanDatetime": None,
                "chaosMedian": None,
                "daySeries": [],
                "items": [],
            }
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    response = app.handle(
        method="GET",
        raw_path="/api/v1/stash/scan/valuations/result",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": "poe_session=test-session",
        },
        body_reader=BytesIO(b""),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["structuredMode"] is True
    assert captured == {
        "account_name": "qa-exile",
        "league": "Mirage",
        "realm": "pc",
    }


def test_stash_scan_valuations_status_route_translates_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            app_module.StashScanBackendUnavailable("down")
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/status",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"
    assert exc.value.message == "backend unavailable"


def test_stash_scan_valuations_result_route_translates_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(app_module.StashBackendUnavailable("down")),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"
    assert exc.value.message == "backend unavailable"


def test_stash_scan_valuations_result_route_translates_lookup_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    latest_payload = mock.Mock(side_effect=AssertionError("unexpected payload lookup"))

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            app_module.StashScanBackendUnavailable("down")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        latest_payload,
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"
    assert exc.value.message == "backend unavailable"
    assert latest_payload.call_count == 0


def test_stash_scan_valuations_start_route_translates_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    class _FakeHarvester:
        pass

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app._load_private_stash_token_state",
        lambda _settings, _account_name: ({"status": "connected"}, "token-123"),
    )
    monkeypatch.setattr(
        "poe_trade.api.app._build_private_stash_harvester",
        lambda *args, **kwargs: _FakeHarvester(),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            app_module.StashScanBackendUnavailable("down")
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/stash/scan/valuations/start",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"
    assert exc.value.message == "backend unavailable"


def test_stash_scan_valuations_status_route_requires_stash_feature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected")),
    )
    with mock.patch.dict(
        os.environ,
        {
            "POE_API_OPERATOR_TOKEN": "phase1-token",
            "POE_API_CORS_ORIGINS": "https://app.example.com",
            "POE_API_MAX_BODY_BYTES": "32768",
            "POE_API_LEAGUE_ALLOWLIST": "Mirage",
            "POE_ENABLE_ACCOUNT_STASH": "false",
            "POE_ML_AUTOMATION_ENABLED": "true",
        },
        clear=True,
    ):
        app = ApiApp(
            Settings.from_env(),
            clickhouse_client=ClickHouseClient(endpoint="http://ch"),
        )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/status",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "feature_unavailable"
    assert exc.value.message == "stash feature is unavailable; set POE_ENABLE_ACCOUNT_STASH=true"


def test_stash_scan_valuations_result_route_requires_stash_feature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected")),
    )
    with mock.patch.dict(
        os.environ,
        {
            "POE_API_OPERATOR_TOKEN": "phase1-token",
            "POE_API_CORS_ORIGINS": "https://app.example.com",
            "POE_API_MAX_BODY_BYTES": "32768",
            "POE_API_LEAGUE_ALLOWLIST": "Mirage",
            "POE_ENABLE_ACCOUNT_STASH": "false",
            "POE_ML_AUTOMATION_ENABLED": "true",
        },
        clear=True,
    ):
        app = ApiApp(
            Settings.from_env(),
            clickhouse_client=ClickHouseClient(endpoint="http://ch"),
        )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "feature_unavailable"
    assert exc.value.message == "stash feature is unavailable; set POE_ENABLE_ACCOUNT_STASH=true"


def test_stash_scan_valuations_status_route_uses_account_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: None,
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_valuation_refresh_status_payload",
        lambda _client, **kwargs: (
            captured.update(kwargs)
            or {
                "status": "idle",
                "activeScanId": None,
                "publishedScanId": None,
                "startedAt": None,
                "updatedAt": None,
                "publishedAt": None,
                "progress": {
                    "tabsTotal": 0,
                    "tabsProcessed": 0,
                    "itemsTotal": 0,
                    "itemsProcessed": 0,
                },
                "error": None,
            }
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    response = app.handle(
        method="GET",
        raw_path="/api/v1/stash/scan/valuations/status",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": "poe_session=test-session",
        },
        body_reader=BytesIO(b""),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["status"] == "idle"
    assert captured == {
        "account_name": "qa-exile",
        "league": "Mirage",
        "realm": "pc",
        "published_scan_id": None,
        "stale_timeout_seconds": app.settings.account_stash_scan_stale_timeout_seconds,
    }


def test_stash_scan_valuations_start_payload_exposes_refresh_lifecycle_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    class _ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            return None

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda *_args, **_kwargs: {
            "status": "published",
            "scanId": "scan-2",
            "startedAt": "2026-03-21T12:10:00Z",
            "publishedAt": "2026-03-21T12:11:00Z",
        },
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _ImmediateThread)

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload["scanKind"] == "valuation_refresh"
        assert payload["sourceScanId"] == "scan-1"
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)


def test_start_stash_valuations_refresh_ignores_ordinary_active_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    captured: dict[str, object] = {}

    class _DeferredThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon
            captured["thread_started"] = False

        def start(self) -> None:
            captured["thread_started"] = True
            captured["thread_target"] = self._target

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_scan",
        lambda _client, **kwargs: {
            "scanId": "scan-ordinary",
            "isActive": True,
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:02:00Z",
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_valuation_refresh",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "poe_trade.api.app.uuid.uuid4",
        lambda: type("U", (), {"hex": "scan-new"})(),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda _client, **kwargs: (
            captured.update({"run_refresh": kwargs})
            or {
                "scanId": kwargs["scan_id"],
                "status": "published",
                "startedAt": kwargs["started_at"],
                "publishedAt": "2026-03-21T12:02:00Z",
                "accountName": "qa-exile",
                "league": kwargs["league"],
                "realm": kwargs["realm"],
            }
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update({"latest_payload": kwargs})
            or {
                "structuredMode": True,
                "scanId": captured.get("run_refresh", {}).get("scan_id", "scan-new"),
                "stashId": captured.get("run_refresh", {}).get("scan_id", "scan-new"),
                "itemId": None,
                "scanDatetime": None,
                "chaosMedian": None,
                "daySeries": [],
                "items": [],
            }
        ),
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _DeferredThread)

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload["status"] == "running"
        assert payload["activeScanId"] == "scan-new"
        assert payload.get("deduplicated") is not True
        assert captured["thread_started"] is True
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_start_stash_valuations_refresh_ignores_refresh_for_older_source_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    captured: dict[str, object] = {}

    class _DeferredThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon
            captured["thread_started"] = False

        def start(self) -> None:
            captured["thread_started"] = True
            captured["thread_target"] = self._target

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-current",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_scan",
        lambda _client, **kwargs: {
            "scanId": "scan-old",
            "isActive": True,
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:02:00Z",
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_valuation_refresh",
        lambda _client, **kwargs: None,
    )
    monkeypatch.setattr(
        "poe_trade.api.app.uuid.uuid4",
        lambda: type("U", (), {"hex": "scan-next"})(),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda _client, **kwargs: (
            captured.update({"run_refresh": kwargs})
            or {
                "scanId": kwargs["scan_id"],
                "status": "published",
                "startedAt": kwargs["started_at"],
                "publishedAt": "2026-03-21T12:02:00Z",
                "accountName": "qa-exile",
                "league": kwargs["league"],
                "realm": kwargs["realm"],
            }
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update({"latest_payload": kwargs})
            or {
                "structuredMode": True,
                "scanId": captured.get("run_refresh", {}).get("scan_id", "scan-next"),
                "stashId": captured.get("run_refresh", {}).get("scan_id", "scan-next"),
                "itemId": None,
                "scanDatetime": None,
                "chaosMedian": None,
                "daySeries": [],
                "items": [],
            }
        ),
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _DeferredThread)

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload["status"] == "running"
        assert payload["activeScanId"] == "scan-next"
        assert payload["publishedScanId"] == "scan-current"
        assert payload.get("deduplicated") is not True
        assert captured["thread_started"] is True
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_start_stash_valuations_refresh_evicts_stale_pending_cache_after_published_scan_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS[scope] = {
        "status": "running",
        "activeScanId": "scan-old",
        "publishedScanId": "scan-old",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:00:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }

    captured: dict[str, object] = {}

    class _DeferredThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon
            captured["thread_started"] = False

        def start(self) -> None:
            captured["thread_started"] = True
            captured["thread_target"] = self._target

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-current",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_valuation_refresh",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "poe_trade.api.app.uuid.uuid4",
        lambda: type("U", (), {"hex": "scan-next"})(),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda _client, **kwargs: (
            captured.update({"run_refresh": kwargs})
            or {
                "scanId": kwargs["scan_id"],
                "status": "published",
                "startedAt": kwargs["started_at"],
                "publishedAt": "2026-03-21T12:02:00Z",
                "accountName": "qa-exile",
                "league": kwargs["league"],
                "realm": kwargs["realm"],
            }
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update({"latest_payload": kwargs})
            or {
                "structuredMode": True,
                "scanId": captured.get("run_refresh", {}).get("scan_id", "scan-next"),
                "stashId": captured.get("run_refresh", {}).get("scan_id", "scan-next"),
                "itemId": None,
                "scanDatetime": None,
                "chaosMedian": None,
                "daySeries": [],
                "items": [],
            }
        ),
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _DeferredThread)

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload["status"] == "running"
        assert payload["activeScanId"] == "scan-next"
        assert payload["sourceScanId"] == "scan-current"
        assert payload["publishedScanId"] == "scan-current"
        assert payload.get("deduplicated") is not True
        assert captured["thread_started"] is True
        assert app_module._PENDING_STASH_VALUATIONS[scope]["sourceScanId"] == "scan-current"
        assert app_module._PENDING_STASH_VALUATIONS[scope]["publishedScanId"] == "scan-current"
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["sourceScanId"] == "scan-current"
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["publishedScanId"] == "scan-current"
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_start_stash_valuations_refresh_rechecks_published_scan_after_lock_before_reusing_pending_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS[scope] = {
        "status": "running",
        "activeScanId": "scan-old-refresh",
        "sourceScanId": "scan-old",
        "publishedScanId": "scan-old",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:00:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }

    captured: dict[str, object] = {"thread_started": False, "published_scan_ids": []}

    class _DeferredThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            captured["thread_started"] = True
            captured["thread_target"] = self._target

    published_scan_ids = iter(["scan-old", "scan-current"])

    def _fetch_published_scan_id(
        _client, *, account_name: str, league: str, realm: str
    ) -> str:
        del account_name, league, realm
        published_scan_id = next(published_scan_ids)
        seen_ids = captured["published_scan_ids"]
        assert isinstance(seen_ids, list)
        seen_ids.append(published_scan_id)
        return published_scan_id

    monkeypatch.setattr("poe_trade.api.app.fetch_published_scan_id", _fetch_published_scan_id)
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_valuation_refresh",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "poe_trade.api.app.uuid.uuid4",
        lambda: type("U", (), {"hex": "scan-next"})(),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda _client, **kwargs: {
            "scanId": kwargs["scan_id"],
            "status": "published",
            "startedAt": kwargs["started_at"],
            "publishedAt": "2026-03-21T12:02:00Z",
            "accountName": "qa-exile",
            "league": kwargs["league"],
            "realm": kwargs["realm"],
        },
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _DeferredThread)

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload["status"] == "running"
        assert payload["activeScanId"] == "scan-next"
        assert payload["sourceScanId"] == "scan-current"
        assert payload["publishedScanId"] == "scan-current"
        assert payload.get("deduplicated") is not True
        assert captured["thread_started"] is True
        assert captured["published_scan_ids"] == ["scan-old", "scan-current"]
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_stash_scan_valuations_status_route_ignores_ordinary_active_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_valuation_refresh_status_payload",
        lambda _client, **kwargs: {
            "status": "idle",
            "activeScanId": None,
            "publishedScanId": kwargs["published_scan_id"],
            "startedAt": None,
            "updatedAt": None,
            "publishedAt": None,
            "progress": {
                "tabsTotal": 0,
                "tabsProcessed": 0,
                "itemsTotal": 0,
                "itemsProcessed": 0,
            },
            "error": None,
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app.stash_scan_status_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generic stash status must not be used")
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    response = app.handle(
        method="GET",
        raw_path="/api/v1/stash/scan/valuations/status",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": "poe_session=test-session",
        },
        body_reader=BytesIO(b""),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["status"] == "idle"
    assert body["publishedScanId"] == "scan-1"


def test_stash_scan_valuations_status_route_evicts_stale_pending_refresh_after_published_scan_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS[scope] = {
        "status": "running",
        "activeScanId": "scan-old",
        "publishedScanId": "scan-old",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:00:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-current",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_valuation_refresh_status_payload",
        lambda _client, **kwargs: {
            "status": "idle",
            "activeScanId": None,
            "publishedScanId": kwargs["published_scan_id"],
            "startedAt": None,
            "updatedAt": None,
            "publishedAt": None,
            "progress": {
                "tabsTotal": 0,
                "tabsProcessed": 0,
                "itemsTotal": 0,
                "itemsProcessed": 0,
            },
            "error": None,
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app.stash_scan_status_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generic stash status must not be used")
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    response = app.handle(
        method="GET",
        raw_path="/api/v1/stash/scan/valuations/status",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": "poe_session=test-session",
        },
        body_reader=BytesIO(b""),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["status"] == "idle"
    assert body["publishedScanId"] == "scan-current"
    assert scope not in app_module._PENDING_STASH_VALUATIONS


def test_stash_scan_valuations_status_route_ignores_refresh_for_older_source_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-current",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_valuation_refresh_status_payload",
        lambda _client, **kwargs: {
            "status": "idle",
            "activeScanId": None,
            "publishedScanId": kwargs["published_scan_id"],
            "startedAt": None,
            "updatedAt": None,
            "publishedAt": None,
            "progress": {
                "tabsTotal": 0,
                "tabsProcessed": 0,
                "itemsTotal": 0,
                "itemsProcessed": 0,
            },
            "error": None,
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app.stash_scan_status_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generic stash status must not be used")
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    response = app.handle(
        method="GET",
        raw_path="/api/v1/stash/scan/valuations/status",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": "poe_session=test-session",
        },
        body_reader=BytesIO(b""),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["status"] == "idle"
    assert body["publishedScanId"] == "scan-current"


def test_stash_scan_valuations_status_route_prefers_persisted_running_progress_over_pending_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS[scope] = {
        "status": "running",
        "activeScanId": "scan-pending",
        "sourceScanId": "scan-1",
        "publishedScanId": "scan-1",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:00:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }

    persisted_payload = {
        "status": "running",
        "scanKind": "valuation_refresh",
        "activeScanId": "scan-persisted",
        "sourceScanId": "scan-1",
        "publishedScanId": "scan-1",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:04:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 2,
            "tabsProcessed": 1,
            "itemsTotal": 5,
            "itemsProcessed": 3,
        },
        "error": None,
    }
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_valuation_refresh_status_payload",
        lambda _client, **kwargs: captured.update(kwargs) or persisted_payload,
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/status",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
            },
            body_reader=BytesIO(b""),
        )

        body = json.loads(response.body.decode("utf-8"))
        assert response.status == 200
        assert body == persisted_payload
        assert captured == {
            "account_name": "qa-exile",
            "league": "Mirage",
            "realm": "pc",
            "published_scan_id": "scan-1",
            "stale_timeout_seconds": app.settings.account_stash_scan_stale_timeout_seconds,
        }
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)


def test_stash_scan_valuations_status_route_recovers_published_refresh_after_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS[scope] = {
        "status": "running",
        "activeScanId": "scan-old",
        "publishedScanId": "scan-old",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:00:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }
    app_module._LATEST_STASH_VALUATION_STATUS[scope] = {
        "status": "published",
        "activeScanId": None,
        "publishedScanId": "scan-old",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:03:00Z",
        "publishedAt": "2026-03-21T12:03:00Z",
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }
    app_module._LATEST_STASH_VALUATION_RESULTS[scope] = {
        "structuredMode": True,
        "scanId": "scan-old",
        "stashId": "scan-old",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }

    class _QueryAwareClickHouse(ClickHouseClient):
        def __init__(self, payloads: list[str]) -> None:
            super().__init__(endpoint="http://ch")
            self._payloads = list(payloads)
            self.queries: list[str] = []
            self._scan_run_queries = 0
            self._active_scan_queries = 0

        def execute(  # pyright: ignore[reportImplicitOverride]
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_published_scans" in query:
                return self._payloads[0]
            if "account_stash_active_scans" in query:
                self._active_scan_queries += 1
                return self._payloads[1]
            if "account_stash_scan_runs" in query:
                self._scan_run_queries += 1
                if self._scan_run_queries == 1:
                    return self._payloads[2]
                return self._payloads[3]
            return ""

    client = _QueryAwareClickHouse(
        payloads=[
            '{"scan_id":"scan-2"}\n',
            "",
            "",
            '{"scan_id":"scan-2","source_scan_id":"scan-1","status":"published","started_at":"2026-03-21T12:01:00Z","updated_at":"2026-03-21T12:03:00Z","published_at":"2026-03-21T12:03:00Z","tabs_total":2,"tabs_processed":2,"items_total":5,"items_processed":5,"error_message":""}\n',
        ]
    )

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=client,
    )

    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    response = app.handle(
        method="GET",
        raw_path="/api/v1/stash/scan/valuations/status",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": "poe_session=test-session",
        },
        body_reader=BytesIO(b""),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["status"] == "published"
    assert body["scanKind"] == "valuation_refresh"
    assert body["activeScanId"] is None
    assert body["sourceScanId"] == "scan-1"
    assert body["publishedScanId"] == "scan-2"
    assert body["publishedAt"] == "2026-03-21T12:03:00Z"
    assert scope not in app_module._PENDING_STASH_VALUATIONS
    assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["publishedScanId"] == "scan-2"
    assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["sourceScanId"] == "scan-1"
    assert scope not in app_module._LATEST_STASH_VALUATION_RESULTS
    stash_queries = [query for query in client.queries if "account_stash" in query]
    assert len(stash_queries) == 4
    assert "scan_kind = 'valuation_refresh'" in stash_queries[1]
    assert "source_scan_id = 'scan-2'" in stash_queries[1]
    assert "scan_kind = 'valuation_refresh'" in stash_queries[3]
    assert "AND scan_id = 'scan-2'" in stash_queries[3]


def test_stash_scan_valuations_start_route_uses_persisted_refresh_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.start_stash_valuations_refresh",
        lambda settings, _client, *, account_name, league, realm: (
            captured.update(
                {
                    "settings": settings,
                    "account_name": account_name,
                    "league": league,
                    "realm": realm,
                }
            )
            or {
                "status": "running",
                "activeScanId": "scan-2",
                "publishedScanId": "scan-1",
                "startedAt": "2026-03-21T12:00:00Z",
                "updatedAt": "2026-03-21T12:00:00Z",
                "publishedAt": None,
                "progress": {
                    "tabsTotal": 0,
                    "tabsProcessed": 0,
                    "itemsTotal": 0,
                    "itemsProcessed": 0,
                },
                "error": None,
            }
        ),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    response = app.handle(
        method="POST",
        raw_path="/api/v1/stash/scan/valuations/start",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": "poe_session=test-session",
            "Content-Length": "0",
        },
        body_reader=BytesIO(b""),
    )

    assert response.status == 202
    assert json.loads(response.body.decode("utf-8"))["activeScanId"] == "scan-2"
    assert captured == {
        "settings": app.settings,
        "account_name": "qa-exile",
        "league": "Mirage",
        "realm": "pc",
    }


def test_start_stash_valuations_refresh_uses_persisted_rows_without_oauth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    captured: dict[str, object] = {}

    class _DeferredThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon
            captured["thread_started"] = False

        def start(self) -> None:
            captured["thread_started"] = True
            captured["thread_target"] = self._target

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app._load_private_stash_token_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oauth token loader should not be used")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app._build_private_stash_harvester",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("private harvester should not be built")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda _client, **kwargs: (
            captured.update({"run_refresh": kwargs})
            or {
                "scanId": kwargs["scan_id"],
                "status": "published",
                "startedAt": kwargs["started_at"],
                "publishedAt": "2026-03-21T12:02:00Z",
                "accountName": "qa-exile",
                "league": kwargs["league"],
                "realm": kwargs["realm"],
            }
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update({"latest_payload": kwargs})
            or {
                "structuredMode": True,
                "scanId": captured.get("run_refresh", {}).get("scan_id", "scan-2"),
                "stashId": captured.get("run_refresh", {}).get("scan_id", "scan-2"),
                "itemId": None,
                "scanDatetime": None,
                "chaosMedian": None,
                "daySeries": [],
                "items": [],
            }
        ),
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _DeferredThread)

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload["status"] == "running"
        assert payload["activeScanId"] != "scan-1"
        assert payload["sourceScanId"] == "scan-1"
        assert payload["publishedScanId"] == "scan-1"
        assert captured["thread_started"] is True
        assert "latest_payload" not in captured

        captured["thread_target"]()

        assert captured["run_refresh"]["scan_id"] == payload["activeScanId"]
        assert captured["run_refresh"]["published_scan_id"] == "scan-1"
        assert callable(captured["run_refresh"]["price_item"])
        assert captured["latest_payload"] == {
            "account_name": "qa-exile",
            "league": "Mirage",
            "realm": "pc",
        }
        assert app_module._LATEST_STASH_VALUATION_RESULTS[scope]["scanId"] == payload["activeScanId"]
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["status"] == "published"
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["sourceScanId"] == "scan-1"
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["publishedScanId"] == payload["activeScanId"]
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_start_stash_valuations_refresh_deduplicates_against_persisted_active_scan_after_cache_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_active_valuation_refresh",
        lambda _client, *, account_name, league, realm, published_scan_id, stale_timeout_seconds: {
            "scanId": "scan-2",
            "isActive": True,
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:02:00Z",
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app._load_private_stash_token_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oauth token loader should not be used")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app._build_private_stash_harvester",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("private harvester should not be built")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.uuid.uuid4",
        lambda: (_ for _ in ()).throw(AssertionError("uuid should not be minted")),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.threading.Thread",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("background thread should not be started")
        ),
    )

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload == {
            "status": "running",
            "scanKind": "valuation_refresh",
            "activeScanId": "scan-2",
            "sourceScanId": "scan-1",
            "publishedScanId": "scan-1",
            "startedAt": "2026-03-21T12:01:00Z",
            "updatedAt": "2026-03-21T12:02:00Z",
            "publishedAt": None,
            "progress": {
                "tabsTotal": 0,
                "tabsProcessed": 0,
                "itemsTotal": 0,
                "itemsProcessed": 0,
            },
            "error": None,
            "deduplicated": True,
        }
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_start_stash_valuations_refresh_republishes_latest_scan_from_persisted_v2_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    captured: dict[str, object] = {}

    class _DeferredThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon
            captured["thread_started"] = False

        def start(self) -> None:
            captured["thread_started"] = True
            captured["thread_target"] = self._target

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app._load_private_stash_token_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oauth token loader should not be used")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app._build_private_stash_harvester",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("private harvester should not be built")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda _client, **kwargs: (
            captured.update({"run_refresh": kwargs})
            or {
                "scanId": kwargs["scan_id"],
                "status": "published",
                "startedAt": kwargs["started_at"],
                "publishedAt": "2026-03-21T12:02:00Z",
                "accountName": "qa-exile",
                "league": kwargs["league"],
                "realm": kwargs["realm"],
            }
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: (
            captured.update({"latest_payload": kwargs})
            or {
                "structuredMode": True,
                "scanId": captured.get("run_refresh", {}).get("scan_id", "scan-2"),
                "stashId": captured.get("run_refresh", {}).get("scan_id", "scan-2"),
                "itemId": None,
                "scanDatetime": None,
                "chaosMedian": None,
                "daySeries": [],
                "items": [],
            }
        ),
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _DeferredThread)

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )

        assert payload["status"] == "running"
        assert payload["activeScanId"] != "scan-1"
        assert payload["sourceScanId"] == "scan-1"
        assert payload["publishedScanId"] == "scan-1"
        assert captured["thread_started"] is True
        assert "latest_payload" not in captured

        captured["thread_target"]()

        assert captured["run_refresh"]["scan_id"] == payload["activeScanId"]
        assert captured["run_refresh"]["published_scan_id"] == "scan-1"
        assert callable(captured["run_refresh"]["price_item"])
        assert captured["latest_payload"] == {
            "account_name": "qa-exile",
            "league": "Mirage",
            "realm": "pc",
        }
        assert app_module._LATEST_STASH_VALUATION_RESULTS[scope]["scanId"] == payload["activeScanId"]
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["status"] == "published"
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["sourceScanId"] == "scan-1"
        assert app_module._LATEST_STASH_VALUATION_STATUS[scope]["publishedScanId"] == payload["activeScanId"]
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_stash_scan_valuations_status_evicts_stale_completed_cache_after_published_scan_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS[scope] = {
        "status": "published",
        "activeScanId": None,
        "publishedScanId": "scan-1",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:03:00Z",
        "publishedAt": "2026-03-21T12:03:00Z",
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }
    app_module._LATEST_STASH_VALUATION_RESULTS[scope] = {
        "structuredMode": True,
        "scanId": "scan-1",
        "stashId": "scan-1",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-2",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_valuation_refresh_status_payload",
        lambda _client, **kwargs: {
            "status": "idle",
            "activeScanId": None,
            "publishedScanId": kwargs["published_scan_id"],
            "startedAt": None,
            "updatedAt": None,
            "publishedAt": None,
            "progress": {
                "tabsTotal": 0,
                "tabsProcessed": 0,
                "itemsTotal": 0,
                "itemsProcessed": 0,
            },
            "error": None,
        },
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/status",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
            },
            body_reader=BytesIO(b""),
        )

        body = json.loads(response.body.decode("utf-8"))
        assert response.status == 200
        assert body["publishedScanId"] == "scan-2"
        assert body["status"] == "idle"
        assert scope not in app_module._LATEST_STASH_VALUATION_STATUS
        assert scope not in app_module._LATEST_STASH_VALUATION_RESULTS
    finally:
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)


def test_stash_scan_valuations_status_rechecks_published_scan_after_lock_before_using_cached_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS[scope] = {
        "status": "published",
        "scanKind": "valuation_refresh",
        "activeScanId": None,
        "sourceScanId": "scan-old",
        "publishedScanId": "scan-old",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:03:00Z",
        "publishedAt": "2026-03-21T12:03:00Z",
        "progress": {
            "tabsTotal": 2,
            "tabsProcessed": 2,
            "itemsTotal": 5,
            "itemsProcessed": 5,
        },
        "error": None,
    }

    published_scan_ids: list[str] = []
    published_scan_iter = iter(["scan-old", "scan-current"])

    def _fetch_published_scan_id(
        _client, *, account_name: str, league: str, realm: str
    ) -> str:
        del account_name, league, realm
        published_scan_id = next(published_scan_iter)
        published_scan_ids.append(published_scan_id)
        return published_scan_id

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr("poe_trade.api.app.fetch_published_scan_id", _fetch_published_scan_id)
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_valuation_refresh_status_payload",
        lambda _client, **kwargs: {
            "status": "idle",
            "scanKind": "valuation_refresh",
            "activeScanId": None,
            "sourceScanId": None,
            "publishedScanId": kwargs["published_scan_id"],
            "startedAt": None,
            "updatedAt": None,
            "publishedAt": None,
            "progress": {
                "tabsTotal": 0,
                "tabsProcessed": 0,
                "itemsTotal": 0,
                "itemsProcessed": 0,
            },
            "error": None,
        },
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/status",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

        body = json.loads(response.body.decode("utf-8"))
        assert response.status == 200
        assert body["status"] == "idle"
        assert body["publishedScanId"] == "scan-current"
        assert published_scan_ids == ["scan-old", "scan-current"]
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)


def test_stash_scan_valuations_result_evicts_stale_completed_cache_after_published_scan_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS[scope] = {
        "structuredMode": True,
        "scanId": "scan-1",
        "stashId": "scan-1",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }

    rebuilt_payload = {
        "structuredMode": True,
        "scanId": "scan-2",
        "stashId": "scan-2",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-2",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: rebuilt_payload | kwargs,
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

        body = json.loads(response.body.decode("utf-8"))
        assert response.status == 200
        assert body["scanId"] == "scan-2"
        assert app_module._LATEST_STASH_VALUATION_RESULTS[scope]["scanId"] == "scan-2"
        assert body["account_name"] == "qa-exile"
        assert body["league"] == "Mirage"
        assert body["realm"] == "pc"
    finally:
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)


def test_stash_scan_valuations_result_rechecks_published_scan_after_lock_before_using_cached_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS[scope] = {
        "structuredMode": True,
        "scanId": "scan-old",
        "stashId": "scan-old",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }

    published_scan_ids: list[str] = []
    published_scan_iter = iter(["scan-old", "scan-current"])

    def _fetch_published_scan_id(
        _client, *, account_name: str, league: str, realm: str
    ) -> str:
        del account_name, league, realm
        published_scan_id = next(published_scan_iter)
        published_scan_ids.append(published_scan_id)
        return published_scan_id

    rebuilt_payload = {
        "structuredMode": True,
        "scanId": "scan-current",
        "stashId": "scan-current",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr("poe_trade.api.app.fetch_published_scan_id", _fetch_published_scan_id)
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: rebuilt_payload | kwargs,
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

        body = json.loads(response.body.decode("utf-8"))
        assert response.status == 200
        assert body["scanId"] == "scan-current"
        assert body["account_name"] == "qa-exile"
        assert body["league"] == "Mirage"
        assert body["realm"] == "pc"
        assert published_scan_ids == ["scan-old", "scan-current"]
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)


def test_stash_scan_valuations_result_route_recovers_published_refresh_after_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    app_module._PENDING_STASH_VALUATIONS[scope] = {
        "status": "running",
        "activeScanId": "scan-old",
        "publishedScanId": "scan-old",
        "startedAt": "2026-03-21T12:00:00Z",
        "updatedAt": "2026-03-21T12:00:00Z",
        "publishedAt": None,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": None,
    }
    app_module._LATEST_STASH_VALUATION_RESULTS[scope] = {
        "structuredMode": True,
        "scanId": "scan-old",
        "stashId": "scan-old",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }

    rebuilt_payload = {
        "structuredMode": True,
        "scanId": "scan-2",
        "stashId": "scan-2",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [
            {
                "fingerprint": "sig:item-1",
                "itemId": "item-1",
                "priceBand": "good",
                "priceEvaluation": "well_priced",
            }
        ],
    }

    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-2",
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        lambda _client, **kwargs: rebuilt_payload | kwargs,
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
    app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)

    try:
        response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )

        body = json.loads(response.body.decode("utf-8"))
        assert response.status == 200
        assert body["scanId"] == "scan-2"
        assert body["items"] == rebuilt_payload["items"]
        assert body["account_name"] == "qa-exile"
        assert body["league"] == "Mirage"
        assert body["realm"] == "pc"
        assert app_module._LATEST_STASH_VALUATION_RESULTS[scope]["scanId"] == "scan-2"
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)


def test_stash_scan_valuations_refresh_failed_status_preserves_last_good_result_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    cached_payload = {
        "structuredMode": True,
        "scanId": "scan-1",
        "stashId": "scan-1",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }
    app_module._LATEST_STASH_VALUATION_RESULTS[scope] = cached_payload

    class _ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app._load_private_stash_token_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oauth token loader should not be used")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app._build_private_stash_harvester",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("private harvester should not be built")
        ),
    )
    monkeypatch.setattr(
        app_module,
        "run_private_scan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("live private scan should not be used")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda _client, **kwargs: {
            "status": "failed",
            "scanId": kwargs["scan_id"],
            "startedAt": kwargs["started_at"],
            "publishedAt": None,
            "error": "publish marker missing",
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        mock.Mock(side_effect=AssertionError("unexpected payload refresh")),
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _ImmediateThread)
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )
        assert payload["status"] == "running"
        assert payload["activeScanId"] != payload["publishedScanId"]
        assert payload["publishedScanId"] == "scan-1"

        status_response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/status",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )
        status_body = json.loads(status_response.body.decode("utf-8"))
        assert status_response.status == 200
        assert status_body["status"] == "failed"
        assert status_body["activeScanId"] == payload["activeScanId"]
        assert status_body["publishedScanId"] == "scan-1"
        assert status_body["error"] == "publish marker missing"

        result_response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )
        assert result_response.status == 200
        assert json.loads(result_response.body.decode("utf-8")) == cached_payload
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_stash_scan_valuations_refresh_exception_preserves_last_good_result_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = ("qa-exile", "Mirage", "pc")
    cached_payload = {
        "structuredMode": True,
        "scanId": "scan-1",
        "stashId": "scan-1",
        "itemId": None,
        "scanDatetime": None,
        "chaosMedian": None,
        "daySeries": [],
        "items": [],
    }
    app_module._LATEST_STASH_VALUATION_RESULTS[scope] = cached_payload

    class _ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(
        "poe_trade.api.app.fetch_published_scan_id",
        lambda _client, *, account_name, league, realm: "scan-1",
    )
    monkeypatch.setattr(
        "poe_trade.api.app._load_private_stash_token_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oauth token loader should not be used")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app._build_private_stash_harvester",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("private harvester should not be built")
        ),
    )
    monkeypatch.setattr(
        app_module,
        "run_private_scan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("live private scan should not be used")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        "poe_trade.api.app.run_persisted_valuation_refresh",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("refresh exploded")
        ),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.latest_stash_scan_valuations_payload",
        mock.Mock(side_effect=AssertionError("unexpected payload refresh")),
    )
    monkeypatch.setattr("poe_trade.api.app.threading.Thread", _ImmediateThread)
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )

    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    try:
        payload = start_stash_valuations_refresh(
            app.settings,
            app.client,
            account_name="qa-exile",
            league="Mirage",
            realm="pc",
        )
        assert payload["status"] == "running"
        assert payload["activeScanId"] != payload["publishedScanId"]
        assert payload["publishedScanId"] == "scan-1"

        status_response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/status",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )
        status_body = json.loads(status_response.body.decode("utf-8"))
        assert status_response.status == 200
        assert status_body["status"] == "failed"
        assert status_body["activeScanId"] == payload["activeScanId"]
        assert status_body["publishedScanId"] == "scan-1"
        assert status_body["error"] == "refresh exploded"

        result_response = app.handle(
            method="GET",
            raw_path="/api/v1/stash/scan/valuations/result",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=test-session",
                "Content-Length": "0",
            },
            body_reader=BytesIO(b""),
        )
        assert result_response.status == 200
        assert json.loads(result_response.body.decode("utf-8")) == cached_payload
    finally:
        app_module._PENDING_STASH_VALUATIONS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_RESULTS.pop(scope, None)
        app_module._LATEST_STASH_VALUATION_STATUS.pop(scope, None)


def test_stash_scan_valuations_start_route_description_mentions_persisted_refresh() -> None:
    text = Path("apispec.yml").read_text(encoding="utf-8")
    assert "Start persisted stash valuation refresh" in text
    assert "persisted private-stash valuation refresh" in text
    assert "Reload latest stash valuation snapshot" not in text


def test_build_stash_scan_valuations_payload_prefers_v2_snapshot_rows() -> None:
    class _StubClickHouse(ClickHouseClient):
        def __init__(self, payloads: list[str]) -> None:
            super().__init__(endpoint="http://ch")
            self.payloads = list(payloads)
            self.queries: list[str] = []

        def execute(
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if self.payloads:
                return self.payloads.pop(0)
            return ""

    v2_row = json.dumps(
        {
            "scan_id": "scan-1",
            "account_name": "qa-exile",
            "league": "Mirage",
            "realm": "pc",
            "tab_id": "tab-1",
            "tab_index": 0,
            "tab_name": "Currency",
            "tab_type": "normal",
            "lineage_key": "sig:item-1",
            "item_id": "item-1",
            "item_name": "Grim Bane",
            "base_type": "Hubris Circlet",
            "item_class": "Helmet",
            "rarity": "rare",
            "x": 0,
            "y": 0,
            "w": 2,
            "h": 2,
            "listed_price": 40.0,
            "listed_currency": "chaos",
            "listed_price_chaos": 40.0,
            "estimated_price_chaos": 45.0,
            "price_p10_chaos": 39.0,
            "price_p90_chaos": 51.0,
            "confidence": 82.0,
            "estimate_trust": "normal",
            "estimate_warning": "",
            "fallback_reason": "",
            "icon_url": "https://example.invalid/icon.png",
            "priced_at": "2026-03-21T10:10:00Z",
            "payload_json": json.dumps(
                {
                    "id": "item-1",
                    "name": "Grim Bane",
                    "typeLine": "Hubris Circlet",
                    "frameType": 2,
                    "itemClass": "Helmet",
                    "icon": "https://example.invalid/icon.png",
                    "x": 0,
                    "y": 0,
                    "w": 2,
                    "h": 2,
                    "note": "~price 40 chaos",
                }
            ),
        }
    )
    client = _StubClickHouse([v2_row + "\n", ""])

    payload = build_stash_scan_valuations_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        scan_id="scan-1",
        item_id=None,
        structured_mode=True,
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["items"][0]["priceBand"] == "mediocre"
    assert payload["items"][0]["priceEvaluation"] == "could_be_better"
    assert "account_stash_scan_items_v2" in client.queries[0]


def test_build_stash_scan_valuations_payload_keeps_every_v2_item_and_price_fields() -> None:
    class _StubClickHouse(ClickHouseClient):
        def __init__(self, payload: str) -> None:
            super().__init__(endpoint="http://ch")
            self.payload = payload
            self.queries: list[str] = []

        def execute(
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            return self.payload if len(self.queries) == 1 else ""

    payload = "\n".join(
        [
            json.dumps(
                {
                    "scan_id": "scan-1",
                    "account_name": "qa-exile",
                    "league": "Mirage",
                    "realm": "pc",
                    "tab_id": "tab-1",
                    "tab_index": 0,
                    "tab_name": "Currency",
                    "tab_type": "normal",
                    "lineage_key": "sig:item-1",
                    "item_id": "item-1",
                    "item_name": "Grim Bane",
                    "base_type": "Hubris Circlet",
                    "item_class": "Helmet",
                    "rarity": "rare",
                    "x": 0,
                    "y": 0,
                    "w": 2,
                    "h": 2,
                    "listed_price": 40.0,
                    "listed_currency": "chaos",
                    "listed_price_chaos": 40.0,
                    "estimated_price_chaos": 38.0,
                    "price_p10_chaos": 36.0,
                    "price_p90_chaos": 40.0,
                    "confidence": 82.0,
                    "estimate_trust": "normal",
                    "estimate_warning": "",
                    "fallback_reason": "",
                    "price_band": "good",
                    "price_band_version": 1,
                    "icon_url": "https://example.invalid/icon-1.png",
                    "priced_at": "2026-03-21T10:10:00Z",
                    "payload_json": json.dumps(
                        {
                            "id": "item-1",
                            "name": "Grim Bane",
                            "typeLine": "Hubris Circlet",
                            "frameType": 2,
                            "itemClass": "Helmet",
                            "icon": "https://example.invalid/icon-1.png",
                            "x": 0,
                            "y": 0,
                            "w": 2,
                            "h": 2,
                            "note": "~price 40 chaos",
                        }
                    ),
                }
            ),
            json.dumps(
                {
                    "scan_id": "scan-1",
                    "account_name": "qa-exile",
                    "league": "Mirage",
                    "realm": "pc",
                    "tab_id": "tab-2",
                    "tab_index": 1,
                    "tab_name": "Dump",
                    "tab_type": "quad",
                    "lineage_key": "sig:item-2",
                    "item_id": "",
                    "item_name": "Vaal Regalia",
                    "base_type": "Vaal Regalia",
                    "item_class": "Body Armour",
                    "rarity": "rare",
                    "x": 4,
                    "y": 6,
                    "w": 2,
                    "h": 3,
                    "listed_price": 55.0,
                    "listed_currency": "chaos",
                    "listed_price_chaos": 55.0,
                    "estimated_price_chaos": 44.0,
                    "price_p10_chaos": 40.0,
                    "price_p90_chaos": 48.0,
                    "confidence": 73.0,
                    "estimate_trust": "normal",
                    "estimate_warning": "",
                    "fallback_reason": "",
                    "price_band": "mediocre",
                    "price_band_version": 1,
                    "icon_url": "https://example.invalid/icon-2.png",
                    "priced_at": "2026-03-21T10:10:00Z",
                    "payload_json": json.dumps(
                        {
                            "name": "Vaal Regalia",
                            "typeLine": "Vaal Regalia",
                            "frameType": 2,
                            "itemClass": "Body Armour",
                            "icon": "https://example.invalid/icon-2.png",
                            "x": 4,
                            "y": 6,
                            "w": 2,
                            "h": 3,
                            "note": "~price 55 chaos",
                        }
                    ),
                }
            ),
        ]
    )
    client = _StubClickHouse(payload + "\n")

    result = build_stash_scan_valuations_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        scan_id="scan-1",
        item_id=None,
        structured_mode=True,
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert len(result["items"]) == 2
    assert result["items"][0]["fingerprint"] == "sig:item-1"
    assert result["items"][0]["priceBand"] == "good"
    assert result["items"][0]["priceEvaluation"] == "well_priced"
    assert result["items"][0]["priceBandVersion"] == 1
    assert result["items"][1]["fingerprint"] == "sig:item-2"
    assert result["items"][1]["priceBand"] == "mediocre"
    assert result["items"][1]["priceEvaluation"] == "could_be_better"
    assert result["items"][1]["priceBandVersion"] == 1


def test_latest_result_includes_every_scanned_item_and_price_quality_fields() -> None:
    class _StubClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://ch")
            self.queries: list[str] = []

        def execute(
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            if "account_stash_published_scans" in query:
                return '{"scan_id":"scan-1"}\n'
            if "account_stash_scan_items_v2" in query:
                return '\n'.join(
                    [
                        json.dumps(
                            {
                                "scan_id": "scan-1",
                                "account_name": "qa-exile",
                                "league": "Mirage",
                                "realm": "pc",
                                "tab_id": "tab-1",
                                "tab_index": 0,
                                "tab_name": "Currency",
                                "tab_type": "normal",
                                "lineage_key": "sig:item-1",
                                "item_id": "item-1",
                                "item_name": "Grim Bane",
                                "base_type": "Hubris Circlet",
                                "item_class": "Helmet",
                                "rarity": "rare",
                                "x": 0,
                                "y": 0,
                                "w": 2,
                                "h": 2,
                                "listed_price": 40.0,
                                "listed_currency": "chaos",
                                "listed_price_chaos": 40.0,
                                "estimated_price_chaos": 40.0,
                                "price_p10_chaos": 38.0,
                                "price_p90_chaos": 42.0,
                                "price_delta_chaos": 0.0,
                                "price_delta_pct": 0.0,
                                "confidence": 82.0,
                                "estimate_trust": "normal",
                                "estimate_warning": "",
                                "fallback_reason": "",
                                "price_band": "good",
                                "price_band_version": 1,
                                "icon_url": "https://example.invalid/icon-1.png",
                                "priced_at": "2026-03-21T10:10:00Z",
                                "payload_json": json.dumps(
                                    {
                                        "id": "item-1",
                                        "name": "Grim Bane",
                                        "typeLine": "Hubris Circlet",
                                        "frameType": 2,
                                        "itemClass": "Helmet",
                                        "icon": "https://example.invalid/icon-1.png",
                                        "x": 0,
                                        "y": 0,
                                        "w": 2,
                                        "h": 2,
                                        "note": "~price 40 chaos",
                                    }
                                ),
                            }
                        ),
                        json.dumps(
                            {
                                "scan_id": "scan-1",
                                "account_name": "qa-exile",
                                "league": "Mirage",
                                "realm": "pc",
                                "tab_id": "tab-2",
                                "tab_index": 1,
                                "tab_name": "Gear",
                                "tab_type": "normal",
                                "lineage_key": "sig:item-2",
                                "item_id": "item-2",
                                "item_name": "Vaal Regalia",
                                "base_type": "Vaal Regalia",
                                "item_class": "Body Armour",
                                "rarity": "rare",
                                "x": 4,
                                "y": 6,
                                "w": 2,
                                "h": 3,
                                "listed_price": 55.0,
                                "listed_currency": "chaos",
                                "listed_price_chaos": 55.0,
                                "estimated_price_chaos": 44.0,
                                "price_p10_chaos": 40.0,
                                "price_p90_chaos": 48.0,
                                "price_delta_chaos": 11.0,
                                "price_delta_pct": 25.0,
                                "confidence": 73.0,
                                "estimate_trust": "normal",
                                "estimate_warning": "",
                                "fallback_reason": "",
                                "price_band": "mediocre",
                                "price_band_version": 1,
                                "icon_url": "https://example.invalid/icon-2.png",
                                "priced_at": "2026-03-21T10:10:00Z",
                                "payload_json": json.dumps(
                                    {
                                        "id": "item-2",
                                        "name": "Vaal Regalia",
                                        "typeLine": "Vaal Regalia",
                                        "frameType": 2,
                                        "itemClass": "Body Armour",
                                        "icon": "https://example.invalid/icon-2.png",
                                        "x": 4,
                                        "y": 6,
                                        "w": 2,
                                        "h": 3,
                                        "note": "~price 55 chaos",
                                    }
                                ),
                            }
                        ),
                    ]
                ) + '\n'
            return ""

    client = _StubClickHouse()

    payload = build_stash_scan_valuations_payload(
        client,
        account_name="qa-exile",
        league="Mirage",
        realm="pc",
        scan_id="scan-1",
        item_id=None,
        structured_mode=True,
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["scanId"] == "scan-1"
    assert [item["itemId"] for item in payload["items"]] == ["item-1", "item-2"]
    assert payload["items"][0]["priceBand"] == "good"
    assert payload["items"][0]["priceEvaluation"] == "well_priced"
    assert payload["items"][1]["priceBand"] == "mediocre"
    assert payload["items"][1]["priceEvaluation"] == "could_be_better"
    assert all(
        item["priceBandVersion"] == 1 for item in payload["items"]
    )


def test_build_stash_item_valuation_round_trips_divine_orb_display_values() -> None:
    class _StubClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://ch")
            self.queries: list[str] = []

        def execute(
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            return ""

    client = _StubClickHouse()
    row = {
        "scan_id": "scan-1",
        "item_id": "item-1",
        "item_name": "Divine Orb",
        "item_class": "Currency",
        "rarity": "normal",
        "x": 0,
        "y": 0,
        "w": 1,
        "h": 1,
        "listed_price": 2.0,
        "listed_currency": "divine orb",
        "listed_price_chaos": 400.0,
        "estimated_price_chaos": 400.0,
        "price_p10_chaos": 380.0,
        "price_p90_chaos": 420.0,
        "confidence": 88.0,
        "estimate_trust": "normal",
        "estimate_warning": "",
        "fallback_reason": "",
        "priced_at": "2026-03-21T10:10:00Z",
        "payload_json": json.dumps(
            {
                "typeLine": "Divine Orb",
                "note": "~price 2 divine orb",
            }
        ),
    }

    payload = _build_stash_item_valuation(
        client,
        row,
        league="Mirage",
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["listedCurrency"] == "divine orb"
    assert payload["listedPrice"] == 2.0
    assert payload["listedPriceChaos"] == 400.0
    assert payload["estimatedPrice"] == 2.0
    assert payload["estimatedPriceChaos"] == 400.0
    assert payload["priceBand"] == "good"
    assert payload["priceEvaluation"] == "well_priced"
    assert payload["fingerprint"] == "item:item-1"


def test_build_stash_item_valuation_preserves_stored_chaos_values_for_non_computable_currency() -> None:
    class _StubClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://ch")
            self.queries: list[str] = []

        def execute(
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            return ""

    client = _StubClickHouse()
    row = {
        "scan_id": "scan-1",
        "item_id": "item-1",
        "item_name": "Grim Bane",
        "item_class": "Helmet",
        "rarity": "rare",
        "x": 0,
        "y": 0,
        "w": 1,
        "h": 1,
        "listed_price": 2.0,
        "listed_currency": "exalted orb",
        "listed_price_chaos": 24.0,
        "estimated_price_chaos": 24.0,
        "price_p10_chaos": 22.0,
        "price_p90_chaos": 26.0,
        "confidence": 88.0,
        "estimate_trust": "normal",
        "estimate_warning": "",
        "fallback_reason": "",
        "priced_at": "2026-03-21T10:10:00Z",
        "payload_json": json.dumps(
            {
                "typeLine": "Hubris Circlet",
                "note": "~price 2 exalted orb",
            }
        ),
    }

    payload = _build_stash_item_valuation(
        client,
        row,
        league="Mirage",
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["listedCurrency"] == "exalted orb"
    assert payload["listedPrice"] == 2.0
    assert payload["listedPriceChaos"] == 24.0
    assert payload["estimatedPrice"] is None
    assert payload["estimatedPriceChaos"] == 24.0
    assert payload["priceDeltaChaos"] == 0.0
    assert payload["priceDeltaPercent"] == 0.0
    assert payload["priceBand"] == "good"
    assert payload["priceEvaluation"] == "well_priced"
    assert payload["priceRecommendationEligible"] is True
    assert payload["fingerprint"] == "item:item-1"


def test_build_stash_item_valuation_handles_mixed_currency_legacy_rows() -> None:
    class _StubClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://ch")
            self.queries: list[str] = []

        def execute(
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            return ""

    client = _StubClickHouse()
    row = {
        "scan_id": "scan-1",
        "item_id": "item-1",
        "item_name": "Divine Orb",
        "item_class": "Currency",
        "rarity": "normal",
        "x": 0,
        "y": 0,
        "w": 1,
        "h": 1,
        "listed_price": 2.0,
        "currency": "chaos",
        "predicted_price": 24.0,
        "price_p10": 22.0,
        "price_p90": 26.0,
        "confidence": 88.0,
        "estimate_trust": "normal",
        "estimate_warning": "",
        "fallback_reason": "",
        "priced_at": "2026-03-21T10:10:00Z",
        "payload_json": json.dumps(
            {
                "typeLine": "Divine Orb",
                "note": "~price 2 divine orb",
            }
        ),
    }

    payload = _build_stash_item_valuation(
        client,
        row,
        league="Mirage",
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["listedCurrency"] == "divine orb"
    assert payload["listedPriceChaos"] == 400.0
    assert payload["estimatedPriceChaos"] == 24.0
    assert payload["estimatedPrice"] == 0.12
    assert payload["priceDeltaChaos"] == 376.0
    assert round(payload["priceDeltaPercent"], 6) == round((376.0 / 24.0) * 100.0, 6)
    assert payload["priceBand"] == "bad"
    assert payload["priceEvaluation"] == "mispriced"


def test_build_stash_item_valuation_treats_c_shortcut_as_chaos() -> None:
    class _StubClickHouse(ClickHouseClient):
        def __init__(self) -> None:
            super().__init__(endpoint="http://ch")
            self.queries: list[str] = []

        def execute(
            self, query: str, settings: Mapping[str, str] | None = None
        ) -> str:
            del settings
            self.queries.append(query)
            return ""

    client = _StubClickHouse()
    row = {
        "scan_id": "scan-1",
        "item_id": "item-1",
        "item_name": "Chaos Orb",
        "item_class": "Currency",
        "rarity": "normal",
        "x": 0,
        "y": 0,
        "w": 1,
        "h": 1,
        "listed_price": 40.0,
        "listed_currency": "c",
        "listed_price_chaos": 40.0,
        "estimated_price_chaos": 40.0,
        "price_p10_chaos": 38.0,
        "price_p90_chaos": 42.0,
        "confidence": 88.0,
        "estimate_trust": "normal",
        "estimate_warning": "",
        "fallback_reason": "",
        "priced_at": "2026-03-21T10:10:00Z",
        "payload_json": json.dumps(
            {
                "typeLine": "Chaos Orb",
                "note": "~price 40 c",
            }
        ),
    }

    payload = _build_stash_item_valuation(
        client,
        row,
        league="Mirage",
        min_threshold=10.0,
        max_threshold=50.0,
        max_age_days=30,
    )

    assert payload["listedCurrency"] == "c"
    assert payload["listedPrice"] == 40.0
    assert payload["listedPriceChaos"] == 40.0
    assert payload["estimatedPrice"] == 40.0
    assert payload["estimatedPriceChaos"] == 40.0
    assert payload["priceBand"] == "good"
    assert payload["priceEvaluation"] == "well_priced"


def test_stash_scan_valuations_route_returns_structured_batch_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.stash_scan_valuations_payload",
        lambda _client, **kwargs: {
            "structuredMode": True,
            "stashId": "scan-1",
            "itemId": None,
            "scanDatetime": None,
            "chaosMedian": None,
            "daySeries": [],
            "items": [
                {
                    "stashId": "scan-1",
                    "itemId": "item-1",
                    "scanDatetime": "2026-03-21T12:00:00Z",
                    "chaosMedian": 42.0,
                    "daySeries": [],
                    "priceBand": "good",
                },
                {
                    "stashId": "scan-1",
                    "itemId": "item-2",
                    "scanDatetime": "2026-03-21T12:00:00Z",
                    "chaosMedian": 55.0,
                    "daySeries": [],
                    "priceBand": "bad",
                },
            ],
        },
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    body = _request_body(structuredMode=True, itemId="")
    response = app.handle(
        method="POST",
        raw_path="/api/v1/stash/scan/valuations?league=Mirage&realm=pc",
        headers=_request_headers(body),
        body_reader=BytesIO(body),
    )

    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["structuredMode"] is True
    assert len(body["items"]) == 2
    assert body["items"][0]["priceBand"] == "good"


def test_stash_scan_valuations_route_rejects_unknown_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    monkeypatch.setattr(
        "poe_trade.api.app.stash_scan_valuations_payload",
        lambda _client, **_kwargs: (_ for _ in ()).throw(LookupError("item not found")),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    body = _request_body(itemId="missing-item")
    with pytest.raises(ApiError) as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/stash/scan/valuations?league=Mirage&realm=pc",
            headers=_request_headers(body),
            body_reader=BytesIO(body),
        )

    assert exc.value.status == 404
    assert exc.value.code == "item_not_found"


@pytest.mark.parametrize(
    "body",
    [
        _request_body(maxAgeDays="bad"),
        _request_body(minThreshold="bad"),
        _request_body(maxThreshold="bad"),
    ],
)
def test_stash_scan_valuations_route_rejects_invalid_numeric_input(
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: _connected_session(session_id),
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/stash/scan/valuations?league=Mirage&realm=pc",
            headers=_request_headers(body),
            body_reader=BytesIO(body),
        )

    assert exc.value.status == 400
    assert exc.value.code == "invalid_input"


@pytest.mark.parametrize(
    "session_status,expected_code",
    [("disconnected", "auth_required"), ("session_expired", "session_expired")],
)
def test_stash_scan_valuations_route_requires_connected_session(
    monkeypatch: pytest.MonkeyPatch,
    session_status: str,
    expected_code: str,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.get_session",
        lambda _settings, *, session_id: {
            "session_id": session_id,
            "status": session_status,
            "account_name": "qa-exile",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )
    app = ApiApp(
        _settings_with_stash_enabled(),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )

    with pytest.raises(ApiError) as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/stash/scan/valuations?league=Mirage&realm=pc",
            headers=_request_headers(_request_body()),
            body_reader=BytesIO(_request_body()),
        )

    assert exc.value.status == 401
    assert exc.value.code == expected_code
