from __future__ import annotations

import json
import os
from io import BytesIO
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest

from poe_trade.api.app import ApiApp
from poe_trade.api.auth_session import (
    OAuthExchangeResult,
    authorize_redirect,
    begin_login,
    create_session,
    load_credential_state,
    load_oauth_token_state,
    save_credential_state,
    save_oauth_token_state,
)
from poe_trade.api.responses import ApiError
from poe_trade.config.settings import Settings
from poe_trade.db import ClickHouseClient


def test_authorize_redirect_urlencodes_redirect_uri() -> None:
    env = {
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_REDIRECT_URI": "https://api.example.com/auth/start?foo=bar&baz=qux",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_ACCOUNT_OAUTH_SCOPE": "account:profile account:stashes",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    tx = begin_login(settings)
    location = authorize_redirect(settings, tx)
    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert query["redirect_uri"][0] == env["POE_ACCOUNT_REDIRECT_URI"]


def test_auth_login_uses_frontend_complete_uri_when_redirect_uri_is_blank() -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_ACCOUNT_OAUTH_AUTHORIZE_URL": "https://auth.example.com/oauth/authorize",
        "POE_ACCOUNT_OAUTH_SCOPE": "account:profile account:stashes",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    response = app.handle(
        method="GET",
        raw_path="/api/v1/auth/login",
        headers={"Origin": "https://app.example.com"},
        body_reader=BytesIO(b""),
    )

    payload = json.loads(response.body.decode("utf-8"))
    parsed = urlparse(payload["authorizeUrl"])
    query = parse_qs(parsed.query)

    assert response.status == 200
    assert set(payload) == {"authorizeUrl"}
    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.example.com"
    assert parsed.path == "/oauth/authorize"
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [env["POE_ACCOUNT_FRONTEND_COMPLETE_URI"]]
    assert query["scope"] == [env["POE_ACCOUNT_OAUTH_SCOPE"]]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"][0]
    assert query["code_challenge"][0]


def test_auth_callback_exchanges_code_and_sets_session_cookie(tmp_path) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
        "POE_AUTH_COOKIE_SECURE": "true",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    login_response = app.handle(
        method="GET",
        raw_path="/api/v1/auth/login",
        headers={"Origin": "https://app.example.com"},
        body_reader=BytesIO(b""),
    )
    login_payload = json.loads(login_response.body.decode("utf-8"))
    state = parse_qs(urlparse(login_payload["authorizeUrl"]).query)["state"][0]
    callback_path = f"/api/v1/auth/callback?code=code-123&state={state}"

    exchange = OAuthExchangeResult(
        account_name="qa-exile",
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="bearer",
        expires_in=3600,
        scope="account:profile account:stashes",
    )
    with mock.patch(
        "poe_trade.api.app.exchange_oauth_code", return_value=exchange
    ) as mocked_exchange:
        with mock.patch(
            "poe_trade.api.app.create_session",
            return_value={
                "session_id": "session-123",
                "account_name": "qa-exile",
                "expires_at": "2026-01-01T00:00:00Z",
                "scope": ["account:profile", "account:stashes"],
            },
        ) as mocked_session:
            response = app.handle(
                method="GET",
                raw_path=callback_path,
                headers={"Origin": "https://app.example.com"},
                body_reader=BytesIO(b""),
            )

    payload = json.loads(response.body.decode("utf-8"))

    assert response.status == 200
    assert payload["status"] == "connected"
    assert payload["accountName"] == "qa-exile"
    assert "Set-Cookie" in response.headers
    assert "poe_session=session-123" in response.headers["Set-Cookie"]
    assert "Secure" in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]
    assert "Path=/" in response.headers["Set-Cookie"]
    mocked_exchange.assert_called_once_with(settings, code="code-123", state=state)
    mocked_session.assert_called_once_with(settings, account_name="qa-exile")


def test_auth_callback_persists_oauth_token_state(tmp_path) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    login_response = app.handle(
        method="GET",
        raw_path="/api/v1/auth/login",
        headers={"Origin": "https://app.example.com"},
        body_reader=BytesIO(b""),
    )
    login_payload = json.loads(login_response.body.decode("utf-8"))
    state = parse_qs(urlparse(login_payload["authorizeUrl"]).query)["state"][0]

    exchange = OAuthExchangeResult(
        account_name="qa-exile",
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="bearer",
        expires_in=3600,
        scope="account:profile account:stashes",
    )
    with mock.patch("poe_trade.api.app.exchange_oauth_code", return_value=exchange):
        response = app.handle(
            method="GET",
            raw_path=f"/api/v1/auth/callback?code=code-123&state={state}",
            headers={"Origin": "https://app.example.com"},
            body_reader=BytesIO(b""),
        )

    token_state = load_oauth_token_state(settings, account_name="qa-exile")

    assert response.status == 200
    assert token_state is not None
    assert token_state["account_name"] == "qa-exile"
    assert token_state["access_token"] == "access-token"
    assert token_state["refresh_token"] == "refresh-token"
    assert token_state["token_type"] == "bearer"
    assert token_state["scope"] == "account:profile account:stashes"
    assert token_state["status"] == "connected"
    assert token_state["expires_at"].endswith("Z")
    assert isinstance(token_state["updated_at"], str)


def test_auth_callback_rejects_empty_access_token_before_creating_session(
    tmp_path,
) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    login_response = app.handle(
        method="GET",
        raw_path="/api/v1/auth/login",
        headers={"Origin": "https://app.example.com"},
        body_reader=BytesIO(b""),
    )
    login_payload = json.loads(login_response.body.decode("utf-8"))
    state = parse_qs(urlparse(login_payload["authorizeUrl"]).query)["state"][0]
    exchange = OAuthExchangeResult(
        account_name="qa-exile",
        access_token="",
        refresh_token="refresh-token",
        token_type="bearer",
        expires_in=3600,
        scope="account:profile account:stashes",
    )

    with mock.patch("poe_trade.api.app.exchange_oauth_code", return_value=exchange):
        with mock.patch("poe_trade.api.app.create_session") as mocked_session:
            with pytest.raises(ApiError, match="missing access token") as exc:
                _ = app.handle(
                    method="GET",
                    raw_path=f"/api/v1/auth/callback?code=code-123&state={state}",
                    headers={"Origin": "https://app.example.com"},
                    body_reader=BytesIO(b""),
                )

    assert exc.value.code == "oauth_missing_access_token"
    assert exc.value.status == 502
    mocked_session.assert_not_called()
    assert load_oauth_token_state(settings, account_name="qa-exile") is None


def test_auth_logout_keeps_oauth_token_state_when_same_account_has_another_session(
    tmp_path,
) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    primary = create_session(settings, account_name="qa-exile")
    _ = create_session(settings, account_name="qa-exile")
    saved = save_oauth_token_state(
        settings,
        account_name="qa-exile",
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="bearer",
        scope="account:profile account:stashes",
        expires_at="2026-03-24T12:00:00Z",
        status="connected",
    )

    response = app.handle(
        method="POST",
        raw_path="/api/v1/auth/logout",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": f"poe_session={primary['session_id']}",
        },
        body_reader=BytesIO(b""),
    )

    assert response.status == 200
    assert load_oauth_token_state(settings, account_name="qa-exile") == saved


def test_auth_logout_keeps_legacy_credential_state_when_same_account_has_another_session(
    tmp_path,
) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    primary = create_session(settings, account_name="qa-exile")
    _ = create_session(settings, account_name="qa-exile")
    saved = save_credential_state(
        settings,
        account_name="qa-exile",
        poe_session_id="POESESSID-123",
        cf_clearance="cf-clearance-123",
        status="bootstrap_connected",
    )

    response = app.handle(
        method="POST",
        raw_path="/api/v1/auth/logout",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": f"poe_session={primary['session_id']}",
        },
        body_reader=BytesIO(b""),
    )

    assert response.status == 200
    assert load_credential_state(settings) == saved


def test_auth_logout_keeps_other_account_legacy_credential_state(tmp_path) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    session = create_session(settings, account_name="qa-exile")
    saved = save_credential_state(
        settings,
        account_name="other-exile",
        poe_session_id="POESESSID-999",
        cf_clearance="cf-clearance-999",
        status="bootstrap_connected",
    )

    response = app.handle(
        method="POST",
        raw_path="/api/v1/auth/logout",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": f"poe_session={session['session_id']}",
        },
        body_reader=BytesIO(b""),
    )

    assert response.status == 200
    assert load_credential_state(settings) == saved


def test_auth_logout_clears_oauth_token_state_for_last_session_account(
    tmp_path,
) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    session = create_session(settings, account_name="qa-exile")
    _ = save_oauth_token_state(
        settings,
        account_name="qa-exile",
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="bearer",
        scope="account:profile account:stashes",
        expires_at="2026-03-24T12:00:00Z",
        status="connected",
    )

    response = app.handle(
        method="POST",
        raw_path="/api/v1/auth/logout",
        headers={
            "Origin": "https://app.example.com",
            "Cookie": f"poe_session={session['session_id']}",
        },
        body_reader=BytesIO(b""),
    )

    assert response.status == 200
    assert load_oauth_token_state(settings, account_name="qa-exile") is None


@pytest.mark.parametrize(
    ("error", "description", "code", "status"),
    [
        ("access_denied", "user cancelled", "oauth_access_denied", 401),
        ("invalid_request", "bad request", "oauth_callback_failed", 400),
    ],
)
def test_auth_callback_maps_provider_errors_without_creating_session(
    error: str,
    description: str,
    code: str,
    status: int,
    tmp_path,
) -> None:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_OAUTH_CLIENT_ID": "client-id",
        "POE_ACCOUNT_FRONTEND_COMPLETE_URI": "https://app.example.com/auth/callback",
        "POE_AUTH_STATE_DIR": str(tmp_path / "auth-state"),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        settings = Settings.from_env()
    app = ApiApp(settings, clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    with mock.patch("poe_trade.api.app.create_session") as mocked_session:
        with pytest.raises(ApiError, match=description) as exc:
            _ = app.handle(
                method="GET",
                raw_path=f"/api/v1/auth/callback?error={error}&error_description={description.replace(' ', '+')}",
                headers={"Origin": "https://app.example.com"},
                body_reader=BytesIO(b""),
            )

    assert exc.value.code == code
    assert exc.value.status == status
    mocked_session.assert_not_called()
