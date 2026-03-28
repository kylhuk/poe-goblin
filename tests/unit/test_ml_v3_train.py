from __future__ import annotations

import json
from typing import Any, cast

import joblib

from poe_trade.db import ClickHouseClient
from poe_trade.ml.v3 import train


class _Client:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def execute(self, _query: str, settings=None) -> str:  # noqa: ANN001
        return self.payload


def test_train_route_v3_returns_no_data_when_empty() -> None:
    client = _Client(payload="")

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir="artifacts/ml",
    )

    assert result["status"] == "no_data"
    assert result["row_count"] == 0


def test_train_route_v3_writes_bundle_for_small_dataset(tmp_path) -> None:
    rows = [
        {
            "feature_vector_json": '{"ilvl":86,"stack_size":1,"corrupted":0}',
            "mod_features_json": '{"MaximumLife_tier":8,"MaximumLife_roll":0.9}',
            "target_price_chaos": 100.0,
            "target_fast_sale_24h_price": 92.0,
            "target_sale_probability_24h": 0.8,
        },
        {
            "feature_vector_json": '{"ilvl":84,"stack_size":1,"corrupted":0}',
            "mod_features_json": '{"MaximumLife_tier":7,"MaximumLife_roll":0.7}',
            "target_price_chaos": 80.0,
            "target_fast_sale_24h_price": 72.0,
            "target_sale_probability_24h": 0.6,
        },
        {
            "feature_vector_json": '{"ilvl":70,"stack_size":1,"corrupted":1}',
            "mod_features_json": '{"MaximumLife_tier":5,"MaximumLife_roll":0.4}',
            "target_price_chaos": 40.0,
            "target_fast_sale_24h_price": 35.0,
            "target_sale_probability_24h": 0.2,
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )

    assert result["status"] == "trained"
    assert result["row_count"] == 3
    assert result["model_bundle_path"].endswith("bundle.joblib")
    bundle = joblib.load(result["model_bundle_path"])
    assert bundle["models"]["fast_sale_24h"] is not None
    assert bundle["models"]["p10"] is not None
    assert bundle["models"]["p90"] is not None


def test_train_route_v3_writes_hybrid_bundle_contents(tmp_path) -> None:
    rows = [
        {
            "feature_vector_json": '{"ilvl":86,"stack_size":1,"corrupted":0}',
            "mod_features_json": '{"explicit.max_life":1,"explicit.fire_res":1}',
            "target_price_chaos": 100.0,
            "target_fast_sale_24h_price": 88.0,
            "target_sale_probability_24h": 0.8,
        },
        {
            "feature_vector_json": '{"ilvl":84,"stack_size":1,"corrupted":0}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 72.0,
            "target_fast_sale_24h_price": 63.0,
            "target_sale_probability_24h": 0.5,
        },
        {
            "feature_vector_json": '{"ilvl":70,"stack_size":1,"corrupted":1}',
            "mod_features_json": '{"explicit.light_radius":1}',
            "target_price_chaos": 30.0,
            "target_fast_sale_24h_price": 24.0,
            "target_sale_probability_24h": 0.2,
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )

    bundle = joblib.load(result["model_bundle_path"])
    assert "search_config" in bundle
    assert "fair_value_residual_model" in bundle
    assert "route_family_priors" in bundle
    assert bundle["metadata"]["prediction_space"] == "log1p_price"
    assert len(bundle["metadata"]["feature_schema"]["fingerprint"]) == 64
    assert callable(getattr(bundle["models"]["sale_probability"], "predict", None))


def test_train_route_v3_keeps_chaos_bundle_when_divine_targets_are_mixed(
    tmp_path,
) -> None:
    rows = [
        {
            "feature_vector_json": '{"ilvl":86,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 100.0,
            "target_fast_sale_24h_price": 90.0,
            "target_price_divine": 1.0,
            "target_fast_sale_24h_price_divine": 0.9,
            "target_sale_probability_24h": 0.8,
        },
        {
            "feature_vector_json": '{"ilvl":84,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 75.0,
            "target_fast_sale_24h_price": 66.0,
            "target_sale_probability_24h": 0.4,
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )
    bundle = joblib.load(result["model_bundle_path"])

    assert bundle["metadata"]["price_unit"] == "chaos"


def test_train_route_v3_marks_divine_bundle_when_all_rows_have_divine_targets(
    tmp_path,
) -> None:
    rows = [
        {
            "feature_vector_json": '{"ilvl":86,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 100.0,
            "target_fast_sale_24h_price": 90.0,
            "target_price_divine": 1.0,
            "target_fast_sale_24h_price_divine": 0.9,
            "target_sale_probability_24h": 0.8,
        },
        {
            "feature_vector_json": '{"ilvl":84,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 75.0,
            "target_fast_sale_24h_price": 66.0,
            "target_price_divine": 0.75,
            "target_fast_sale_24h_price_divine": 0.66,
            "target_sale_probability_24h": 0.4,
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )
    bundle = joblib.load(result["model_bundle_path"])

    assert bundle["metadata"]["price_unit"] == "divine"


def test_hybrid_training_persists_fast_sale_target_metadata(tmp_path) -> None:
    rows = [
        {
            "feature_vector_json": '{"ilvl":86}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 100.0,
            "target_fast_sale_24h_price": 90.0,
            "target_sale_probability_24h": 0.8,
        },
        {
            "feature_vector_json": '{"ilvl":84}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 75.0,
            "target_fast_sale_24h_price": 65.0,
            "target_sale_probability_24h": 0.4,
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )
    bundle = joblib.load(result["model_bundle_path"])

    assert bundle["metadata"]["has_fast_sale_target"] is True


def test_train_route_v3_bundle_metadata_includes_route_and_cohort_identity(
    tmp_path,
) -> None:
    cohort_key = (
        "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
    )
    rows = [
        {
            "feature_vector_json": '{"ilvl":86}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 120.0,
            "target_fast_sale_24h_price": 105.0,
            "target_sale_probability_24h": 0.9,
            "strategy_family": "sparse_retrieval",
            "cohort_key": cohort_key,
        },
        {
            "feature_vector_json": '{"ilvl":75}',
            "mod_features_json": '{"explicit.max_life":0.5}',
            "target_price_chaos": 55.0,
            "target_fast_sale_24h_price": 48.0,
            "target_sale_probability_24h": 0.2,
            "strategy_family": "sparse_retrieval",
            "cohort_key": cohort_key,
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )
    bundle = joblib.load(result["model_bundle_path"])

    metadata = bundle["metadata"]
    assert metadata["strategy_family"] == "__route_wide__"
    assert metadata["cohort_key"] == "__route_wide__"
    assert metadata["model_scope"] == "route_wide"
    assert metadata["row_count"] == 2
    assert metadata["route_compatibility_alias"] == "sparse_retrieval"

    cohort_bundle = bundle["cohort_bundles"][f"sparse_retrieval::{cohort_key}"]
    cohort_metadata = cohort_bundle["metadata"]
    assert cohort_metadata["strategy_family"] == "sparse_retrieval"
    assert cohort_metadata["cohort_key"] == cohort_key
    assert cohort_metadata["model_scope"] == "cohort"


def test_train_route_v3_writes_cohort_keyed_bundle_map_with_route_compatibility(
    tmp_path,
) -> None:
    cohort_key_one = (
        "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
    )
    cohort_key_two = (
        "sparse_retrieval|ring|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
    )
    rows = [
        {
            "feature_vector_json": '{"ilvl":86,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 120.0,
            "target_fast_sale_24h_price": 102.0,
            "target_sale_probability_24h": 0.8,
            "strategy_family": "sparse_retrieval",
            "cohort_key": cohort_key_one,
        },
        {
            "feature_vector_json": '{"ilvl":75,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":0.5}',
            "target_price_chaos": 58.0,
            "target_fast_sale_24h_price": 47.0,
            "target_sale_probability_24h": 0.2,
            "strategy_family": "sparse_retrieval",
            "cohort_key": cohort_key_one,
        },
        {
            "feature_vector_json": '{"ilvl":88,"stack_size":1}',
            "mod_features_json": '{"explicit.chaos_res":1}',
            "target_price_chaos": 98.0,
            "target_fast_sale_24h_price": 84.0,
            "target_sale_probability_24h": 0.7,
            "strategy_family": "sparse_retrieval",
            "cohort_key": cohort_key_two,
        },
        {
            "feature_vector_json": '{"ilvl":72,"stack_size":1}',
            "mod_features_json": '{"explicit.chaos_res":0.4}',
            "target_price_chaos": 45.0,
            "target_fast_sale_24h_price": 36.0,
            "target_sale_probability_24h": 0.1,
            "strategy_family": "sparse_retrieval",
            "cohort_key": cohort_key_two,
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )
    bundle = joblib.load(result["model_bundle_path"])

    cohort_bundles = bundle["cohort_bundles"]
    assert set(cohort_bundles) == {
        f"sparse_retrieval::{cohort_key_one}",
        f"sparse_retrieval::{cohort_key_two}",
    }
    assert bundle["metadata"]["row_count"] == 4
    assert bundle["metadata"]["model_scope"] == "route_wide"
    assert bundle["metadata"]["route_compatibility_alias"] == "sparse_retrieval"
    assert bundle["metadata"]["cohort_count"] == 2
    assert bundle["metadata"]["cohort_key"] == "__route_wide__"
    assert bundle["metadata"]["strategy_family"] == "__route_wide__"
    for cohort_bundle in cohort_bundles.values():
        assert (
            cohort_bundle["metadata"]["route_compatibility_alias"] == "sparse_retrieval"
        )
        assert cohort_bundle["metadata"]["strategy_family"] == "sparse_retrieval"
        assert cohort_bundle["metadata"]["row_count"] == 2
        assert cohort_bundle["metadata"]["model_scope"] == "cohort"

    assert bundle["vectorizer"] is not None
    assert bundle["models"]["p50"] is not None


def test_residual_caps_follow_spec_thresholds() -> None:
    capped = train.apply_residual_cap(
        anchor_price=100.0,
        confidence=0.20,
        fair_residual=20.0,
        fast_residual=20.0,
    )

    assert capped["fair_value"] == 108.0
    assert capped["fast_sale"] == 106.0


def test_train_route_v3_single_cohort_avoids_duplicate_training_call(
    monkeypatch, tmp_path
) -> None:
    rows = [
        {
            "feature_vector_json": '{"ilvl":86,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 120.0,
            "target_fast_sale_24h_price": 102.0,
            "target_sale_probability_24h": 0.8,
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        },
        {
            "feature_vector_json": '{"ilvl":75,"stack_size":1}',
            "mod_features_json": '{"explicit.max_life":0.5}',
            "target_price_chaos": 58.0,
            "target_fast_sale_24h_price": 47.0,
            "target_sale_probability_24h": 0.2,
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)
    calls: list[int] = []

    original = train._train_bundle_for_rows

    def _spy_train_bundle_for_rows(**kwargs):
        calls.append(len(kwargs["rows"]))
        return original(**kwargs)

    monkeypatch.setattr(train, "_train_bundle_for_rows", _spy_train_bundle_for_rows)

    train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )

    assert calls == [2]


def test_load_training_rows_keeps_eval_tail_out_of_train_slice() -> None:
    class _CaptureClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            self.queries.append(query)
            if "count() AS rows" in query:
                return json.dumps({"rows": 850}) + "\n"
            return ""

    client = _CaptureClient()

    _ = train._load_training_rows(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        max_rows=60_000,
    )

    training_query = next(
        query for query in client.queries if "ORDER BY as_of_ts" in query
    )
    assert "ORDER BY as_of_ts ASC, identity_key ASC" in training_query
    assert "LIMIT 680" in training_query
    assert "listing_episode_id" in training_query
    assert "snapshot_count" in training_query

    client_eval = _CaptureClient()
    _ = train._load_eval_rows(
        cast(Any, client_eval),
        league="Mirage",
        route="sparse_retrieval",
        max_rows=2_000,
    )
    eval_query = next(
        query for query in client_eval.queries if "ORDER BY as_of_ts" in query
    )
    assert "ORDER BY as_of_ts ASC, identity_key ASC" in eval_query
    assert "LIMIT 170 OFFSET 680" in eval_query
    assert "listing_episode_id" in eval_query
    assert "snapshot_count" in eval_query


def test_train_all_routes_v3_runs_ring_parser_audit_first(monkeypatch) -> None:
    calls: list[str] = []

    class _AuditClient(ClickHouseClient):
        payload: str = ""

        def __init__(self) -> None:
            super().__init__(endpoint="http://localhost")

        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            return self.payload

    client = object.__new__(_AuditClient)

    def _audit(client, *, league: str) -> None:  # noqa: ANN001
        calls.append(f"audit:{league}")

    def _query_rows(_client, _query: str):  # noqa: ANN001
        calls.append("query_rows")
        return [{"route": "sparse_retrieval", "rows": 1}]

    def _train_route_v3(
        client, *, league: str, route: str, model_dir: str, max_rows: int
    ):  # noqa: ANN001
        calls.append(f"train:{route}")
        return {
            "league": league,
            "route": route,
            "row_count": 1,
            "model_bundle_path": f"{model_dir}/bundle.joblib",
            "status": "trained",
        }

    def _record_eval_predictions_for_run(
        client, *, league: str, model_dir: str, routes, run_id: str
    ):  # noqa: ANN001
        calls.append("record_eval")
        return 0

    monkeypatch.setattr(train.workflows, "audit_ring_parser_invariants", _audit)
    monkeypatch.setattr(train, "_query_rows", _query_rows)
    monkeypatch.setattr(train, "train_route_v3", _train_route_v3)
    monkeypatch.setattr(
        train, "record_eval_predictions_for_run", _record_eval_predictions_for_run
    )

    result = train.train_all_routes_v3(
        cast(Any, client),
        league="Mirage",
        model_dir="/tmp/model-dir",
    )

    assert calls[0] == "audit:Mirage"
    assert calls[1] == "query_rows"
    assert calls[2] == "train:sparse_retrieval"
    assert calls[3] == "record_eval"
    assert result["trained_count"] == 1


def test_train_route_v3_feature_vector_includes_structured_contract_fields(
    tmp_path,
) -> None:
    rows = [
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": 86,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "feature_vector_json": '{"ilvl":86,"stack_size":1,"corrupted":0}',
            "mod_features_json": '{"explicit.max_life":1}',
            "target_price_chaos": 120.0,
            "target_fast_sale_24h_price": 105.0,
            "target_sale_probability_24h": 0.9,
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "parent_cohort_key": "sparse_retrieval|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        },
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": 75,
            "stack_size": 1,
            "corrupted": 1,
            "fractured": 0,
            "synthesised": 0,
            "feature_vector_json": '{"ilvl":75,"stack_size":1,"corrupted":1}',
            "mod_features_json": '{"explicit.max_life":0.5}',
            "target_price_chaos": 55.0,
            "target_fast_sale_24h_price": 48.0,
            "target_sale_probability_24h": 0.2,
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=1|fractured=0|synthesised=0",
            "parent_cohort_key": "sparse_retrieval|v1|rarity=rare|corrupted=1|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=1|fractured=0|synthesised=0",
        },
    ]
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    client = _Client(payload=payload)

    result = train.train_route_v3(
        cast(Any, client),
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )

    bundle = joblib.load(result["model_bundle_path"])
    feature_names = set(bundle["vectorizer"].feature_names_)
    assert "category=helmet" in feature_names
    assert "base_type=Hubris Circlet" in feature_names
    assert "rarity=Rare" in feature_names
    assert "support_count_recent" in feature_names
    assert "strategy_family=sparse_retrieval" in feature_names
    assert (
        "cohort_key=sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
        in feature_names
    )
    assert "route_family=sparse_retrieval" in feature_names
    assert "item_state_key=rare|corrupted=0|fractured=0|synthesised=0" in feature_names
    assert (
        "base_identity_key=hubris circlet|rare|corrupted=0|fractured=0|synthesised=0"
        in feature_names
    )


def test_record_eval_predictions_for_run_writes_engine_version(
    monkeypatch,
    tmp_path,
) -> None:
    vectorizer = train.DictVectorizer(sparse=True)
    vectorizer.fit(
        [
            {
                "category": "helmet",
                "base_type": "Hubris Circlet",
                "rarity": "Rare",
                "ilvl": 86,
                "stack_size": 1,
                "corrupted": 0,
                "fractured": 0,
                "synthesised": 0,
                "mod_token_count": 0,
                "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
                "route_family": "sparse_retrieval",
                "base_identity_key": "hubris circlet|rare|corrupted=0|fractured=0|synthesised=0",
                "explicit.max_life": 1.0,
            }
        ]
    )
    models = {
        "p10": train.GradientBoostingRegressor(random_state=42),
        "p50": train.GradientBoostingRegressor(random_state=42),
        "p90": train.GradientBoostingRegressor(random_state=42),
    }
    feature_row = {
        "category": "helmet",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "ilvl": 86,
        "stack_size": 1,
        "corrupted": 0,
        "fractured": 0,
        "synthesised": 0,
        "mod_token_count": 0,
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "route_family": "sparse_retrieval",
        "base_identity_key": "hubris circlet|rare|corrupted=0|fractured=0|synthesised=0",
        "explicit.max_life": 1.0,
    }
    X = vectorizer.transform([feature_row, feature_row])
    for model in models.values():
        model.fit(X, [1.0, 1.0])
    bundle = {
        "vectorizer": vectorizer,
        "models": models,
        "metadata": {"model_version": "v3-mirage"},
    }

    inserted: list[str] = []

    class _EvalClient:
        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            inserted.append(query)
            return ""

    monkeypatch.setattr(train, "_load_bundle_for_route", lambda **_kwargs: bundle)
    monkeypatch.setattr(
        train,
        "_load_eval_rows",
        lambda *_args, **_kwargs: [
            {
                "as_of_ts": "2026-03-20T00:00:00",
                "item_id": "item-1",
                "identity_key": "item-1",
                "category": "helmet",
                "base_type": "Hubris Circlet",
                "rarity": "Rare",
                "ilvl": 86,
                "stack_size": 1,
                "corrupted": 0,
                "fractured": 0,
                "synthesised": 0,
                "support_count_recent": 4,
                "feature_vector_json": '{"ilvl":86,"stack_size":1,"corrupted":0}',
                "mod_features_json": '{"explicit.max_life":1}',
            }
        ],
    )

    count = train.record_eval_predictions_for_run(
        cast(Any, object.__new__(_EvalClient)),
        league="Mirage",
        model_dir=str(tmp_path),
        routes=["sparse_retrieval"],
        run_id="run-123",
    )

    assert count == 1
    body = "\n".join(inserted)
    assert '"engine_version":"v3-mirage"' in body


def test_record_eval_predictions_for_run_uses_cohort_bundle_when_available(
    monkeypatch,
    tmp_path,
) -> None:
    class _Classifier:
        def fit(self, _X, _y):  # noqa: ANN001
            return self

        def predict_proba(self, _X):  # noqa: ANN001
            return [[0.2, 0.8]]

    vectorizer = train.DictVectorizer(sparse=True)
    feature_row = {
        "category": "helmet",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "ilvl": 86,
        "stack_size": 1,
        "corrupted": 0,
        "fractured": 0,
        "synthesised": 0,
        "mod_token_count": 0,
        "support_count_recent": 4,
        "strategy_family": "sparse_retrieval",
        "cohort_key": (
            "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
        ),
        "parent_cohort_key": "sparse_retrieval|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "route_family": "sparse_retrieval",
        "base_identity_key": "hubris circlet|rare|corrupted=0|fractured=0|synthesised=0",
        "explicit.max_life": 1.0,
    }
    vectorizer.fit([feature_row])

    def _fit_bundle(value: float) -> dict[str, object]:
        models = {
            "p10": train.GradientBoostingRegressor(random_state=42),
            "p50": train.GradientBoostingRegressor(random_state=42),
            "p90": train.GradientBoostingRegressor(random_state=42),
            "fast_sale_24h": train.GradientBoostingRegressor(random_state=42),
            "sale_probability": _Classifier(),
        }
        X = vectorizer.transform([feature_row, feature_row])
        for name, model in models.items():
            if name == "sale_probability":
                continue
            model.fit(X, [value, value])
        return {
            "vectorizer": vectorizer,
            "models": models,
            "metadata": {
                "model_version": "v3-mirage",
                "prediction_space": "price",
                "price_unit": "chaos",
            },
        }

    route_bundle = _fit_bundle(1.0)
    cohort_bundle = _fit_bundle(5.0)
    route_metadata = cast(dict[str, object], route_bundle["metadata"])
    cohort_metadata = cast(dict[str, object], cohort_bundle["metadata"])
    route_metadata["price_unit"] = "chaos"
    cohort_metadata["price_unit"] = "divine"
    route_bundle["cohort_bundles"] = {
        "sparse_retrieval::sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0": cohort_bundle,
    }

    inserted: list[str] = []

    class _EvalClient:
        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            inserted.append(query)
            return ""

    monkeypatch.setattr(train, "_load_bundle_for_route", lambda **_kwargs: route_bundle)
    monkeypatch.setattr(
        train,
        "_load_eval_rows",
        lambda *_args, **_kwargs: [
            {
                "as_of_ts": "2026-03-20T00:00:00",
                "item_id": "item-1",
                "identity_key": "item-1",
                "route": "sparse_retrieval",
                "category": "helmet",
                "base_type": "Hubris Circlet",
                "item_type_line": "Hubris Circlet",
                "rarity": "Rare",
                "ilvl": 86,
                "stack_size": 1,
                "corrupted": 0,
                "fractured": 0,
                "synthesised": 0,
                "support_count_recent": 4,
                "fx_chaos_per_divine": 100.0,
                "feature_vector_json": '{"ilvl":86,"stack_size":1,"corrupted":0}',
                "mod_features_json": '{"explicit.max_life":1}',
            }
        ],
    )

    count = train.record_eval_predictions_for_run(
        cast(Any, object.__new__(_EvalClient)),
        league="Mirage",
        model_dir=str(tmp_path),
        routes=["sparse_retrieval"],
        run_id="run-123",
    )

    assert count == 1
    body = "\n".join(inserted)
    assert '"fair_value_p50":500.0' in body
