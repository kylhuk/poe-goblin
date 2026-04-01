from __future__ import annotations

import json
import os
from io import BytesIO
from typing import cast
from unittest import mock

import pytest

from poe_trade.api import ml as api_ml
from poe_trade.api.app import ApiApp
from poe_trade.api.responses import ApiError
from poe_trade.config.settings import Settings
from poe_trade.db import ClickHouseClient
from poe_trade.db.clickhouse import ClickHouseClientError
from poe_trade.ml import workflows


@pytest.fixture(autouse=True)
def stub_ml_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "poe_trade.ml.workflows.warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )


@pytest.fixture(autouse=True)
def reset_ml_runtime_caches() -> None:
    workflows.reset_serving_runtime_caches()


def _settings() -> Settings:
    env = {
        "POE_API_OPERATOR_TOKEN": "phase1-token",
        "POE_API_CORS_ORIGINS": "https://app.example.com",
        "POE_API_MAX_BODY_BYTES": "128",
        "POE_API_LEAGUE_ALLOWLIST": "Mirage",
        "POE_ML_AUTOMATION_ENABLED": "true",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        return Settings.from_env()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer phase1-token"}


class _RecordingPredictClient:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.registry_query_count = 0
        self.profile_lookup_count = 0
        self.model_dir = "artifacts/ml/mirage_v1"
        self.model_version = "mirage-v1"
        self.promoted_at = "2026-03-19 10:00:00"
        self.profile_snapshot_window_id = "window-1"
        self.profile_as_of_ts = "2026-03-19 10:00:00"
        self.profile_support = 91
        self.profile_price = 13.25

    def execute(self, query: str) -> str:
        self.queries.append(query)
        if "FROM poe_trade.ml_model_registry_v1" in query and "route =" in query:
            self.registry_query_count += 1
            return (
                json.dumps(
                    {
                        "model_dir": self.model_dir,
                        "model_version": self.model_version,
                        "promoted_at": self.promoted_at,
                    }
                )
                + "\n"
            )
        if "FROM poe_trade.ml_serving_profile_v1" in query and "AND category" in query:
            self.profile_lookup_count += 1
            return (
                json.dumps(
                    {
                        "support_count_recent": self.profile_support,
                        "reference_price_p50": self.profile_price,
                        "snapshot_window_id": self.profile_snapshot_window_id,
                        "profile_as_of_ts": self.profile_as_of_ts,
                    }
                )
                + "\n"
            )
        if "SELECT max(as_of_ts) AS profile_as_of_ts" in query:
            return json.dumps({"profile_as_of_ts": self.profile_as_of_ts}) + "\n"
        if (
            "SELECT count() AS value FROM poe_trade.ml_serving_profile_v1" in query
            or "SELECT count() AS value" in query
            and "FROM poe_trade.ml_serving_profile_v1" in query
        ):
            return json.dumps({"value": 1}) + "\n"
        return ""


def _as_clickhouse(client: _RecordingPredictClient) -> ClickHouseClient:
    return cast(ClickHouseClient, cast(object, client))


def _stub_predict_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflows,
        "_parse_clipboard_item",
        lambda _text: {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
        },
    )
    monkeypatch.setattr(
        workflows,
        "_route_for_item",
        lambda _item: {
            "route": "sparse_retrieval",
            "route_reason": "sparse_high_dimensional",
            "support_count_recent": 20,
        },
    )
    monkeypatch.setattr(
        workflows,
        "_load_json_file",
        lambda _path: {"model_bundle_path": "", "train_row_count": 100},
    )
    monkeypatch.setattr(workflows, "_predict_with_artifact", lambda **_kwargs: None)


def test_healthz_shape_and_no_auth_required() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/healthz",
        headers={},
        body_reader=BytesIO(b""),
    )
    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["status"] == "ok"
    assert body["service"] == "api"
    assert body["version"] == "v1"
    assert body["ml"]["ready"] is True
    assert body["ml"]["leagues"]["Mirage"]["ready"] is True


def test_healthz_returns_degraded_when_ml_warmup_has_invalid_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.ml.workflows.warmup_active_models",
        lambda *_args, **_kwargs: {
            "lastAttemptAt": None,
            "routes": {"structured_boosted": "bundle_missing"},
        },
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/healthz",
        headers={},
        body_reader=BytesIO(b""),
    )
    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 503
    assert body["status"] == "degraded"
    assert body["ml"]["ready"] is False
    assert body["ml"]["leagues"]["Mirage"]["degradedRoutes"] == {
        "structured_boosted": "bundle_missing"
    }


def test_healthz_keeps_inactive_routes_non_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.ml.workflows.warmup_active_models",
        lambda *_args, **_kwargs: {
            "lastAttemptAt": None,
            "routes": {"structured_boosted": "inactive"},
        },
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/healthz",
        headers={},
        body_reader=BytesIO(b""),
    )
    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["status"] == "ok"
    assert body["ml"]["ready"] is True
    assert body["ml"]["leagues"]["Mirage"]["degradedRoutes"] == {}


def test_contract_exact_top_level_keys() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/api/v1/ml/contract",
        headers=_auth_headers(),
        body_reader=BytesIO(b""),
    )
    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert set(body) == {
        "version",
        "auth_mode",
        "allowed_leagues",
        "routes",
        "non_goals",
    }
    assert "ml_rollout" not in body["routes"]


def test_unknown_route_uses_shared_error_code() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError) as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/does-not-exist",
            headers={},
            body_reader=BytesIO(b""),
        )
    assert exc.value.status == 404
    assert exc.value.code == "route_not_found"


def test_wrong_method_uses_shared_error_code() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError) as exc:
        app.handle(
            method="POST",
            raw_path="/healthz",
            headers={},
            body_reader=BytesIO(b""),
        )
    assert exc.value.status == 405
    assert exc.value.code == "method_not_allowed"


def test_ml_status_returns_stable_no_runs_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_ml.workflows,
        "status",
        lambda _client, league, run: {
            "league": league,
            "status": "no_runs",
            "warmup": {"lastAttemptAt": None, "routes": {}},
        },
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/api/v1/ml/leagues/Mirage/status",
        headers=_auth_headers(),
        body_reader=BytesIO(b""),
    )
    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert set(body) == {
        "league",
        "run",
        "status",
        "promotion_verdict",
        "stop_reason",
        "active_model_version",
        "latest_avg_mdape",
        "latest_avg_interval_coverage",
        "candidate_vs_incumbent",
        "route_hotspots",
        "warmup",
        "route_decisions",
    }
    assert body["candidate_vs_incumbent"] == {}
    assert body["route_hotspots"] == []
    assert body["route_decisions"] == []
    assert body["warmup"]["routes"] == {}


def test_invalid_league_rejected() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError, match="league is not allowed") as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/ml/leagues/Standard/status",
            headers=_auth_headers(),
            body_reader=BytesIO(b""),
        )
    assert exc.value.code == "league_not_allowed"
    assert exc.value.status == 400


def test_status_backend_failure_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_client, league, run):
        raise ClickHouseClientError("db details should not leak")

    monkeypatch.setattr(api_ml.workflows, "status", _raise)
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError, match="backend unavailable") as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/ml/leagues/Mirage/status",
            headers=_auth_headers(),
            body_reader=BytesIO(b""),
        )
    assert exc.value.code == "backend_unavailable"
    assert exc.value.status == 503


def test_predict_one_returns_stable_dto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_ml.v3_serve,
        "predict_one_v3",
        lambda _client, league, clipboard_text: {
            "league": league,
            "route": "structured_boosted",
            "price_p10": 8.0,
            "price_p50": 10.0,
            "price_p90": 12.0,
            "confidence_percent": 62.0,
            "sale_probability_percent": 60.0,
            "price_recommendation_eligible": True,
            "fallback_reason": "",
            "internal_only": "ignore",
            "retrieval_stage": 3,
            "retrieval_candidate_count": 12,
            "retrieval_effective_support": 7,
            "retrieval_dropped_affixes": ["crafted", "synthetic"],
            "retrieval_degradation_reason": None,
            "retrieval_anchor_price": 9.75,
            "retrieval_anchor_low": 9.2,
            "retrieval_anchor_high": 11.3,
        },
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = {
        "input_format": "poe-clipboard",
        "payload": "item payload",
        "output_mode": "json",
    }
    body = json.dumps(payload).encode("utf-8")
    response = app.handle(
        method="POST",
        raw_path="/api/v1/ml/leagues/Mirage/predict-one",
        headers={**_auth_headers(), "Content-Length": str(len(body))},
        body_reader=BytesIO(body),
    )
    result = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    expected_keys = {
        "league",
        "route",
        "price_p10",
        "price_p50",
        "price_p90",
        "confidence_percent",
        "sale_probability_percent",
        "price_recommendation_eligible",
        "fallback_reason",
        "mlPredicted",
        "predictionSource",
        "estimateTrust",
        "estimateWarning",
        "ml_predicted",
        "prediction_source",
        "estimate_trust",
        "estimate_warning",
        "retrievalStage",
        "retrievalCandidateCount",
        "retrievalEffectiveSupport",
        "retrievalDroppedAffixes",
        "retrievalDegradationReason",
        "retrievalAnchorPrice",
        "retrievalAnchorLow",
        "retrievalAnchorHigh",
        "retrieval_stage",
        "retrieval_candidate_count",
        "retrieval_effective_support",
        "retrieval_dropped_affixes",
        "retrieval_degradation_reason",
        "retrieval_anchor_price",
        "retrieval_anchor_low",
        "retrieval_anchor_high",
    }
    assert expected_keys.issubset(set(result))

    assert result["retrievalStage"] == 3
    assert result["retrieval_candidate_count"] == 12
    assert result["retrieval_effective_support"] == 7
    assert result["retrieval_dropped_affixes"] == ["crafted", "synthetic"]


def test_predict_one_normalize_retrieval_aliases_are_bidirectional() -> None:
    payload = api_ml.normalize_predict_one_payload(
        league="Mirage",
        payload={
            "route": "sparse_retrieval",
            "price_p50": 10.0,
            "price_p10": 9.0,
            "price_p90": 12.0,
            "confidence": 0.81,
            "sale_probability_percent": 54.0,
            "price_recommendation_eligible": True,
            "ml_predicted": True,
            "prediction_source": "v3_model",
            "fallback_reason": "",
            "retrievalStage": 4,
            "retrievalCandidateCount": 25,
            "retrievalEffectiveSupport": 18,
            "retrievalDroppedAffixes": ["fractured"],
            "retrievalDegradationReason": "fallback_to_similar_route",
            "retrievalAnchorPrice": 42.0,
            "retrievalAnchorLow": 38.0,
            "retrievalAnchorHigh": 56.0,
        },
    )

    assert payload["retrieval_stage"] == 4
    assert payload["retrievalCandidateCount"] == 25
    assert payload["retrieval_anchor_price"] == 42.0
    assert payload["retrieval_degradation_reason"] == "fallback_to_similar_route"


def test_predict_one_static_fallback_is_explicitly_marked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_ml.v3_serve,
        "predict_one_v3",
        lambda _client, league, clipboard_text: {
            "league": league,
            "route": "sparse_retrieval",
            "price_p10": 8.0,
            "price_p50": 10.0,
            "price_p90": 12.0,
            "confidence_percent": 40.0,
            "sale_probability_percent": 30.0,
            "price_recommendation_eligible": False,
            "fallback_reason": "ml_no_prediction_static_fallback",
            "ml_predicted": False,
        },
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = {
        "input_format": "poe-clipboard",
        "payload": "item payload",
        "output_mode": "json",
    }
    body = json.dumps(payload).encode("utf-8")
    response = app.handle(
        method="POST",
        raw_path="/api/v1/ml/leagues/Mirage/predict-one",
        headers={**_auth_headers(), "Content-Length": str(len(body))},
        body_reader=BytesIO(body),
    )
    result = json.loads(response.body.decode("utf-8"))
    assert result["mlPredicted"] is False
    assert result["predictionSource"] == "static_fallback"
    assert result["estimateTrust"] == "low"
    assert isinstance(result["estimateWarning"], str)


def test_predict_one_returns_backend_unavailable_for_v3_backend_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_ml.v3_serve,
        "predict_one_v3",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ClickHouseClientError("bundle lookup failed")
        ),
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = {
        "input_format": "poe-clipboard",
        "payload": "item payload",
        "output_mode": "json",
    }
    body = json.dumps(payload).encode("utf-8")
    with pytest.raises(ApiError) as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/ml/leagues/Mirage/predict-one",
            headers={**_auth_headers(), "Content-Length": str(len(body))},
            body_reader=BytesIO(body),
        )
    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"


def test_ml_rollout_route_removed() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    with pytest.raises(ApiError, match="route not found") as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/ml/leagues/Mirage/rollout",
            headers=_auth_headers(),
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 404
    assert exc.value.code == "route_not_found"


def test_predict_one_warm_path_caches_registry_and_profile_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_predict_dependencies(monkeypatch)
    client = _RecordingPredictClient()

    first = workflows.predict_one(
        _as_clickhouse(client),
        league="Mirage",
        clipboard_text="dummy",
    )
    second = workflows.predict_one(
        _as_clickhouse(client),
        league="Mirage",
        clipboard_text="dummy",
    )

    assert first["price_p50"] == 13.25
    assert second["price_p50"] == 13.25
    assert client.registry_query_count == 1
    assert client.profile_lookup_count == 1


def test_predict_one_cache_invalidates_after_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_predict_dependencies(monkeypatch)
    monkeypatch.setattr(workflows, "_insert_json_rows", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        workflows,
        "warmup_active_models",
        lambda _client, *, league: {"lastAttemptAt": None, "routes": {}},
    )
    client = _RecordingPredictClient()

    workflows.predict_one(
        _as_clickhouse(client),
        league="Mirage",
        clipboard_text="dummy",
    )
    assert client.registry_query_count == 1

    client.model_version = "mirage-v2"
    client.model_dir = "artifacts/ml/mirage_v2"
    client.promoted_at = "2026-03-19 11:00:00"
    workflows._promote_models(
        _as_clickhouse(client),
        league="Mirage",
        model_dir=client.model_dir,
        model_version=client.model_version,
        routes=["sparse_retrieval"],
    )
    workflows.predict_one(
        _as_clickhouse(client),
        league="Mirage",
        clipboard_text="dummy",
    )

    assert client.registry_query_count == 2
    assert workflows._ACTIVE_MODEL_VERSION_HINT.get("Mirage") == "mirage-v2"


def test_predict_one_cache_invalidates_after_snapshot_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_predict_dependencies(monkeypatch)
    client = _RecordingPredictClient()

    workflows.predict_one(
        _as_clickhouse(client),
        league="Mirage",
        clipboard_text="dummy",
    )
    workflows.predict_one(
        _as_clickhouse(client),
        league="Mirage",
        clipboard_text="dummy",
    )
    assert client.profile_lookup_count == 1

    client.profile_snapshot_window_id = "window-2"
    client.profile_as_of_ts = "2026-03-19 11:15:00"
    client.profile_price = 21.5
    workflows.build_serving_profile(
        _as_clickhouse(client),
        league="Mirage",
        snapshot_window_id=client.profile_snapshot_window_id,
    )
    refreshed = workflows.predict_one(
        _as_clickhouse(client),
        league="Mirage",
        clipboard_text="dummy",
    )

    assert refreshed["price_p50"] == 21.5
    assert client.profile_lookup_count == 2


def test_predict_one_rejects_unsupported_input_format() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = {"input_format": "unknown", "payload": "x", "output_mode": "json"}
    body = json.dumps(payload).encode("utf-8")
    with pytest.raises(ApiError, match="invalid input") as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/ml/leagues/Mirage/predict-one",
            headers={**_auth_headers(), "Content-Length": str(len(body))},
            body_reader=BytesIO(body),
        )
    assert exc.value.code == "invalid_input"
    assert exc.value.status == 400


def test_predict_one_rejects_malformed_json() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    body = b"{invalid"
    with pytest.raises(ApiError, match="valid JSON") as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/ml/leagues/Mirage/predict-one",
            headers={**_auth_headers(), "Content-Length": str(len(body))},
            body_reader=BytesIO(body),
        )
    assert exc.value.code == "invalid_json"
    assert exc.value.status == 400


def test_predict_one_rejects_oversized_request() -> None:
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    body = b"x" * 1024
    with pytest.raises(ApiError, match="exceeds limit") as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/ml/leagues/Mirage/predict-one",
            headers={**_auth_headers(), "Content-Length": str(len(body))},
            body_reader=BytesIO(body),
        )
    assert exc.value.code == "request_too_large"
    assert exc.value.status == 413


def test_predict_one_backend_failure_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(_client, league, clipboard_text):
        raise ClickHouseClientError("sensitive backend detail")

    monkeypatch.setattr(api_ml.v3_serve, "predict_one_v3", _raise)
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    payload = {
        "input_format": "poe-clipboard",
        "payload": "item payload",
        "output_mode": "json",
    }
    body = json.dumps(payload).encode("utf-8")
    with pytest.raises(ApiError, match="backend unavailable") as exc:
        app.handle(
            method="POST",
            raw_path="/api/v1/ml/leagues/Mirage/predict-one",
            headers={**_auth_headers(), "Content-Length": str(len(body))},
            body_reader=BytesIO(body),
        )
    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"


def test_fetch_predict_one_invalid_clipboard_bubbles_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_ml, "validate_predict_one_request", lambda _payload: "not a clipboard"
    )
    with pytest.raises(ValueError, match="invalid clipboard text"):
        api_ml.fetch_predict_one(
            ClickHouseClient(endpoint="http://ch"),
            league="Mirage",
            request_payload={
                "input_format": "poe-clipboard",
                "payload": "item payload",
                "output_mode": "json",
            },
        )


def test_ml_automation_routes_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_automation_status",
        lambda _client, *, league: {
            "league": league,
            "status": "completed",
            "latestRun": None,
            "activeModelVersion": None,
            "promotionVerdict": None,
            "routeHotspots": [],
        },
    )
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_automation_history",
        lambda _client, *, league: {"league": league, "history": []},
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    status_response = app.handle(
        method="GET",
        raw_path="/api/v1/ml/leagues/Mirage/automation/status",
        headers=_auth_headers(),
        body_reader=BytesIO(b""),
    )
    history_response = app.handle(
        method="GET",
        raw_path="/api/v1/ml/leagues/Mirage/automation/history",
        headers=_auth_headers(),
        body_reader=BytesIO(b""),
    )
    assert status_response.status == 200
    assert history_response.status == 200


def test_fetch_automation_status_keeps_hold_state_without_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_ml,
        "fetch_status",
        lambda _client, *, league: {
            "league": league,
            "status": "failed_gates",
            "promotion_verdict": "hold",
            "active_model_version": "none",
            "route_hotspots": [],
        },
    )
    sample_rows = [
        {
            "run_id": "run-1",
            "status": "failed_gates",
            "stop_reason": "hold_no_material_improvement",
            "active_model_version": "none",
            "updated_at": "2026-03-14 10:00:00",
        }
    ]
    monkeypatch.setattr(api_ml, "_query_rows", lambda _client, _query: sample_rows)
    monkeypatch.setattr(workflows, "_query_rows", lambda _client, _query: sample_rows)

    monkeypatch.setattr(workflows, "_ensure_train_runs_table", lambda _client: None)

    payload = api_ml.fetch_automation_status(
        ClickHouseClient(endpoint="http://ch"),
        league="Mirage",
    )

    assert payload["status"] == "failed_gates"
    assert payload["promotionVerdict"] == "hold"
    assert payload["activeModelVersion"] is None
    assert payload["latestRun"]["status"] == "failed_gates"


def test_fetch_automation_history_normalizes_no_active_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_rows = [
        {
            "run_id": "run-2",
            "status": "stopped_budget",
            "stop_reason": "iteration_budget_exhausted",
            "active_model_version": "none",
            "tuning_config_id": "cfg-1",
            "eval_run_id": "eval-1",
            "updated_at": "2026-03-14 11:00:00",
        }
    ]
    monkeypatch.setattr(api_ml, "_query_rows", lambda _client, _query: sample_rows)
    monkeypatch.setattr(workflows, "_query_rows", lambda _client, _query: sample_rows)

    monkeypatch.setattr(workflows, "_ensure_train_runs_table", lambda _client: None)

    payload = api_ml.fetch_automation_history(
        ClickHouseClient(endpoint="http://ch"),
        league="Mirage",
    )

    assert payload["history"][0]["status"] == "stopped_budget"
    assert payload["history"][0]["activeModelVersion"] is None


def test_fetch_automation_history_v3_does_not_fabricate_eval_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflows, "train_run_history", lambda *_args, **_kwargs: [])

    def _fake_query_rows(
        _client: ClickHouseClient, query: str
    ) -> list[dict[str, object]]:
        if "FROM poe_trade.ml_v3_model_registry" in query:
            return [
                {
                    "route": "sparse_retrieval",
                    "model_version": "v3-mirage-sparse_retrieval",
                    "promoted_at": "2026-03-22 11:48:25.185",
                }
            ]
        if (
            "FROM poe_trade.ml_v3_listing_episodes" in query
            and "count() AS total_rows" in query
        ):
            return [
                {
                    "total_rows": 1000,
                    "base_type_count": 120,
                    "latest_as_of": "2026-03-20 11:57:36.615",
                }
            ]
        if (
            "FROM poe_trade.ml_v3_listing_episodes" in query
            and "GROUP BY route" in query
        ):
            return [{"route": "sparse_retrieval", "rows": 1000}]
        if (
            "FROM poe_trade.ml_v3_eval_runs" in query
            or "FROM poe_trade.ml_v3_route_eval" in query
        ):
            return []
        return []

    monkeypatch.setattr(api_ml, "_query_rows", _fake_query_rows)

    payload = api_ml.fetch_automation_history(
        ClickHouseClient(endpoint="http://ch"),
        league="Mirage",
    )

    assert payload["history"] == []
    assert "charts" in payload
    assert payload["charts"]["mdapeHistory"] == []
    assert "mode" not in payload
    assert payload["summary"]["latestAvgMdape"] is None
    assert payload["summary"]["latestAvgIntervalCoverage"] is None
    assert payload["observability"]["evaluationAvailable"] is False
    assert (
        payload["observability"]["latestTrainingAsOf"] == "2026-03-20T11:57:36.615000Z"
    )


def test_fetch_automation_status_does_not_include_mode_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_ml,
        "fetch_status",
        lambda _client, *, league: {
            "league": league,
            "status": "completed",
            "run": {"run_id": "run-1"},
            "promotion_verdict": "hold",
            "active_model_version": None,
            "route_hotspots": [],
        },
    )
    monkeypatch.setattr(api_ml, "_query_rows", lambda _client, _query: [])
    monkeypatch.setattr(workflows, "_query_rows", lambda _client, _query: [])
    monkeypatch.setattr(workflows, "_ensure_train_runs_table", lambda _client: None)

    payload = api_ml.fetch_automation_status(
        ClickHouseClient(endpoint="http://ch"),
        league="Mirage",
    )

    assert payload["status"] == "completed"
    assert "mode" not in payload


def test_ml_automation_status_backend_failure_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_automation_status",
        lambda _client, *, league: (_ for _ in ()).throw(
            api_ml.BackendUnavailable("backend offline")
        ),
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    with pytest.raises(ApiError, match="backend unavailable") as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/ml/leagues/Mirage/automation/status",
            headers=_auth_headers(),
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"


def test_ml_automation_history_backend_failure_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "poe_trade.api.app.fetch_automation_history",
        lambda _client, *, league: (_ for _ in ()).throw(
            api_ml.BackendUnavailable("backend offline")
        ),
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))

    with pytest.raises(ApiError, match="backend unavailable") as exc:
        app.handle(
            method="GET",
            raw_path="/api/v1/ml/leagues/Mirage/automation/history",
            headers=_auth_headers(),
            body_reader=BytesIO(b""),
        )

    assert exc.value.status == 503
    assert exc.value.code == "backend_unavailable"


def test_explicit_ops_analytics_routes_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    from poe_trade.api import app as api_app

    monkeypatch.setattr(
        api_app,
        "analytics_search_history",
        lambda _client, query_params, default_league: {
            "query": query_params.get("query", [""])[0],
            "league": default_league,
            "rows": [],
        },
    )
    app = ApiApp(_settings(), clickhouse_client=ClickHouseClient(endpoint="http://ch"))
    response = app.handle(
        method="GET",
        raw_path="/api/v1/ops/analytics/search-history?query=divine&limit=25",
        headers=_auth_headers(),
        body_reader=BytesIO(b""),
    )
    body = json.loads(response.body.decode("utf-8"))
    assert response.status == 200
    assert body["query"] == "divine"
    assert body["league"] == "Mirage"


def test_fetch_predict_one_uses_v3_serving_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_ml, "validate_predict_one_request", lambda _payload: "dummy"
    )
    monkeypatch.setattr(
        api_ml.v3_serve,
        "predict_one_v3",
        lambda *_args, **_kwargs: {
            "route": "sparse_retrieval",
            "price_p10": 10.0,
            "price_p50": 12.0,
            "price_p90": 15.0,
            "fast_sale_24h_price": 11.0,
            "sale_probability_percent": 62.0,
            "sale_probability_24h": 0.62,
            "confidence_percent": 75.0,
            "confidence": 0.75,
            "prediction_source": "v3_model",
            "fallback_reason": "",
            "ml_predicted": True,
            "price_recommendation_eligible": True,
            "predictedValue": 12.0,
        },
    )

    payload = api_ml.fetch_predict_one(
        ClickHouseClient(endpoint="http://ch"),
        league="Mirage",
        request_payload={
            "input_format": "poe-clipboard",
            "payload": "dummy",
            "output_mode": "json",
        },
    )

    assert payload["predictionSource"] == "v3_model"
    assert payload["price_p50"] == 12.0
    assert payload["saleProbabilityPercent"] == 62.0


def test_fetch_predict_one_uses_v3_serving_without_feature_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POE_ML_V3_SERVING_ENABLED", raising=False)
    monkeypatch.setattr(
        api_ml, "validate_predict_one_request", lambda _payload: "dummy"
    )
    monkeypatch.setattr(
        api_ml.v3_serve,
        "predict_one_v3",
        lambda *_args, **_kwargs: {
            "route": "sparse_retrieval",
            "price_p10": 10.0,
            "price_p50": 12.0,
            "price_p90": 15.0,
            "fast_sale_24h_price": 11.0,
            "sale_probability_percent": 62.0,
            "sale_probability_24h": 0.62,
            "confidence_percent": 75.0,
            "confidence": 0.75,
            "prediction_source": "v3_model",
            "fallback_reason": "",
            "ml_predicted": True,
            "price_recommendation_eligible": True,
            "predictedValue": 12.0,
        },
    )

    payload = api_ml.fetch_predict_one(
        ClickHouseClient(endpoint="http://ch"),
        league="Mirage",
        request_payload={
            "input_format": "poe-clipboard",
            "payload": "dummy",
            "output_mode": "json",
        },
    )

    assert payload["predictionSource"] == "v3_model"
    assert payload["price_p50"] == 12.0
    assert payload["saleProbabilityPercent"] == 62.0
