from __future__ import annotations

import json
import os
from io import BytesIO
from unittest import mock
from typing import cast

import pytest

import poe_trade.api.app as api_app_module
from poe_trade.api.responses import Response
from poe_trade.api.app import make_handler
from poe_trade.config.settings import Settings
from poe_trade.db import ClickHouseClient
from poe_trade.ml import workflows


def _settings() -> Settings:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_API_CORS_ORIGINS": "https://app.example.com",
        "POE_API_MAX_BODY_BYTES": "32768",
        "POE_API_LEAGUE_ALLOWLIST": "Mirage",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        return Settings.from_env()


def test_handler_logs_request_and_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs: list[str] = []

    def _info(*args: object, **kwargs: object) -> None:
        _ = kwargs
        logs.append(str(args[1]))

    monkeypatch.setattr(api_app_module.logger, "info", _info)
    monkeypatch.setattr(
        workflows,
        "warmup_active_models",
        lambda client, *, league: {
            "lastAttemptAt": None,
            "routes": {"_global": "warm"},
        },
    )

    seen: dict[str, object] = {}

    def _handle(
        *, method: str, raw_path: str, headers: dict[str, str], body_reader: BytesIO
    ) -> Response:
        seen["method"] = method
        seen["raw_path"] = raw_path
        seen["headers"] = headers
        seen["body"] = body_reader.read()
        return Response(
            status=201,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": "11",
            },
            body=b'{"ok":true}',
        )

    app = api_app_module.ApiApp(_settings(), ClickHouseClient(endpoint="http://ch"))
    monkeypatch.setattr(app, "handle", _handle)
    handler_cls = make_handler(app)
    response_headers: list[tuple[str, str]] = []

    class _Handler:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {
                "Content-Length": "7",
                "Content-Type": "application/json",
                "X-Test": "yes",
            }
            self.path: str = "/api/v1/test?x=1"
            self.rfile: BytesIO = BytesIO(b'{"a":1}')
            self.wfile: BytesIO = BytesIO()

        def send_response(self, status: int) -> None:
            seen["status"] = status

        def send_header(self, key: str, value: str) -> None:
            response_headers.append((key, value))

        def end_headers(self) -> None:
            seen["ended"] = True

    handler = _Handler()
    getattr(handler_cls, "_handle")(handler, "POST")

    assert seen["method"] == "POST"
    assert seen["raw_path"] == "/api/v1/test?x=1"
    assert seen["body"] == b'{"a":1}'
    assert seen["status"] == 201
    assert seen["ended"] is True
    assert response_headers == [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", "11"),
    ]

    request_log = cast(dict[str, object], json.loads(logs[0]))
    response_log = cast(dict[str, object], json.loads(logs[1]))
    assert request_log == {
        "request": {
            "method": "POST",
            "path": "/api/v1/test?x=1",
            "headers": {
                "Content-Length": "7",
                "Content-Type": "application/json",
                "X-Test": "yes",
            },
            "body": '{"a":1}',
        }
    }
    assert response_log == {
        "response": {
            "status": 201,
            "headers": {
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": "11",
            },
            "body": '{"ok":true}',
        }
    }
