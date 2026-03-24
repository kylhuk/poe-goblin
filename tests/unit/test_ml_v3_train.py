from __future__ import annotations

import json

import joblib

from poe_trade.ml.v3 import train


class _Client:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def execute(self, _query: str, settings=None) -> str:  # noqa: ANN001
        return self.payload


def test_train_route_v3_returns_no_data_when_empty() -> None:
    client = _Client(payload="")

    result = train.train_route_v3(
        client,
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
        client,
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
        client,
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )

    bundle = joblib.load(result["model_bundle_path"])
    assert "search_config" in bundle
    assert "fair_value_residual_model" in bundle
    assert "route_family_priors" in bundle


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
        client,
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
        client,
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
        client,
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
        client,
        league="Mirage",
        route="sparse_retrieval",
        model_dir=str(tmp_path),
    )

    assert calls == [2]
