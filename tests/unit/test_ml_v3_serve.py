from __future__ import annotations

import json

from poe_trade.ml.v3 import serve


class _Client:
    def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
        if "quantileTDigest(0.5)(target_price_chaos)" in query:
            return json.dumps({"p50": 120.0, "rows": 32}) + "\n"
        return ""


class _DummyVectorizer:
    def transform(self, _rows):  # noqa: ANN001
        return [[1.0]]


class _DummyRegressor:
    def __init__(self, value: float) -> None:
        self.value = value

    def predict(self, _X):  # noqa: ANN001
        return [self.value]


class _DummyClassifier:
    def predict_proba(self, _X):  # noqa: ANN001
        return [[0.2, 0.8]]


def test_predict_one_v3_fallback_returns_dual_prices(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": 86,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 2,
            "mod_features_json": "{}",
        },
    )

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/does/not/exist",
    )

    assert payload["route"] == "sparse_retrieval"
    assert payload["fair_value_p50"] == 120.0
    assert payload["fast_sale_24h_price"] == 108.0
    assert payload["prediction_source"] == "v3_median_fallback"
    assert payload["price_recommendation_eligible"] is True


def test_predict_one_v3_uses_direct_fast_sale_model_when_bundle_exists(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": 86,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 2,
            "mod_features_json": "{}",
        },
    )
    monkeypatch.setattr(
        serve,
        "_load_bundle_if_present",
        lambda **_kwargs: {
            "vectorizer": _DummyVectorizer(),
            "models": {
                "p10": _DummyRegressor(95.0),
                "p50": _DummyRegressor(120.0),
                "p90": _DummyRegressor(140.0),
                "fast_sale_24h": _DummyRegressor(109.0),
                "sale_probability": _DummyClassifier(),
            },
            "fallback_fast_sale_multiplier": 0.9,
            "metadata": {"row_count": 1200},
        },
    )

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/unused",
    )

    assert payload["prediction_source"] == "v3_model"
    assert payload["fair_value_p50"] == 120.0
    assert payload["fast_sale_24h_price"] == 109.0
    assert payload["sale_probability_24h"] == 0.8
    assert payload["confidence"] > 0.35


class _RetrievalClient:
    def __init__(self, candidates: list[dict[str, object]]) -> None:
        self.candidates = candidates

    def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
        if "FROM poe_trade.ml_v3_retrieval_candidates" in query:
            return "\n".join(json.dumps(row) for row in self.candidates)
        if "quantileTDigest(0.5)(target_price_chaos)" in query:
            return json.dumps({"p50": 120.0, "rows": 32}) + "\n"
        return ""


def test_predict_one_v3_uses_retrieval_anchor_without_bundle(
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": 86,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 2,
            "mod_features_json": "{}",
        },
    )
    client = _RetrievalClient(
        [
            {"candidate_price_chaos": 180.0, "distance_score": 0.15},
            {"candidate_price_chaos": 120.0, "distance_score": 0.35},
        ]
    )

    payload = serve.predict_one_v3(
        client,
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/does/not/exist",
    )

    assert payload["prediction_source"] == "v3_retrieval_fallback"
    assert payload["route"] == "sparse_retrieval"
    assert payload["fair_value_p50"] == 180.0
    assert payload["retrieval_stage"] == 4
    assert payload["retrieval_candidate_count"] == 2
    assert payload["retrieval_effective_support"] == 2
    assert payload["retrieval_anchor_price"] == 180.0


def test_predict_one_v3_carries_retrieval_diagnostics_when_bundle_exists(
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": 86,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 2,
            "mod_features_json": "{}",
        },
    )
    monkeypatch.setattr(
        serve,
        "_load_bundle_if_present",
        lambda **_kwargs: {
            "vectorizer": _DummyVectorizer(),
            "models": {
                "p10": _DummyRegressor(95.0),
                "p50": _DummyRegressor(120.0),
                "p90": _DummyRegressor(140.0),
                "fast_sale_24h": _DummyRegressor(109.0),
                "sale_probability": _DummyClassifier(),
            },
            "fallback_fast_sale_multiplier": 0.9,
            "metadata": {"row_count": 1200},
        },
    )
    client = _RetrievalClient(
        [
            {"candidate_price_chaos": 160.0, "distance_score": 0.06},
            {"candidate_price_chaos": 140.0, "distance_score": 0.08},
            {"candidate_price_chaos": 200.0, "distance_score": 0.2},
        ]
    )

    payload = serve.predict_one_v3(
        client,
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/unused",
    )

    assert payload["prediction_source"] == "v3_model"
    assert payload["retrieval_stage"] == 4
    assert payload["retrieval_effective_support"] == 3
    assert payload["retrieval_anchor_price"] is not None
    assert payload["prediction_as_of_ts"]
