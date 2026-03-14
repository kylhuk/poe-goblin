from __future__ import annotations

import json
from typing import Any

from poe_trade.config.settings import Settings
from poe_trade.db import ClickHouseClient
from poe_trade.db.clickhouse import ClickHouseClientError
from poe_trade.ml import workflows


class BackendUnavailable(RuntimeError):
    pass


def contract_payload(settings: Settings) -> dict[str, Any]:
    return {
        "version": "v1",
        "auth_mode": "bearer_operator_token",
        "allowed_leagues": list(settings.api_league_allowlist),
        "routes": {
            "healthz": "/healthz",
            "ml_contract": "/api/v1/ml/contract",
            "ml_status": "/api/v1/ml/leagues/{league}/status",
            "ml_predict_one": "/api/v1/ml/leagues/{league}/predict-one",
            "ml_automation_status": "/api/v1/ml/leagues/{league}/automation/status",
            "ml_automation_history": "/api/v1/ml/leagues/{league}/automation/history",
        },
        "non_goals": [
            "no_train_loop_route",
            "no_evaluate_route",
            "no_report_route",
            "no_predict_batch_route",
        ],
    }


def ensure_allowed_league(league: str, settings: Settings) -> None:
    if league not in settings.api_league_allowlist:
        raise ValueError(f"league {league!r} is not allowed")


def fetch_status(client: ClickHouseClient, *, league: str) -> dict[str, Any]:
    try:
        payload = workflows.status(client, league=league, run="latest")
    except ClickHouseClientError as exc:
        raise BackendUnavailable("status backend unavailable") from exc
    except Exception as exc:
        raise BackendUnavailable("status backend unavailable") from exc
    return map_status_payload(league=league, payload=payload)


def fetch_predict_one(
    client: ClickHouseClient,
    *,
    league: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    clipboard = validate_predict_one_request(request_payload)
    try:
        raw = workflows.predict_one(client, league=league, clipboard_text=clipboard)
    except ClickHouseClientError as exc:
        raise BackendUnavailable("predict backend unavailable") from exc
    except Exception as exc:
        raise BackendUnavailable("predict backend unavailable") from exc
    return {
        "league": league,
        "route": str(raw.get("route") or "fallback_abstain"),
        "price_p10": _opt_float(raw.get("price_p10")),
        "price_p50": _opt_float(raw.get("price_p50")),
        "price_p90": _opt_float(raw.get("price_p90")),
        "confidence_percent": _opt_float(raw.get("confidence_percent")),
        "sale_probability_percent": _opt_float(raw.get("sale_probability_percent")),
        "price_recommendation_eligible": bool(
            raw.get("price_recommendation_eligible", False)
        ),
        "fallback_reason": str(raw.get("fallback_reason") or ""),
    }


def fetch_automation_status(client: ClickHouseClient, *, league: str) -> dict[str, Any]:
    status_payload = fetch_status(client, league=league)
    history_rows = _query_rows(
        client,
        "SELECT run_id, status, stop_reason, active_model_version, updated_at "
        "FROM poe_trade.ml_train_runs "
        f"WHERE league = {_quote(league)} ORDER BY updated_at DESC LIMIT 1 FORMAT JSONEachRow",
    )
    latest = history_rows[0] if history_rows else {}
    active_model_version = _opt_model_version(latest.get("active_model_version"))
    if active_model_version is None:
        active_model_version = _opt_model_version(
            status_payload.get("active_model_version")
        )
    return {
        "league": league,
        "status": status_payload.get("status"),
        "activeModelVersion": active_model_version,
        "latestRun": {
            "runId": latest.get("run_id"),
            "status": latest.get("status"),
            "stopReason": latest.get("stop_reason"),
            "updatedAt": str(latest.get("updated_at") or "").replace(" ", "T") + "Z"
            if latest.get("updated_at")
            else None,
        }
        if latest
        else None,
        "promotionVerdict": status_payload.get("promotion_verdict"),
        "routeHotspots": status_payload.get("route_hotspots") or [],
    }


def fetch_automation_history(
    client: ClickHouseClient, *, league: str, limit: int = 20
) -> dict[str, Any]:
    rows = _query_rows(
        client,
        "SELECT run_id, status, stop_reason, active_model_version, tuning_config_id, eval_run_id, updated_at "
        "FROM poe_trade.ml_train_runs "
        f"WHERE league = {_quote(league)} ORDER BY updated_at DESC LIMIT {max(1, limit)} FORMAT JSONEachRow",
    )
    return {
        "league": league,
        "history": [
            {
                "runId": row.get("run_id"),
                "status": row.get("status"),
                "stopReason": row.get("stop_reason"),
                "activeModelVersion": _opt_model_version(
                    row.get("active_model_version")
                ),
                "tuningConfigId": row.get("tuning_config_id"),
                "evalRunId": row.get("eval_run_id"),
                "updatedAt": str(row.get("updated_at") or "").replace(" ", "T") + "Z"
                if row.get("updated_at")
                else None,
            }
            for row in rows
        ],
    }


def map_status_payload(*, league: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") == "no_runs":
        return {
            "league": league,
            "run": None,
            "status": "no_runs",
            "promotion_verdict": None,
            "stop_reason": None,
            "active_model_version": None,
            "latest_avg_mdape": None,
            "latest_avg_interval_coverage": None,
            "candidate_vs_incumbent": {},
            "route_hotspots": [],
        }
    return {
        "league": league,
        "run": _opt_str(payload.get("run_id")),
        "status": _opt_str(payload.get("status")),
        "promotion_verdict": _opt_str(payload.get("promotion_verdict")),
        "stop_reason": _opt_str(payload.get("stop_reason")),
        "active_model_version": _opt_model_version(payload.get("active_model_version")),
        "latest_avg_mdape": _opt_float(payload.get("latest_avg_mdape")),
        "latest_avg_interval_coverage": _opt_float(
            payload.get("latest_avg_interval_coverage")
        ),
        "candidate_vs_incumbent": _as_dict(payload.get("candidate_vs_incumbent")),
        "route_hotspots": _as_list(payload.get("route_hotspots")),
    }


def validate_predict_one_request(payload: dict[str, Any]) -> str:
    expected_keys = {"input_format", "payload", "output_mode"}
    extra = set(payload) - expected_keys
    if extra:
        raise ValueError("unexpected request field")
    if payload.get("input_format") != "poe-clipboard":
        raise ValueError("input_format must be poe-clipboard")
    output_mode = payload.get("output_mode")
    if output_mode is not None and output_mode != "json":
        raise ValueError("output_mode must be json")
    raw_payload = payload.get("payload")
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        raise ValueError("payload must be a non-empty string")
    return raw_payload


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _opt_model_version(value: Any) -> str | None:
    normalized = _opt_str(value)
    if normalized is None:
        return None
    compact = normalized.strip()
    if not compact:
        return None
    if compact.lower() in {"none", "null", "no_model"}:
        return None
    return compact


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _query_rows(client: ClickHouseClient, query: str) -> list[dict[str, Any]]:
    try:
        payload = client.execute(query).strip()
    except ClickHouseClientError as exc:
        raise BackendUnavailable("status backend unavailable") from exc
    if not payload:
        return []
    rows: list[dict[str, Any]] = []
    for line in payload.splitlines():
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"
