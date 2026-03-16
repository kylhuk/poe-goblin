from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from poe_trade.config.settings import Settings


_ACCOUNT_NAME_TEXT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{1,63}$")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _state_dir(settings: Settings) -> Path:
    root = Path(settings.auth_state_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    _ = path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _state_path(settings: Settings) -> Path:
    return _state_dir(settings) / "oauth-state.json"


def _sessions_path(settings: Settings) -> Path:
    return _state_dir(settings) / "sessions.json"


def credential_state_path(settings: Settings) -> Path:
    return _state_dir(settings) / "credential-state.json"


def load_credential_state(settings: Settings) -> dict[str, Any]:
    payload = _load_json(credential_state_path(settings))
    account_name = payload.get("account_name")
    poe_session_id = payload.get("poe_session_id")
    status = payload.get("status")
    updated_at = payload.get("updated_at")
    if not isinstance(account_name, str):
        account_name = ""
    if not isinstance(poe_session_id, str):
        poe_session_id = ""
    if not isinstance(status, str):
        status = "unknown"
    if not isinstance(updated_at, str):
        updated_at = _iso(_now())
    return {
        "account_name": account_name,
        "poe_session_id": poe_session_id,
        "status": status,
        "updated_at": updated_at,
    }


def save_credential_state(
    settings: Settings,
    *,
    account_name: str,
    status: str,
    poe_session_id: str = "",
) -> dict[str, Any]:
    payload = {
        "account_name": account_name,
        "poe_session_id": poe_session_id.strip(),
        "status": status,
        "updated_at": _iso(_now()),
    }
    _save_json(credential_state_path(settings), payload)
    return payload


def clear_credential_state(settings: Settings) -> dict[str, Any]:
    return save_credential_state(
        settings,
        account_name="",
        poe_session_id="",
        status="logged_out",
    )


def resolve_account_name(settings: Settings, *, poe_session_id: str) -> str:
    trimmed_session_id = poe_session_id.strip()
    if not trimmed_session_id:
        raise ValueError("poeSessionId is required")
    request_headers = {
        "Accept": "application/json, text/plain;q=0.9",
        "Cookie": f"POESESSID={trimmed_session_id}",
        "User-Agent": settings.poe_user_agent,
    }
    urls = _account_name_candidate_urls(settings)
    for url in urls:
        request = urllib.request.Request(url, headers=request_headers, method="GET")
        try:
            with urllib.request.urlopen(
                request, timeout=settings.poe_request_timeout
            ) as resp:
                body = resp.read().decode("utf-8", errors="strict")
        except (UnicodeDecodeError, urllib.error.URLError):
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            account_name = _extract_account_name_from_text(body)
            if account_name:
                return account_name
            continue
        account_name = _extract_account_name(payload)
        if account_name:
            return account_name
    raise ValueError("unable to resolve account name")


def _account_name_candidate_urls(settings: Settings) -> tuple[str, ...]:
    base = settings.poe_api_base_url.rstrip("/")
    candidates = (
        f"{base}/account/profile",
        f"{base}/account-profile",
        f"{base}/account",
        "https://www.pathofexile.com/api/account-profile",
        "https://www.pathofexile.com/character-window/get-account-name",
    )
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        deduped.append(candidate)
        seen.add(candidate)
    return tuple(deduped)


def _extract_account_name(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("accountName", "account_name", "name"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        nested = payload.get("account")
        if isinstance(nested, dict):
            return _extract_account_name(nested)
    return None


def _extract_account_name_from_text(payload: str) -> str | None:
    candidate = payload.strip()
    if not candidate:
        return None
    if "<" in candidate or "\n" in candidate or "\r" in candidate:
        return None
    if not _ACCOUNT_NAME_TEXT_PATTERN.match(candidate):
        return None
    return candidate


@dataclass(frozen=True)
class LoginTransaction:
    state: str
    code_verifier: str
    code_challenge: str
    created_at: str
    expires_at: str


def begin_login(settings: Settings) -> LoginTransaction:
    raw_verifier = secrets.token_urlsafe(48)
    code_verifier = raw_verifier[:128]
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    state = secrets.token_urlsafe(24)
    created = _now()
    expires = created + timedelta(seconds=30)
    tx = LoginTransaction(
        state=state,
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        created_at=_iso(created),
        expires_at=_iso(expires),
    )
    _save_json(
        _state_path(settings),
        {
            "state": tx.state,
            "code_verifier": tx.code_verifier,
            "code_challenge": tx.code_challenge,
            "created_at": tx.created_at,
            "expires_at": tx.expires_at,
        },
    )
    return tx


def validate_state(settings: Settings, *, state: str) -> bool:
    payload = _load_json(_state_path(settings))
    if payload.get("state") != state:
        return False
    expires_raw = payload.get("expires_at")
    if not isinstance(expires_raw, str):
        return False
    try:
        expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return _now() <= expires


def create_session(settings: Settings, *, account_name: str) -> dict[str, Any]:
    sessions = _load_json(_sessions_path(settings))
    session_id = secrets.token_urlsafe(32)
    expires = _now() + timedelta(days=7)
    session = {
        "session_id": session_id,
        "account_name": account_name,
        "status": "connected",
        "created_at": _iso(_now()),
        "expires_at": _iso(expires),
        "scope": [
            part.strip()
            for part in settings.poe_account_oauth_scope.split(" ")
            if part.strip()
        ],
    }
    sessions[session_id] = session
    _save_json(_sessions_path(settings), sessions)
    return session


def get_session(settings: Settings, *, session_id: str | None) -> dict[str, Any] | None:
    if not session_id:
        return None
    sessions = _load_json(_sessions_path(settings))
    row = sessions.get(session_id)
    if not isinstance(row, dict):
        return None
    expires_raw = row.get("expires_at")
    if not isinstance(expires_raw, str):
        return None
    try:
        expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if _now() > expires:
        return {
            "session_id": session_id,
            "status": "session_expired",
            "account_name": row.get("account_name") or "",
            "expires_at": expires_raw,
            "scope": row.get("scope") or [],
        }
    return row


def clear_session(settings: Settings, *, session_id: str | None) -> None:
    if not session_id:
        return
    sessions = _load_json(_sessions_path(settings))
    if session_id in sessions:
        del sessions[session_id]
        _save_json(_sessions_path(settings), sessions)


def authorize_redirect(settings: Settings, tx: LoginTransaction) -> str:
    base = settings.poe_account_oauth_authorize_url
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.oauth_client_id,
            "redirect_uri": settings.poe_account_redirect_uri,
            "scope": settings.poe_account_oauth_scope,
            "state": tx.state,
            "code_challenge": tx.code_challenge,
            "code_challenge_method": "S256",
        },
        quote_via=quote,
    )
    return f"{base}?{query}"
