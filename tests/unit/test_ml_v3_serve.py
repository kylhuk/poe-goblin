from __future__ import annotations

import json
from datetime import UTC, datetime

from poe_trade.ml.v3 import serve
from poe_trade.ml.v3 import hybrid_search
from poe_trade.ml.v3.hybrid_search import SearchResult, run_search


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


class _RaisingRegressor:
    def predict(self, _X):  # noqa: ANN001
        raise ValueError("model runtime failure")


class _DummyClassifier:
    def predict_proba(self, _X):  # noqa: ANN001
        return [[0.2, 0.8]]


def _parsed_payload() -> dict[str, object]:
    return {
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
    }


def test_resolve_rollout_bundle_key_prefers_promoted_exact_cohort() -> None:
    cohort_key = "structured_boosted|default|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0"
    parent_cohort_key = (
        "structured_boosted|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0"
    )
    available_bundle_keys = {
        "structured_boosted::" + cohort_key,
        "sparse_retrieval::sparse_retrieval|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0",
    }
    promoted_rows = [
        {
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0",
            "promoted": 1,
        },
        {
            "strategy_family": "structured_boosted",
            "cohort_key": cohort_key,
            "promoted": 1,
        },
    ]

    selected = serve._resolve_rollout_bundle_key(
        strategy_family="structured_boosted",
        cohort_key=cohort_key,
        parent_cohort_key=parent_cohort_key,
        promoted_rows=promoted_rows,
        available_bundle_keys=available_bundle_keys,
    )

    assert selected == "structured_boosted::" + cohort_key


def test_resolve_rollout_bundle_key_falls_back_to_promoted_parent() -> None:
    cohort_key = (
        "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
    )
    parent_cohort_key = (
        "sparse_retrieval|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
    )
    parent_bundle_key = "sparse_retrieval::" + parent_cohort_key

    selected = serve._resolve_rollout_bundle_key(
        strategy_family="sparse_retrieval",
        cohort_key=cohort_key,
        parent_cohort_key=parent_cohort_key,
        promoted_rows=[
            {
                "strategy_family": "sparse_retrieval",
                "cohort_key": parent_cohort_key,
                "promoted": 1,
            }
        ],
        available_bundle_keys={parent_bundle_key},
    )

    assert selected == parent_bundle_key


def test_resolve_rollout_bundle_key_supports_family_defaults() -> None:
    reference_parent = (
        "fungible_reference|v1|rarity=normal|corrupted=0|fractured=0|synthesised=0"
    )
    retrieval_parent = (
        "sparse_retrieval|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
    )
    ml_cohort = "structured_boosted|default|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0"
    ml_parent = (
        "structured_boosted|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0"
    )

    selected_reference = serve._resolve_rollout_bundle_key(
        strategy_family="fungible_reference",
        cohort_key="fungible_reference|fossil|v1|rarity=normal|corrupted=0|fractured=0|synthesised=0",
        parent_cohort_key=reference_parent,
        promoted_rows=[],
        available_bundle_keys={"fungible_reference::" + reference_parent},
    )
    assert selected_reference == "fungible_reference::" + reference_parent

    selected_retrieval = serve._resolve_rollout_bundle_key(
        strategy_family="sparse_retrieval",
        cohort_key="sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        parent_cohort_key=retrieval_parent,
        promoted_rows=[],
        available_bundle_keys={"sparse_retrieval::" + retrieval_parent},
    )
    assert selected_retrieval == "sparse_retrieval::" + retrieval_parent

    retrieval_same = "sparse_retrieval|default|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0"
    selected_ml = serve._resolve_rollout_bundle_key(
        strategy_family="structured_boosted",
        cohort_key=ml_cohort,
        parent_cohort_key=ml_parent,
        promoted_rows=[
            {
                "strategy_family": "sparse_retrieval",
                "cohort_key": retrieval_same,
                "promoted": 1,
            }
        ],
        available_bundle_keys={"sparse_retrieval::" + retrieval_same},
    )
    assert selected_ml == "sparse_retrieval::" + retrieval_same

    selected_abstain = serve._resolve_rollout_bundle_key(
        strategy_family="fallback_abstain",
        cohort_key="fallback_abstain|default|v1|rarity=unknown|corrupted=0|fractured=0|synthesised=0",
        parent_cohort_key="fallback_abstain|v1|rarity=unknown|corrupted=0|fractured=0|synthesised=0",
        promoted_rows=[],
        available_bundle_keys=set(),
    )
    assert selected_abstain is None


def test_resolve_rollout_bundle_key_is_deterministic_with_unsorted_rows() -> None:
    cohort_key = "structured_boosted|default|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0"
    parent_cohort_key = (
        "structured_boosted|v1|rarity=unique|corrupted=0|fractured=0|synthesised=0"
    )
    promoted_rows = [
        {
            "strategy_family": "structured_boosted",
            "cohort_key": cohort_key,
            "promoted": 1,
        },
        {
            "strategy_family": "fallback_abstain",
            "cohort_key": "fallback_abstain|default|v1|rarity=unknown|corrupted=0|fractured=0|synthesised=0",
            "promoted": 1,
        },
    ]
    available_bundle_keys = {"structured_boosted::" + cohort_key}

    first = serve._resolve_rollout_bundle_key(
        strategy_family="structured_boosted",
        cohort_key=cohort_key,
        parent_cohort_key=parent_cohort_key,
        promoted_rows=promoted_rows,
        available_bundle_keys=available_bundle_keys,
    )
    second = serve._resolve_rollout_bundle_key(
        strategy_family="structured_boosted",
        cohort_key=cohort_key,
        parent_cohort_key=parent_cohort_key,
        promoted_rows=list(reversed(promoted_rows)),
        available_bundle_keys=available_bundle_keys,
    )

    assert first == second == "structured_boosted::" + cohort_key


def test_resolve_rollout_bundle_key_handles_duplicate_promoted_rows() -> None:
    cohort_key = "shared|default|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0"
    promoted_rows = [
        {
            "strategy_family": "sparse_retrieval",
            "cohort_key": cohort_key,
            "promoted": 1,
        },
        {
            "strategy_family": "structured_boosted",
            "cohort_key": cohort_key,
            "promoted": 1,
        },
    ]
    available_bundle_keys = {
        "sparse_retrieval::" + cohort_key,
        "structured_boosted::" + cohort_key,
    }

    preferred = serve._resolve_rollout_bundle_key(
        strategy_family="structured_boosted",
        cohort_key=cohort_key,
        parent_cohort_key="structured_boosted|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        promoted_rows=promoted_rows,
        available_bundle_keys=available_bundle_keys,
    )
    assert preferred == "structured_boosted::" + cohort_key

    ambiguous = serve._resolve_rollout_bundle_key(
        strategy_family="fungible_reference",
        cohort_key=cohort_key,
        parent_cohort_key="fungible_reference|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        promoted_rows=promoted_rows,
        available_bundle_keys=available_bundle_keys,
    )
    assert ambiguous is None


def test_load_promoted_rollout_rows_uses_shared_sql_table_constant(
    monkeypatch,
) -> None:
    captured: dict[str, str] = {}

    def _fake_query_rows(_client, query: str):
        captured["query"] = query
        return []

    monkeypatch.setattr(serve, "_query_rows", _fake_query_rows)

    serve._load_promoted_rollout_rows(_Client(), league="Mirage")

    assert f"FROM {serve.sql.ROLLOUT_STATE_TABLE}" in captured["query"]


def test_predict_one_v3_fallback_returns_dual_prices(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
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
    assert payload["uncertainty_tier"] == "high"
    assert payload["price_recommendation_eligible"] is False


def test_predict_one_v3_fallback_survives_retrieval_query_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )
    monkeypatch.setattr(
        serve.sql,
        "build_retrieval_candidate_query",
        lambda **_kwargs: "RETRIEVE",
    )

    def _fake_query_rows(_client, query: str):
        if query == "RETRIEVE":
            raise RuntimeError("retrieval unavailable")
        if "quantileTDigest(0.5)(target_price_chaos)" in query:
            return [{"p50": 120.0, "rows": 32}]
        return []

    monkeypatch.setattr(serve, "_query_rows", _fake_query_rows)

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/does/not/exist",
    )

    assert payload["prediction_source"] == "v3_median_fallback"
    assert payload["fair_value_p50"] == 120.0
    assert payload["retrieval_stage"] == 0
    assert payload["retrieval_candidate_count"] == 0


def test_predict_one_v3_fallback_survives_median_query_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )

    def _fake_query_rows(_client, query: str):
        if "quantileTDigest(0.5)(target_price_chaos)" in query:
            raise RuntimeError("median unavailable")
        return []

    monkeypatch.setattr(serve, "_query_rows", _fake_query_rows)

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/does/not/exist",
    )

    assert payload["prediction_source"] == "v3_median_fallback"
    assert payload["fair_value_p50"] == 1.0
    assert payload["support_count_recent"] == 0
    assert payload["fast_sale_24h_price"] == 0.9
    assert payload["confidence"] == 0.1


def test_predict_one_v3_emits_prediction_contract_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/does/not/exist",
    )

    assert payload["strategy_family"] == "sparse_retrieval"
    assert payload["cohort_key"].startswith("sparse_retrieval|")
    assert payload["parent_cohort_key"].startswith("sparse_retrieval|")
    assert payload["engine_version"] == "ml_v3"
    assert isinstance(payload["fallback_depth"], int)
    assert payload["incumbent_flag"] in {0, 1}


def test_predict_one_v3_uses_direct_fast_sale_model_when_bundle_exists(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
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
    assert payload["confidence"] == 0.1


def test_predict_one_v3_falls_back_when_bundle_schema_is_incomplete(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )
    monkeypatch.setattr(
        serve,
        "_load_bundle_if_present",
        lambda **_kwargs: {
            "vectorizer": object(),
            "models": {},
        },
    )

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/unused",
    )

    assert payload["prediction_source"] == "v3_median_fallback"


def test_predict_one_v3_ignores_malformed_fast_sale_model(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
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
                "fast_sale_24h": object(),
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
    assert payload["fast_sale_24h_price"] == 108.0


def test_predict_one_v3_ignores_malformed_sale_probability_model(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
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
                "sale_probability": object(),
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
    assert payload["sale_probability_24h"] == 0.5


def test_predict_one_v3_defaults_on_malformed_fast_sale_multiplier(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
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
            },
            "fallback_fast_sale_multiplier": "not-a-number",
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
    assert payload["fast_sale_24h_price"] == 108.0


def test_predict_one_v3_runs_retrieval_search_and_attaches_diagnostics(
    monkeypatch,
) -> None:
    parsed_item = _parsed_payload()
    parsed_item["mod_features_json"] = (
        '{"explicit.crit_chance": 10, "explicit.life": 5}'
    )
    retrieval_calls: dict[str, object] = {}

    def _fake_parse(_text: str) -> dict[str, object]:
        return parsed_item

    monkeypatch.setattr(serve.workflows, "_parse_clipboard_item", _fake_parse)

    def _fake_run_search(
        *,
        parsed_item: dict[str, object],
        candidate_rows: list[dict[str, object]],
        ranked_affixes: list[dict[str, object]] | None,
        stage_support_targets=None,
        max_candidates: int,
    ) -> SearchResult:
        retrieval_calls["parsed_item"] = parsed_item
        retrieval_calls["candidate_rows"] = candidate_rows
        retrieval_calls["ranked_affixes"] = ranked_affixes
        retrieval_calls["max_candidates"] = max_candidates
        return SearchResult(
            stage=2,
            candidates=[
                {
                    "identity_key": "cmp-1",
                    "price": 99.0,
                    "score": 0.77,
                }
            ],
            dropped_affixes=["explicit.life"],
            effective_support=3,
            candidate_count=5,
            degradation_reason=None,
        )

    monkeypatch.setattr(serve.hybrid_search, "run_search", _fake_run_search)
    retrieval_query = {
        "built": False,
        "args": {},
    }

    def _fake_build_query(
        *, league: str, route: str, item_state_key: str, limit: int = 2000
    ) -> str:
        retrieval_query.update(
            {
                "built": True,
                "args": {
                    "league": league,
                    "route": route,
                    "item_state_key": item_state_key,
                    "limit": limit,
                },
            }
        )
        return "RETRIEVE"

    monkeypatch.setattr(serve.sql, "build_retrieval_candidate_query", _fake_build_query)

    def _fake_query_rows(_client, query: str):
        if query == "RETRIEVE":
            return [
                {
                    "identity_key": "id-1",
                    "base_type": "Hubris Circlet",
                    "rarity": "Rare",
                    "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
                    "target_price_chaos": 100.0,
                    "target_fast_sale_24h_price": 95.0,
                    "target_sale_probability_24h": 0.62,
                    "support_count_recent": 5,
                    "mod_features_json": '{"explicit.crit_chance": 10}',
                    "as_of_ts": "2026-03-22T10:00:00",
                },
                {
                    "identity_key": "id-2",
                    "base_type": "Hubris Circlet",
                    "rarity": "Rare",
                    "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
                    "target_price_chaos": 101.0,
                    "target_fast_sale_24h_price": 96.0,
                    "target_sale_probability_24h": 0.60,
                    "support_count_recent": 5,
                    "mod_features_json": '{"explicit.crit_chance": 10}',
                    "as_of_ts": "2026-03-22T09:00:00",
                },
            ]
        return []

    monkeypatch.setattr(serve, "_query_rows", _fake_query_rows)

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/does/not/exist",
    )

    assert retrieval_query["built"] is True
    assert retrieval_query["args"]["league"] == "Mirage"
    assert retrieval_query["args"]["route"] == "sparse_retrieval"
    assert (
        retrieval_query["args"]["item_state_key"]
        == "rare|corrupted=0|fractured=0|synthesised=0"
    )

    assert isinstance(retrieval_calls["parsed_item"], dict)
    assert len(retrieval_calls["candidate_rows"]) == 2
    assert retrieval_calls["ranked_affixes"]
    assert retrieval_calls["max_candidates"] == 64

    assert payload["retrieval_stage"] == 2
    assert payload["retrievalStage"] == 2
    assert payload["retrieval_candidate_count"] == 5
    assert payload["retrievalCandidateCount"] == 5
    assert payload["retrieval_effective_support"] == 3
    assert payload["retrieval_effectiveSupport"] == 3
    assert payload["retrieval_dropped_affixes"] == ["explicit.life"]
    assert payload["retrievalDroppedAffixes"] == ["explicit.life"]
    assert payload["retrieval_degradation_reason"] is None


def test_predict_one_v3_preserves_bundle_prediction_with_retrieval_context(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
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
    monkeypatch.setattr(
        serve.sql,
        "build_retrieval_candidate_query",
        lambda **_kwargs: "RETRIEVE",
    )
    retrieval_called = {"run": 0}

    def _fake_run_search(
        *,
        parsed_item: dict[str, object],
        candidate_rows: list[dict[str, object]],
        ranked_affixes: list[dict[str, object]] | None,
        stage_support_targets=None,
        max_candidates: int,
    ) -> SearchResult:
        retrieval_called["run"] += 1
        return SearchResult(
            stage=4,
            candidates=[],
            dropped_affixes=[],
            effective_support=0,
            candidate_count=0,
            degradation_reason="no_relevant_comparables",
        )

    monkeypatch.setattr(serve.hybrid_search, "run_search", _fake_run_search)

    def _fake_query_rows(_client, query: str):
        if query == "RETRIEVE":
            return []
        return []

    monkeypatch.setattr(serve, "_query_rows", _fake_query_rows)

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/unused",
    )

    assert retrieval_called["run"] == 1
    assert payload["prediction_source"] == "v3_model"
    assert payload["fair_value_p50"] == 120.0
    assert payload["retrieval_stage"] == 4
    assert payload["retrieval_degradation_reason"] == "no_relevant_comparables"


def test_predict_one_v3_falls_back_when_core_predictor_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )
    monkeypatch.setattr(
        serve,
        "_load_bundle_if_present",
        lambda **_kwargs: {
            "vectorizer": _DummyVectorizer(),
            "models": {
                "p10": _DummyRegressor(95.0),
                "p50": _RaisingRegressor(),
                "p90": _DummyRegressor(140.0),
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

    assert payload["prediction_source"] == "v3_median_fallback"


def test_load_bundle_if_present_returns_none_on_corrupt_bundle(monkeypatch) -> None:
    monkeypatch.setattr(serve.Path, "exists", lambda _self: True)

    def _raise_load(_path):  # noqa: ANN001
        raise ValueError("corrupt")

    monkeypatch.setattr(serve.joblib, "load", _raise_load)

    payload = serve._load_bundle_if_present(
        model_dir="/unused",
        league="Mirage",
        route="sparse_retrieval",
    )

    assert payload is None


def test_predict_one_v3_returns_hybrid_prediction_source(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )
    monkeypatch.setattr(
        serve,
        "_load_bundle_if_present",
        lambda **_kwargs: {
            "vectorizer": _DummyVectorizer(),
            "models": {
                "p10": _DummyRegressor(90.0),
                "p50": _DummyRegressor(110.0),
                "p90": _DummyRegressor(130.0),
                "fast_sale_24h": _DummyRegressor(102.0),
                "sale_probability": _DummyClassifier(),
            },
            "metadata": {"row_count": 100},
            "fair_value_residual_model": _DummyRegressor(4.0),
            "fast_sale_residual_model": _DummyRegressor(2.0),
        },
    )
    monkeypatch.setattr(
        serve.sql,
        "build_retrieval_candidate_query",
        lambda **_kwargs: "RETRIEVE",
    )
    monkeypatch.setattr(
        serve,
        "_query_rows",
        lambda _client, _query: [
            {
                "identity_key": "id-1",
                "base_type": "Hubris Circlet",
                "rarity": "Rare",
                "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
                "target_price_chaos": 100.0,
                "target_fast_sale_24h_price": 95.0,
                "target_sale_probability_24h": 0.62,
                "support_count_recent": 5,
                "mod_features_json": "{}",
                "as_of_ts": "2026-03-22T10:00:00",
            }
        ],
    )
    monkeypatch.setattr(
        serve.hybrid_search,
        "run_search",
        lambda **_kwargs: SearchResult(
            stage=2,
            candidates=[{"identity_key": "id-1", "price": 100.0, "score": 0.9}],
            dropped_affixes=[],
            effective_support=1,
            candidate_count=1,
            degradation_reason=None,
        ),
    )

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/unused",
    )

    assert payload["prediction_source"] == "v3_hybrid"


def test_predict_one_v3_uses_stage_zero_prior_when_no_comparables(monkeypatch) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )
    monkeypatch.setattr(serve, "_load_bundle_if_present", lambda **_kwargs: None)
    monkeypatch.setattr(
        serve.sql,
        "build_retrieval_candidate_query",
        lambda **_kwargs: "RETRIEVE",
    )
    monkeypatch.setattr(serve, "_query_rows", lambda _client, _query: [])
    monkeypatch.setattr(
        serve.hybrid_search,
        "run_search",
        lambda **_kwargs: SearchResult(
            stage=0,
            candidates=[],
            dropped_affixes=[],
            effective_support=0,
            candidate_count=0,
            degradation_reason="no_relevant_comparables",
        ),
    )

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/unused",
    )

    assert payload["estimate_trust"] == "low"
    assert payload["searchDiagnostics"]["stage"] == 0


def test_predict_one_v3_does_not_apply_residual_on_stage_zero_prior(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        serve.workflows,
        "_parse_clipboard_item",
        lambda _text: _parsed_payload(),
    )
    monkeypatch.setattr(
        serve,
        "_load_bundle_if_present",
        lambda **_kwargs: {
            "vectorizer": _DummyVectorizer(),
            "models": {
                "p10": _DummyRegressor(90.0),
                "p50": _DummyRegressor(110.0),
                "p90": _DummyRegressor(130.0),
                "fast_sale_24h": _DummyRegressor(102.0),
            },
            "fair_value_residual_model": _DummyRegressor(20.0),
        },
    )
    monkeypatch.setattr(
        serve.sql,
        "build_retrieval_candidate_query",
        lambda **_kwargs: "RETRIEVE",
    )
    monkeypatch.setattr(serve, "_query_rows", lambda _client, _query: [])
    monkeypatch.setattr(
        serve.hybrid_search,
        "run_search",
        lambda **_kwargs: SearchResult(
            stage=0,
            candidates=[],
            dropped_affixes=[],
            effective_support=0,
            candidate_count=0,
            degradation_reason="no_relevant_comparables",
        ),
    )

    payload = serve.predict_one_v3(
        _Client(),
        league="Mirage",
        clipboard_text="dummy",
        model_dir="/unused",
    )

    assert payload["comparablesSummary"]["anchorPrice"] == payload["fair_value_p50"]


def test_run_search_enforces_cohort_native_hard_filters() -> None:
    parsed_item = {
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": "{}",
    }

    candidate_rows = [
        {
            "identity_key": "ok-1",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 100.0,
            "support_count_recent": 10,
        },
        {
            "identity_key": "wrong-league",
            "league": "Settlers",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 101.0,
            "support_count_recent": 10,
        },
        {
            "identity_key": "wrong-family",
            "league": "Mirage",
            "strategy_family": "structured_boosted",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 102.0,
            "support_count_recent": 10,
        },
        {
            "identity_key": "wrong-cohort",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|ring|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 103.0,
            "support_count_recent": 10,
        },
        {
            "identity_key": "wrong-material",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=1|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=1|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=1|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 104.0,
            "support_count_recent": 10,
        },
    ]

    result = run_search(
        parsed_item=parsed_item,
        candidate_rows=candidate_rows,
        ranked_affixes=[],
        stage_support_targets={1: 1, 2: 1, 3: 1, 4: 1},
        max_candidates=64,
    )

    assert [candidate["identity_key"] for candidate in result.candidates] == ["ok-1"]


def test_run_search_enforces_hard_candidate_cap_of_64() -> None:
    parsed_item = {
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": "{}",
    }

    rows = [
        {
            "identity_key": f"id-{i:03d}",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 100.0 + i,
            "support_count_recent": 10,
        }
        for i in range(80)
    ]

    result = run_search(
        parsed_item=parsed_item,
        candidate_rows=rows,
        ranked_affixes=[],
        stage_support_targets={1: 1, 2: 1, 3: 1, 4: 1},
        max_candidates=200,
    )

    assert result.stage == 1
    assert result.candidate_count == 80
    assert len(result.candidates) == 64


def test_run_search_uses_deterministic_latency_budget_fallback() -> None:
    parsed_item = {
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": "{}",
    }
    rows = [
        {
            "identity_key": f"id-{i:03d}",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 200.0 - i,
            "support_count_recent": 4,
            "as_of_ts": f"2026-03-2{i % 9}T10:00:00",
        }
        for i in range(70)
    ]

    result = run_search(
        parsed_item=parsed_item,
        candidate_rows=rows,
        ranked_affixes=[],
        max_candidates=128,
        latency_budget_ms=0,
    )

    assert result.stage == 4
    assert result.degradation_reason == "latency_budget_exceeded"
    assert result.candidate_count == 70
    assert len(result.candidates) == 64
    assert result.candidates[0]["identity_key"] == "id-000"


def test_run_search_rejects_candidates_missing_cohort_contract_fields() -> None:
    parsed_item = {
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": "{}",
    }
    base_row = {
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": "{}",
        "target_price_chaos": 100.0,
        "support_count_recent": 10,
    }
    rows = [
        {
            **base_row,
            "identity_key": "ok",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        },
        {
            **base_row,
            "identity_key": "missing-league",
            "league": None,
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        },
        {
            **base_row,
            "identity_key": "missing-family",
            "league": "Mirage",
            "strategy_family": "",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        },
        {
            **base_row,
            "identity_key": "missing-cohort",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": None,
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        },
        {
            **base_row,
            "identity_key": "missing-material",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "",
        },
    ]

    result = run_search(
        parsed_item=parsed_item,
        candidate_rows=rows,
        ranked_affixes=[],
        stage_support_targets={1: 1, 2: 1, 3: 1, 4: 1},
    )

    assert [candidate["identity_key"] for candidate in result.candidates] == ["ok"]


def test_run_search_stage1_rejects_adjacent_tier_value_rows() -> None:
    parsed_item = {
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": '{"explicit.life": 10}',
    }
    row = {
        "identity_key": "adjacent",
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": '{"explicit.life": 11}',
        "target_price_chaos": 110.0,
        "support_count_recent": 10,
    }
    ranked_affixes = [{"affix": "explicit.life", "importance": 5.0, "support": 10}]

    result = run_search(
        parsed_item=parsed_item,
        candidate_rows=[row],
        ranked_affixes=ranked_affixes,
        stage_support_targets={1: 1, 2: 1, 3: 1, 4: 1},
    )

    assert result.stage == 2


def test_run_search_latency_fallback_stops_scoring_early(monkeypatch) -> None:
    parsed_item = {
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": "{}",
    }
    rows = [
        {
            "identity_key": f"id-{i:03d}",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 100.0,
            "support_count_recent": 10,
        }
        for i in range(200)
    ]

    calls = {"scored": 0, "ticks": 0}

    def _fake_score_candidate(**kwargs):  # noqa: ANN003
        calls["scored"] += 1
        row = kwargs["row"]
        return {
            "identity_key": row["identity_key"],
            "price": row["target_price_chaos"],
            "score": 0.9,
            "matched_affixes": [],
            "missing_affixes": [],
            "observed_at": None,
            "support": 1.0,
        }

    def _fake_monotonic() -> float:
        calls["ticks"] += 1
        if calls["ticks"] < 8:
            return 0.0
        return 1.0

    monkeypatch.setattr(hybrid_search, "_score_candidate", _fake_score_candidate)
    monkeypatch.setattr(hybrid_search, "monotonic", _fake_monotonic)

    result = run_search(
        parsed_item=parsed_item,
        candidate_rows=rows,
        ranked_affixes=[],
        stage_support_targets={1: 500, 2: 500, 3: 500, 4: 500},
        latency_budget_ms=150,
    )

    assert result.degradation_reason == "latency_budget_exceeded"
    assert calls["scored"] < len(rows)


def test_run_search_uses_supplied_now_utc_for_deterministic_recency() -> None:
    parsed_item = {
        "league": "Mirage",
        "strategy_family": "sparse_retrieval",
        "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
        "mod_features_json": "{}",
    }
    rows = [
        {
            "identity_key": "older",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 100.0,
            "support_count_recent": 10,
            "as_of_ts": "2026-03-01T00:00:00+00:00",
        },
        {
            "identity_key": "newer",
            "league": "Mirage",
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "item_state_key": "rare|corrupted=0|fractured=0|synthesised=0",
            "mod_features_json": "{}",
            "target_price_chaos": 100.0,
            "support_count_recent": 10,
            "as_of_ts": "2026-03-10T00:00:00+00:00",
        },
    ]

    result = run_search(
        parsed_item=parsed_item,
        candidate_rows=rows,
        ranked_affixes=[],
        stage_support_targets={1: 1, 2: 1, 3: 1, 4: 1},
        now_utc=datetime(2026, 3, 12, 0, 0, 0, tzinfo=UTC),
    )

    assert [candidate["identity_key"] for candidate in result.candidates[:2]] == [
        "newer",
        "older",
    ]
