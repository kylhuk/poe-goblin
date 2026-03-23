from __future__ import annotations

import os
import json
from io import BytesIO
from typing import cast
from unittest import mock

import pytest

from poe_trade.api.app import ApiApp
from poe_trade.api.auth_session import load_credential_state
from poe_trade.api.responses import ApiError
from poe_trade.config.settings import Settings
from poe_trade.db import ClickHouseClient


def _settings(
    *,
    trusted_origin_bypass: bool = False,
    auth_state_dir: str | None = None,
) -> Settings:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_API_CORS_ORIGINS": "https://app.example.com",
        "POE_API_MAX_BODY_BYTES": "32768",
        "POE_API_LEAGUE_ALLOWLIST": "Mirage",
        "POE_API_TRUSTED_ORIGIN_BYPASS": "true" if trusted_origin_bypass else "false",
    }
    if auth_state_dir is not None:
        env["POE_AUTH_STATE_DIR"] = auth_state_dir
    with mock.patch.dict(os.environ, env, clear=True):
        return Settings.from_env()


def test_ml_routes_require_bearer_token() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError, match="bearer token required") as exc:
        _ = app.handle(
            method="GET",
            raw_path="/api/v1/ml/contract",
            headers={"Origin": "https://app.example.com"},
            body_reader=BytesIO(b""),
        )
    assert exc.value.code == "auth_required"
    assert exc.value.status == 401
    assert (
        exc.value.headers.get("Access-Control-Allow-Origin")
        == "https://app.example.com"
    )


def test_ml_routes_reject_invalid_bearer_token() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError, match="invalid bearer token") as exc:
        _ = app.handle(
            method="GET",
            raw_path="/api/v1/ml/contract",
            headers={
                "Authorization": "Bearer wrong",
                "Origin": "https://app.example.com",
            },
            body_reader=BytesIO(b""),
        )
    assert exc.value.code == "auth_invalid"
    assert exc.value.status == 401
    assert (
        exc.value.headers.get("Access-Control-Allow-Origin")
        == "https://app.example.com"
    )


def test_ml_routes_accept_valid_bearer_token() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/api/v1/ml/contract",
        headers={"Authorization": "Bearer phase1-token"},
        body_reader=BytesIO(b""),
    )
    assert response.status == 200


def test_ops_routes_require_bearer_token() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError, match="bearer token required") as exc:
        _ = app.handle(
            method="GET",
            raw_path="/api/v1/ops/services",
            headers={"Origin": "https://app.example.com"},
            body_reader=BytesIO(b""),
        )
    assert exc.value.code == "auth_required"
    assert exc.value.status == 401


def test_ops_routes_allow_trusted_origin_without_bearer_when_enabled() -> None:
    app = ApiApp(
        _settings(trusted_origin_bypass=True),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )
    response = app.handle(
        method="GET",
        raw_path="/api/v1/ops/contract",
        headers={
            "Origin": "https://app.example.com",
            "Referer": "https://app.example.com/",
        },
        body_reader=BytesIO(b""),
    )
    assert response.status == 200


def test_ops_routes_require_bearer_when_trusted_bypass_missing_referer() -> None:
    app = ApiApp(
        _settings(trusted_origin_bypass=True),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )
    with pytest.raises(ApiError, match="bearer token required") as exc:
        _ = app.handle(
            method="GET",
            raw_path="/api/v1/ops/services",
            headers={"Origin": "https://app.example.com"},
            body_reader=BytesIO(b""),
        )
    assert exc.value.code == "auth_required"
    assert exc.value.status == 401


def test_ops_routes_require_bearer_when_referer_host_is_spoofed() -> None:
    app = ApiApp(
        _settings(trusted_origin_bypass=True),
        clickhouse_client=ClickHouseClient(endpoint="http://ch"),
    )
    with pytest.raises(ApiError, match="bearer token required") as exc:
        _ = app.handle(
            method="GET",
            raw_path="/api/v1/ops/services",
            headers={
                "Origin": "https://app.example.com",
                "Referer": "https://app.example.com.evil/",
            },
            body_reader=BytesIO(b""),
        )
    assert exc.value.code == "auth_required"
    assert exc.value.status == 401


def test_auth_session_route_is_public_and_returns_disconnected() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/api/v1/auth/session",
        headers={"Origin": "https://app.example.com"},
        body_reader=BytesIO(b""),
    )
    assert response.status == 200


def test_auth_session_bootstrap_sets_cookie_and_returns_connected(
    tmp_path,
) -> None:
    settings = _settings(auth_state_dir=str(tmp_path / "auth-state"))
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = json.dumps(
        {
            "poeSessionId": "POESESSID-123",
            "cf_clearance": "cf-clearance-123",
        }
    ).encode("utf-8")

    with mock.patch("poe_trade.api.app.resolve_account_name", return_value="qa-exile"):
        response = app.handle(
            method="POST",
            raw_path="/api/v1/auth/session",
            headers={
                "Origin": "https://app.example.com",
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            },
            body_reader=BytesIO(payload),
        )

    body = cast(dict[str, object], json.loads(response.body.decode("utf-8")))
    credential_state = load_credential_state(settings)
    assert response.status == 200
    assert body["status"] == "connected"
    assert body["accountName"] == "qa-exile"
    assert "poeSessionId" not in body
    assert "Set-Cookie" in response.headers
    assert "poe_session=" in response.headers["Set-Cookie"]
    assert "POESESSID=" not in response.headers["Set-Cookie"]
    assert credential_state["account_name"] == "qa-exile"
    assert credential_state["status"] == "bootstrap_connected"
    assert credential_state["poe_session_id"] == "POESESSID-123"
    assert credential_state["cf_clearance"] == "cf-clearance-123"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"poeSessionId": ""},
        {"poeSessionId": "   "},
        {"poeSessionId": 12345},
    ],
)
def test_auth_session_bootstrap_rejects_invalid_input(
    payload: dict[str, object],
) -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    raw = json.dumps(payload).encode("utf-8")

    with pytest.raises(ApiError) as exc:
        _ = app.handle(
            method="POST",
            raw_path="/api/v1/auth/session",
            headers={
                "Origin": "https://app.example.com",
                "Content-Type": "application/json",
                "Content-Length": str(len(raw)),
            },
            body_reader=BytesIO(raw),
        )

    assert exc.value.status == 400
    assert exc.value.code == "invalid_input"


def test_auth_session_bootstrap_rejects_unresolvable_account() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = json.dumps({"poeSessionId": "POESESSID-123"}).encode("utf-8")

    with mock.patch(
        "poe_trade.api.app.resolve_account_name", side_effect=ValueError("invalid")
    ):
        with pytest.raises(ApiError) as exc:
            _ = app.handle(
                method="POST",
                raw_path="/api/v1/auth/session",
                headers={
                    "Origin": "https://app.example.com",
                    "Content-Type": "application/json",
                    "Content-Length": str(len(payload)),
                },
                body_reader=BytesIO(payload),
            )

    assert exc.value.status == 400
    assert exc.value.code == "invalid_input"


def test_auth_logout_clears_session_and_returns_disconnected_on_next_read(
    tmp_path,
) -> None:
    settings = _settings(auth_state_dir=str(tmp_path / "auth-state"))
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = json.dumps({"poeSessionId": "POESESSID-123"}).encode("utf-8")
    with mock.patch("poe_trade.api.app.resolve_account_name", return_value="qa-exile"):
        bootstrap = app.handle(
            method="POST",
            raw_path="/api/v1/auth/session",
            headers={
                "Origin": "https://app.example.com",
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            },
            body_reader=BytesIO(payload),
        )
    set_cookie = bootstrap.headers.get("Set-Cookie", "")
    cookie_pair = set_cookie.split(";", maxsplit=1)[0]

    logout = app.handle(
        method="POST",
        raw_path="/api/v1/auth/logout",
        headers={"Origin": "https://app.example.com", "Cookie": cookie_pair},
        body_reader=BytesIO(b""),
    )
    assert logout.status == 200
    assert "Max-Age=0" in logout.headers.get("Set-Cookie", "")

    follow_up = app.handle(
        method="GET",
        raw_path="/api/v1/auth/session",
        headers={"Origin": "https://app.example.com", "Cookie": cookie_pair},
        body_reader=BytesIO(b""),
    )
    credential_state = load_credential_state(settings)
    body = cast(dict[str, object], json.loads(follow_up.body.decode("utf-8")))
    assert follow_up.status == 200
    assert body == {"status": "disconnected", "accountName": None}
    assert credential_state["status"] == "logged_out"
    assert credential_state["account_name"] == ""
    assert credential_state["poe_session_id"] == ""


def test_auth_session_expired_clears_cookie() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    with mock.patch(
        "poe_trade.api.app.get_session",
        return_value={
            "session_id": "session-1",
            "status": "session_expired",
            "account_name": "qa-exile",
            "expires_at": "2026-01-01T00:00:00Z",
            "scope": [],
        },
    ):
        response = app.handle(
            method="GET",
            raw_path="/api/v1/auth/session",
            headers={
                "Origin": "https://app.example.com",
                "Cookie": "poe_session=session-1",
            },
            body_reader=BytesIO(b""),
        )

    body = cast(dict[str, object], json.loads(response.body.decode("utf-8")))
    assert response.status == 200
    assert body["status"] == "session_expired"
    assert "Set-Cookie" in response.headers
    assert "Max-Age=0" in response.headers["Set-Cookie"]
