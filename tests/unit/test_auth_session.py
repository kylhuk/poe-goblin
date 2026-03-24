from __future__ import annotations

import os
import json
import threading
import time
import urllib.error
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest

import poe_trade.api.auth_session as auth_session
from poe_trade.api.auth_session import (
    _account_name_html_urls,
    begin_login,
    clear_credential_state,
    clear_oauth_token_state,
    clear_session,
    consume_login_state,
    create_session,
    credential_state_path,
    exchange_oauth_code,
    has_connected_session_for_account,
    load_credential_state,
    load_oauth_credential_state,
    load_oauth_token_state,
    OAuthExchangeError,
    prune_login_transactions,
    resolve_account_name,
    save_credential_state,
    save_oauth_credential_state,
    save_oauth_token_state,
    validate_state,
)
from poe_trade.config.settings import Settings


def _settings(state_dir: str) -> Settings:
    with mock.patch.dict(
        os.environ,
        {
            "POE_AUTH_STATE_DIR": state_dir,
            "POE_OAUTH_CLIENT_ID": "client-id",
        },
        clear=True,
    ):
        return Settings.from_env()


def test_credential_state_path_stable_under_auth_state_dir(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    path = credential_state_path(settings)

    assert path == tmp_path / "auth-state" / "credential-state.json"
    assert path.parent.exists()


def test_save_and_load_credential_state_round_trip(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    saved = save_credential_state(
        settings,
        account_name="qa-exile",
        cf_clearance="cf-clearance-123",
        status="token_present",
    )
    loaded = load_credential_state(settings)

    assert saved["account_name"] == "qa-exile"
    assert saved["status"] == "token_present"
    assert isinstance(saved["updated_at"], str)
    assert loaded == saved


def test_save_and_load_oauth_credential_state_round_trip(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    saved = save_oauth_credential_state(
        settings,
        account_name="qa-exile",
        poe_session_id="POESESSID-123",
        cf_clearance="cf-clearance-123",
        status="connected",
    )
    loaded = load_oauth_credential_state(settings)

    assert saved["account_name"] == "qa-exile"
    assert saved["poe_session_id"] == "POESESSID-123"
    assert saved["cf_clearance"] == "cf-clearance-123"
    assert saved["status"] == "connected"
    assert isinstance(saved["updated_at"], str)
    assert loaded == saved


def test_load_credential_state_defaults_when_file_is_missing(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    loaded = load_credential_state(settings)

    assert loaded["account_name"] == ""
    assert loaded["poe_session_id"] == ""
    assert loaded["cf_clearance"] == ""
    assert loaded["status"] == "unknown"
    assert isinstance(loaded["updated_at"], str)


def test_clear_credential_state_resets_sensitive_fields(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    _ = save_credential_state(
        settings,
        account_name="qa-exile",
        poe_session_id="POESESSID-123",
        cf_clearance="cf-clearance-123",
        status="bootstrap_connected",
    )

    cleared = clear_credential_state(settings)

    assert cleared["status"] == "logged_out"
    assert cleared["account_name"] == ""
    assert cleared["poe_session_id"] == ""
    assert cleared["cf_clearance"] == ""
    assert load_credential_state(settings) == cleared


def test_save_and_load_oauth_token_state_round_trip(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

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
    loaded = load_oauth_token_state(settings, account_name="qa-exile")

    assert saved["account_name"] == "qa-exile"
    assert saved["access_token"] == "access-token"
    assert saved["refresh_token"] == "refresh-token"
    assert saved["token_type"] == "bearer"
    assert saved["scope"] == "account:profile account:stashes"
    assert saved["expires_at"] == "2026-03-24T12:00:00Z"
    assert saved["status"] == "connected"
    assert isinstance(saved["updated_at"], str)
    assert loaded == saved


def test_consume_login_state_marks_row_used_once(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    tx = begin_login(settings)

    consumed = consume_login_state(settings, state=tx.state)

    assert consumed.state == tx.state
    assert consumed.used_at
    assert validate_state(settings, state=tx.state) is False
    with pytest.raises(OAuthExchangeError, match="state already used"):
        _ = consume_login_state(settings, state=tx.state)


def test_prune_login_transactions_removes_used_and_expired_rows_with_bound(
    tmp_path: Path,
) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    payload = auth_session._load_json(auth_session._state_path(settings))
    transactions = payload.get("transactions")
    if not isinstance(transactions, dict):
        transactions = {}
        payload["transactions"] = transactions

    base_now = auth_session._now()
    for index in range(33):
        tx = begin_login(settings)
        transactions[tx.state] = {
            "state": tx.state,
            "code_verifier": tx.code_verifier,
            "code_challenge": tx.code_challenge,
            "redirect_uri": tx.redirect_uri,
            "created_at": tx.created_at,
            "expires_at": tx.expires_at,
            "used_at": (base_now - timedelta(seconds=index))
            .isoformat()
            .replace("+00:00", "Z"),
        }

    transactions["expired-state"] = {
        "state": "expired-state",
        "code_verifier": "verifier",
        "code_challenge": "challenge",
        "redirect_uri": "https://app.example.com/auth/callback",
        "created_at": (base_now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        "expires_at": (base_now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "used_at": "",
    }
    auth_session._save_json(auth_session._state_path(settings), payload)

    removed = prune_login_transactions(settings, now=base_now)
    pruned = auth_session._load_json(auth_session._state_path(settings))
    pruned_transactions = pruned["transactions"]

    assert removed == 2
    assert isinstance(pruned_transactions, dict)
    assert len(pruned_transactions) == 32
    assert "expired-state" not in pruned_transactions


def test_clear_oauth_token_state_removes_only_requested_account(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    _ = save_oauth_token_state(
        settings,
        account_name="qa-exile",
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="bearer",
        scope="account:profile",
        expires_at="2026-03-24T12:00:00Z",
        status="connected",
    )
    other = save_oauth_token_state(
        settings,
        account_name="second-exile",
        access_token="other-access-token",
        refresh_token="other-refresh-token",
        token_type="bearer",
        scope="account:stashes",
        expires_at="2026-03-25T12:00:00Z",
        status="connected",
    )

    clear_oauth_token_state(settings, account_name="qa-exile")

    assert load_oauth_token_state(settings, account_name="qa-exile") is None
    assert load_oauth_token_state(settings, account_name="second-exile") == other


def test_save_oauth_token_state_serializes_concurrent_writes(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    first_loaded = threading.Event()
    allow_first_to_continue = threading.Event()
    second_entered = threading.Event()
    original_load_json = auth_session._load_json
    call_count = 0
    call_lock = threading.Lock()

    def _load_json(path: Path):
        nonlocal call_count
        if path != auth_session.oauth_token_state_path(settings):
            return original_load_json(path)
        with call_lock:
            call_count += 1
            current = call_count
        if current == 1:
            first_loaded.set()
            assert allow_first_to_continue.wait(timeout=1)
        elif current == 2 and not allow_first_to_continue.is_set():
            second_entered.set()
        return original_load_json(path)

    with mock.patch("poe_trade.api.auth_session._load_json", side_effect=_load_json):
        first_thread = threading.Thread(
            target=save_oauth_token_state,
            kwargs={
                "settings": settings,
                "account_name": "qa-exile",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
                "scope": "account:profile",
                "expires_at": "2026-03-24T12:00:00Z",
                "status": "connected",
            },
        )
        second_thread = threading.Thread(
            target=save_oauth_token_state,
            kwargs={
                "settings": settings,
                "account_name": "second-exile",
                "access_token": "other-access-token",
                "refresh_token": "other-refresh-token",
                "token_type": "bearer",
                "scope": "account:stashes",
                "expires_at": "2026-03-25T12:00:00Z",
                "status": "connected",
            },
        )
        first_thread.start()
        assert first_loaded.wait(timeout=1)
        second_thread.start()
        time.sleep(0.05)
        assert second_entered.is_set() is False
        allow_first_to_continue.set()
        first_thread.join(timeout=1)
        second_thread.join(timeout=1)


def test_clear_oauth_token_state_serializes_concurrent_mutation(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    _ = save_oauth_token_state(
        settings,
        account_name="qa-exile",
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="bearer",
        scope="account:profile",
        expires_at="2026-03-24T12:00:00Z",
        status="connected",
    )
    first_loaded = threading.Event()
    allow_first_to_continue = threading.Event()
    second_entered = threading.Event()
    original_load_json = auth_session._load_json
    call_count = 0
    call_lock = threading.Lock()

    def _load_json(path: Path):
        nonlocal call_count
        if path != auth_session.oauth_token_state_path(settings):
            return original_load_json(path)
        with call_lock:
            call_count += 1
            current = call_count
        if current == 1:
            first_loaded.set()
            assert allow_first_to_continue.wait(timeout=1)
        elif current == 2 and not allow_first_to_continue.is_set():
            second_entered.set()
        return original_load_json(path)

    with mock.patch("poe_trade.api.auth_session._load_json", side_effect=_load_json):
        clear_thread = threading.Thread(
            target=clear_oauth_token_state,
            kwargs={"settings": settings, "account_name": "qa-exile"},
        )
        save_thread = threading.Thread(
            target=save_oauth_token_state,
            kwargs={
                "settings": settings,
                "account_name": "second-exile",
                "access_token": "other-access-token",
                "refresh_token": "other-refresh-token",
                "token_type": "bearer",
                "scope": "account:stashes",
                "expires_at": "2026-03-25T12:00:00Z",
                "status": "connected",
            },
        )
        clear_thread.start()
        assert first_loaded.wait(timeout=1)
        save_thread.start()
        time.sleep(0.05)
        assert second_entered.is_set() is False
        allow_first_to_continue.set()
        clear_thread.join(timeout=1)
        save_thread.join(timeout=1)


def test_create_session_serializes_concurrent_writes(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    first_loaded = threading.Event()
    allow_first_to_continue = threading.Event()
    second_entered = threading.Event()
    original_load_json = auth_session._load_json
    call_count = 0
    call_lock = threading.Lock()

    def _load_json(path: Path):
        nonlocal call_count
        if path != auth_session._sessions_path(settings):
            return original_load_json(path)
        with call_lock:
            call_count += 1
            current = call_count
        if current == 1:
            first_loaded.set()
            assert allow_first_to_continue.wait(timeout=1)
        elif current == 2 and not allow_first_to_continue.is_set():
            second_entered.set()
        return original_load_json(path)

    with mock.patch("poe_trade.api.auth_session._load_json", side_effect=_load_json):
        first_thread = threading.Thread(
            target=create_session,
            kwargs={"settings": settings, "account_name": "qa-exile"},
        )
        second_thread = threading.Thread(
            target=create_session,
            kwargs={"settings": settings, "account_name": "second-exile"},
        )
        first_thread.start()
        assert first_loaded.wait(timeout=1)
        second_thread.start()
        time.sleep(0.05)
        assert second_entered.is_set() is False
        allow_first_to_continue.set()
        first_thread.join(timeout=1)
        second_thread.join(timeout=1)


def test_has_connected_session_for_account_serializes_with_clear_session(
    tmp_path: Path,
) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    session = create_session(settings, account_name="qa-exile")
    first_loaded = threading.Event()
    allow_first_to_continue = threading.Event()
    second_entered = threading.Event()
    original_load_json = auth_session._load_json
    call_count = 0
    call_lock = threading.Lock()

    def _load_json(path: Path):
        nonlocal call_count
        if path != auth_session._sessions_path(settings):
            return original_load_json(path)
        with call_lock:
            call_count += 1
            current = call_count
        if current == 1:
            first_loaded.set()
            assert allow_first_to_continue.wait(timeout=1)
        elif current == 2 and not allow_first_to_continue.is_set():
            second_entered.set()
        return original_load_json(path)

    with mock.patch("poe_trade.api.auth_session._load_json", side_effect=_load_json):
        clear_thread = threading.Thread(
            target=clear_session,
            kwargs={"settings": settings, "session_id": session["session_id"]},
        )
        check_thread = threading.Thread(
            target=has_connected_session_for_account,
            kwargs={"settings": settings, "account_name": "qa-exile"},
        )
        clear_thread.start()
        assert first_loaded.wait(timeout=1)
        check_thread.start()
        time.sleep(0.05)
        assert second_entered.is_set() is False
        allow_first_to_continue.set()
        clear_thread.join(timeout=1)
        check_thread.join(timeout=1)


def test_begin_login_keeps_multiple_concurrent_oauth_transactions(
    tmp_path: Path,
) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    first = begin_login(settings)
    second = begin_login(settings)
    seen_form: dict[str, str] = {}

    def _http_post_form(url: str, *, form: dict[str, str], headers, timeout):
        seen_form.update(form)
        return (
            json.dumps(
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "token_type": "bearer",
                    "scope": settings.poe_account_oauth_scope,
                    "accountName": "qa-exile",
                }
            ),
            200,
        )

    assert validate_state(settings, state=first.state) is True
    assert validate_state(settings, state=second.state) is True

    with mock.patch(
        "poe_trade.api.auth_session._http_post_form", side_effect=_http_post_form
    ):
        result = exchange_oauth_code(settings, code="code-123", state=first.state)

    assert result.account_name == "qa-exile"
    assert seen_form["code_verifier"] == first.code_verifier


def test_login_transaction_paths_stay_consistent_during_partial_state_snapshots(
    tmp_path: Path,
) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    first = begin_login(settings)

    class _RecordingLock:
        def __init__(self) -> None:
            self.depth = 0

        def __enter__(self):
            self.depth += 1
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.depth -= 1

    lock = _RecordingLock()
    original_load_json = auth_session._load_json
    partial_write_active = True

    def _load_json(path: Path):
        if path != auth_session._state_path(settings):
            return original_load_json(path)
        if partial_write_active and lock.depth == 0:
            return {}
        return original_load_json(path)

    with mock.patch.object(auth_session, "_LOGIN_TRANSACTION_LOCK", lock):
        with mock.patch(
            "poe_trade.api.auth_session._load_json", side_effect=_load_json
        ):
            second = begin_login(settings)

            assert validate_state(settings, state=first.state) is True

            with mock.patch(
                "poe_trade.api.auth_session._http_post_form",
                return_value=(
                    json.dumps(
                        {
                            "access_token": "access-token",
                            "refresh_token": "refresh-token",
                            "token_type": "bearer",
                            "scope": settings.poe_account_oauth_scope,
                            "accountName": "qa-exile",
                        }
                    ),
                    200,
                ),
            ):
                result = exchange_oauth_code(
                    settings, code="code-123", state=first.state
                )

            assert result.account_name == "qa-exile"
            assert validate_state(settings, state=first.state) is False

    payload = original_load_json(auth_session._state_path(settings))
    assert set(payload["transactions"]) == {first.state, second.state}
    assert payload["transactions"][first.state]["used_at"]
    assert payload["transactions"][second.state]["used_at"] == ""


def test_prunes_old_and_excess_consumed_login_transactions(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    active = begin_login(settings)
    fixed_now = auth_session._now()
    old_used_at = fixed_now - timedelta(days=2)
    recent_used_at = fixed_now - timedelta(minutes=5)
    payload = {
        "state": active.state,
        "code_verifier": active.code_verifier,
        "code_challenge": active.code_challenge,
        "redirect_uri": active.redirect_uri,
        "created_at": active.created_at,
        "expires_at": active.expires_at,
        "used_at": "",
        "transactions": {
            active.state: {
                "state": active.state,
                "code_verifier": active.code_verifier,
                "code_challenge": active.code_challenge,
                "redirect_uri": active.redirect_uri,
                "created_at": active.created_at,
                "expires_at": active.expires_at,
                "used_at": "",
            },
            "old-consumed": {
                "state": "old-consumed",
                "code_verifier": "old-verifier",
                "code_challenge": "old-challenge",
                "redirect_uri": active.redirect_uri,
                "created_at": old_used_at.isoformat().replace("+00:00", "Z"),
                "expires_at": (old_used_at + timedelta(minutes=10))
                .isoformat()
                .replace("+00:00", "Z"),
                "used_at": old_used_at.isoformat().replace("+00:00", "Z"),
            },
            "recent-consumed": {
                "state": "recent-consumed",
                "code_verifier": "recent-verifier",
                "code_challenge": "recent-challenge",
                "redirect_uri": active.redirect_uri,
                "created_at": recent_used_at.isoformat().replace("+00:00", "Z"),
                "expires_at": (recent_used_at + timedelta(minutes=10))
                .isoformat()
                .replace("+00:00", "Z"),
                "used_at": recent_used_at.isoformat().replace("+00:00", "Z"),
            },
        },
    }

    auth_session._prune_login_transactions_payload(
        payload, now=fixed_now + timedelta(minutes=1)
    )

    assert "old-consumed" not in payload["transactions"]
    assert "recent-consumed" in payload["transactions"]


def test_prunes_login_transaction_history_to_bounded_size(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    active = begin_login(settings)
    now = auth_session._now()
    transactions = {
        active.state: {
            "state": active.state,
            "code_verifier": active.code_verifier,
            "code_challenge": active.code_challenge,
            "redirect_uri": active.redirect_uri,
            "created_at": active.created_at,
            "expires_at": active.expires_at,
            "used_at": "",
        }
    }
    for index in range(33):
        consumed_at = now - timedelta(minutes=index + 1)
        transactions[f"consumed-{index}"] = {
            "state": f"consumed-{index}",
            "code_verifier": f"verifier-{index}",
            "code_challenge": f"challenge-{index}",
            "redirect_uri": active.redirect_uri,
            "created_at": "2026-03-24T00:00:00Z",
            "expires_at": "2026-03-24T00:10:00Z",
            "used_at": consumed_at.isoformat().replace("+00:00", "Z"),
        }
    payload = {
        "state": active.state,
        "code_verifier": active.code_verifier,
        "code_challenge": active.code_challenge,
        "redirect_uri": active.redirect_uri,
        "created_at": active.created_at,
        "expires_at": active.expires_at,
        "used_at": "",
        "transactions": transactions,
    }

    auth_session._prune_login_transactions_payload(payload, now=now)

    kept_keys = set(payload["transactions"])
    assert active.state in kept_keys
    assert len(kept_keys - {active.state}) == 32


def test_exchange_oauth_code_consumes_login_transaction_after_success(
    tmp_path: Path,
) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    tx = begin_login(settings)

    with mock.patch(
        "poe_trade.api.auth_session._http_post_form",
        return_value=(
            json.dumps(
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "token_type": "bearer",
                    "scope": settings.poe_account_oauth_scope,
                    "accountName": "qa-exile",
                }
            ),
            200,
        ),
    ):
        result = exchange_oauth_code(settings, code="code-123", state=tx.state)

    assert result.account_name == "qa-exile"
    stored = auth_session._load_json(auth_session._state_path(settings))
    assert stored["transactions"][tx.state]["used_at"]
    assert validate_state(settings, state=tx.state) is False
    with pytest.raises(OAuthExchangeError, match="invalid state"):
        _ = exchange_oauth_code(settings, code="code-456", state=tx.state)


def test_exchange_oauth_code_rejects_missing_access_token(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    tx = begin_login(settings)

    with mock.patch(
        "poe_trade.api.auth_session._http_post_form",
        return_value=(
            json.dumps(
                {
                    "refresh_token": "refresh-token",
                    "token_type": "bearer",
                    "scope": settings.poe_account_oauth_scope,
                    "accountName": "qa-exile",
                }
            ),
            200,
        ),
    ):
        with pytest.raises(OAuthExchangeError, match="missing access token"):
            _ = exchange_oauth_code(settings, code="code-123", state=tx.state)


def test_resolve_account_name_uses_poe_session_cookie(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"accountName": "qa-exile"}).encode("utf-8")

    with mock.patch("urllib.request.urlopen", return_value=_Response()) as urlopen_mock:
        account_name = resolve_account_name(settings, poe_session_id="POESESSID-123")

    request = urlopen_mock.call_args[0][0]
    assert account_name == "qa-exile"
    assert request.get_header("Cookie") == "POESESSID=POESESSID-123"


def test_account_name_html_urls_use_non_oauth_profile_pages(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    urls = _account_name_html_urls(settings)

    assert urls == (
        "https://www.pathofexile.com/my-account",
        "https://www.pathofexile.com/account/profile",
    )


def test_resolve_account_name_uses_plain_text_fallback_after_404(
    tmp_path: Path,
) -> None:
    settings = _settings(str(tmp_path / "auth-state"))
    attempted_urls: list[str] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b'<a href="/account/view-profile/qa-exile">qa-exile</a>'

    def _urlopen(request, timeout: float):
        attempted_urls.append(str(request.full_url))
        if request.full_url.endswith("/my-account"):
            return _Response()
        raise urllib.error.URLError("not found")

    with mock.patch("urllib.request.urlopen", side_effect=_urlopen):
        account_name = resolve_account_name(settings, poe_session_id="POESESSID-123")

    assert account_name == "qa-exile"
    assert attempted_urls[0].endswith("/account/profile")
    assert attempted_urls[-1].endswith("/my-account")


def test_resolve_account_name_reads_nested_profile_shape(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"account": {"name": "qa-exile"}}).encode("utf-8")

    with mock.patch("urllib.request.urlopen", return_value=_Response()):
        account_name = resolve_account_name(settings, poe_session_id="POESESSID-123")

    assert account_name == "qa-exile"


def test_resolve_account_name_raises_for_unresolvable_payload(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"unexpected": "shape"}).encode("utf-8")

    with mock.patch("urllib.request.urlopen", return_value=_Response()):
        with pytest.raises(ValueError, match="unable to resolve"):
            _ = resolve_account_name(settings, poe_session_id="POESESSID-123")


def test_resolve_account_name_rejects_html_error_bodies(tmp_path: Path) -> None:
    settings = _settings(str(tmp_path / "auth-state"))

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"<html><title>Not Found</title></html>"

    with mock.patch("urllib.request.urlopen", return_value=_Response()):
        with pytest.raises(ValueError, match="unable to resolve"):
            _ = resolve_account_name(settings, poe_session_id="POESESSID-123")
