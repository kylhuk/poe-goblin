# Hybrid Value Pricing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current direct v3 model-plus-median-fallback pricing path with a comparables-first hybrid estimator that returns fair value, fast-sale value, confidence, and explanation/scenario metadata from one unified serving contract.

**Architecture:** Keep the current v3 route-based runtime, bundle path, registry, evaluation tables, and automation surfaces, but change what each route bundle contains and how serving works. The new path selects a deterministic route, normalizes item state and affixes, retrieves scored comparables, builds a robust anchor, applies capped residual correction, computes calibrated confidence, and returns a unified explanation payload that the frontend consumes directly.

**Tech Stack:** Python 3.11, ClickHouse, existing `poe_trade.ml.v3` modules, sklearn-based residual/calibration path, pytest, TypeScript frontend normalization and UI.

---

## File Structure

- Create: `poe_trade/ml/v3/routes.py` — canonical route selection shared by training, serving, and tests.
- Create: `poe_trade/ml/v3/hybrid_search.py` — item-state normalization, affix importance, retrieval-stage filters, scoring, effective-support logic, and prior fallback selection.
- Create: `poe_trade/ml/v3/hybrid_anchor.py` — weighted anchor and interval calculation.
- Create: `poe_trade/ml/v3/hybrid_explain.py` — explanation payload, comparable summaries, and scenario generation.
- Modify: `poe_trade/ml/v3/features.py` — richer normalized feature extraction for route/item-state/affix descriptors.
- Modify: `poe_trade/ml/v3/sql.py` — training-example SQL fields and retrieval-candidate support fields if required.
- Modify: `poe_trade/ml/v3/train.py` — train/search config, priors, affix-importance artifacts, residual heads, and bundle contents.
- Modify: `poe_trade/ml/v3/serve.py` — replace median fallback/direct-only path with hybrid serving pipeline.
- Modify: `poe_trade/ml/v3/eval.py` — evaluate hybrid outputs and preserve current promotion surfaces.
- Modify: `poe_trade/api/ml.py` — request validation and unified hybrid response normalization.
- Modify: `poe_trade/api/ops.py` — comparable/explanation fields if price-check/ops payloads need alignment.
- Modify: `poe_trade/services/ml_trainer.py` — keep trainer orchestration aligned with hybrid artifacts.
- Modify: `frontend/src/types/api.ts` — add canonical hybrid diagnostics/explanation/scenario types.
- Modify: `frontend/src/services/api.ts` — normalize hybrid response fields and remove now-unneeded second-call assumptions.
- Modify: `frontend/src/components/tabs/PriceCheckTab.tsx` — render unified value drivers, comparable diagnostics, and scenarios from one response.
- Modify: `schema/migrations/0053_ml_v3_training_and_serving_store.sql` only if the existing retrieval candidate table cannot support the approved search contract.
- Create: `tests/unit/test_ml_v3_routes.py`
- Create: `tests/unit/test_ml_v3_hybrid_search.py`
- Create: `tests/unit/test_ml_v3_hybrid_anchor.py`
- Create: `tests/unit/test_ml_v3_hybrid_explain.py`
- Create: `frontend/src/components/tabs/PriceCheckTab.test.tsx`
- Modify: `tests/unit/test_ml_v3_features.py`
- Modify: `tests/unit/test_ml_v3_sql_contract.py`
- Modify: `tests/unit/test_ml_v3_train.py`
- Modify: `tests/unit/test_ml_v3_serve.py`
- Modify: `tests/unit/test_ml_v3_eval.py`
- Modify: `tests/unit/test_api_ml_routes.py`
- Modify: `tests/unit/test_service_ml_trainer.py`

### Task 1: Canonical Route and Item-State Contract

**Files:**
- Create: `poe_trade/ml/v3/routes.py`
- Modify: `poe_trade/ml/v3/serve.py`
- Modify: `poe_trade/ml/v3/sql.py`
- Test: `tests/unit/test_ml_v3_routes.py`

- [ ] **Step 1: Write the failing route-selection tests**

```python
from poe_trade.ml.v3 import routes


def test_select_route_matches_current_sparse_rare_behavior() -> None:
    parsed = {"category": "helmet", "rarity": "Rare"}
    assert routes.select_route(parsed) == "sparse_retrieval"


def test_select_route_is_shared_for_serving_and_training() -> None:
    parsed = {"category": "cluster_jewel", "rarity": "Rare"}
    assert routes.select_route(parsed) == "cluster_jewel_retrieval"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_routes.py -v`
Expected: FAIL because `poe_trade.ml.v3.routes` does not exist.

- [ ] **Step 3: Write minimal shared route-selection implementation**

```python
def select_route(parsed: Mapping[str, Any]) -> str:
    ...  # move current deterministic logic out of serve.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/routes.py poe_trade/ml/v3/serve.py poe_trade/ml/v3/sql.py tests/unit/test_ml_v3_routes.py
git commit -m "refactor: share v3 route selection"
```

### Task 2: Expand Feature Normalization for Hybrid Search

**Files:**
- Modify: `poe_trade/ml/v3/features.py`
- Modify: `poe_trade/ml/v3/sql.py`
- Modify: `tests/unit/test_ml_v3_features.py`

- [ ] **Step 1: Write failing feature tests for item-state and affix metadata**

```python
def test_build_feature_row_emits_item_state_fields() -> None:
    parsed = {
        "category": "helmet",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "corrupted": 1,
        "fractured": 0,
        "synthesised": 0,
        "mod_features_json": '{"explicit.life": 1}',
    }
    row = build_feature_row(parsed)
    assert row["item_state_key"] == "rare|corrupted=1|fractured=0|synthesised=0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_features.py -k item_state -v`
Expected: FAIL because the fields are not produced yet.

- [ ] **Step 3: Implement minimal normalized feature additions**

```python
row["item_state_key"] = build_item_state_key(parsed_item)
row["route_family"] = select_route(parsed_item)
row["base_identity_key"] = ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_features.py -k item_state -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/features.py poe_trade/ml/v3/sql.py tests/unit/test_ml_v3_features.py
git commit -m "feat: add hybrid feature normalization"
```

### Task 2b: Protect SQL Contract Changes

**Files:**
- Modify: `poe_trade/ml/v3/sql.py`
- Modify: `tests/unit/test_ml_v3_sql_contract.py`

- [ ] **Step 1: Write the failing SQL contract tests**

```python
def test_training_sql_emits_route_and_item_state_search_keys() -> None:
    sql = build_training_examples_insert_sql(...)
    assert "item_state_key" in sql


def test_retrieval_candidate_sql_can_partition_by_route_and_state() -> None:
    sql = build_retrieval_candidate_sql(...)
    assert "route" in sql and "item_state_key" in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_sql_contract.py -k "item_state or retrieval_candidate" -v`
Expected: FAIL because the SQL contract does not yet cover the hybrid search keys.

- [ ] **Step 3: Implement minimal SQL contract changes**

```python
# extend SQL builders/DDL fragments with route-aware search keys used by hybrid retrieval
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_sql_contract.py -k "item_state or retrieval_candidate" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/sql.py tests/unit/test_ml_v3_sql_contract.py
git commit -m "test: lock hybrid sql contracts"
```

### Task 3: Deterministic Affix-Importance Ranking and Cohort Fallbacks

**Files:**
- Create: `poe_trade/ml/v3/hybrid_search.py`
- Test: `tests/unit/test_ml_v3_hybrid_search.py`

- [ ] **Step 1: Write the failing affix-importance tests**

```python
def test_rank_affixes_prefers_high_lift_low_frequency_mods() -> None:
    ranked = rank_affixes_by_importance(target_item=..., cohort_rows=[...])
    assert ranked[0].affix_key == "explicit.max_life"


def test_rank_affixes_falls_back_from_30d_to_90d_then_route_prior() -> None:
    ranked = rank_affixes_by_importance(target_item=..., cohort_rows=[])
    assert ranked[0].source in {"90d_cohort", "route_prior"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_search.py -k "importance or route_prior" -v`
Expected: FAIL because affix-importance ranking and fallback logic do not exist.

- [ ] **Step 3: Implement minimal deterministic importance logic**

```python
def rank_affixes_by_importance(...):
    ...  # 30d cohort -> 90d cohort -> route-family prior fallback
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_search.py -k "importance or route_prior" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/hybrid_search.py tests/unit/test_ml_v3_hybrid_search.py
git commit -m "feat: rank hybrid affix importance"
```

### Task 4: Deterministic Comparable Retrieval Engine

**Files:**
- Create: `poe_trade/ml/v3/hybrid_search.py`
- Modify: `poe_trade/ml/v3/sql.py`
- Test: `tests/unit/test_ml_v3_hybrid_search.py`

- [ ] **Step 1: Write failing retrieval-stage tests**

```python
def test_search_preserves_high_value_affixes_before_common_ones() -> None:
    result = run_search(...)
    assert result.stage == 3
    assert result.dropped_affixes == ["explicit.light_radius"]


def test_search_applies_specified_similarity_weights_and_penalties() -> None:
    result = run_search(...)
    assert result.candidates[0].score == pytest.approx(0.82, rel=1e-3)


def test_search_uses_prior_only_stage_zero_when_no_candidates_exist() -> None:
    result = run_search(...)
    assert result.stage == 0
    assert result.candidate_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_search.py -v`
Expected: FAIL because the search engine does not exist.

- [ ] **Step 3: Implement minimal stage ladder and effective-support logic**

```python
@dataclass
class SearchResult:
    stage: int
    candidates: list[dict[str, Any]]
    dropped_affixes: list[str]
    effective_support: int
    degradation_reason: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_search.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/hybrid_search.py poe_trade/ml/v3/sql.py tests/unit/test_ml_v3_hybrid_search.py
git commit -m "feat: add hybrid comparable retrieval stages"
```

### Task 5: Robust Anchor Calculation

**Files:**
- Create: `poe_trade/ml/v3/hybrid_anchor.py`
- Test: `tests/unit/test_ml_v3_hybrid_anchor.py`

- [ ] **Step 1: Write failing anchor tests**

```python
def test_anchor_uses_weighted_median_from_positive_weight_candidates() -> None:
    anchor = build_anchor([...])
    assert anchor.anchor_price == 120.0


def test_anchor_ignores_zero_weight_rows_for_effective_support() -> None:
    anchor = build_anchor([...])
    assert anchor.effective_support == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_anchor.py -v`
Expected: FAIL because the anchor module does not exist.

- [ ] **Step 3: Implement minimal anchor calculator**

```python
def build_anchor(candidates: list[Candidate]) -> AnchorResult:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_anchor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/hybrid_anchor.py tests/unit/test_ml_v3_hybrid_anchor.py
git commit -m "feat: add hybrid anchor calculator"
```

### Task 6: Confidence and Recommendation Policy

**Files:**
- Modify: `poe_trade/ml/v3/hybrid_search.py`
- Modify: `tests/unit/test_ml_v3_hybrid_search.py`

- [ ] **Step 1: Write failing confidence-policy tests**

```python
def test_confidence_formula_matches_spec_components() -> None:
    result = score_confidence(...)
    assert result.confidence == pytest.approx(0.61, rel=1e-3)
    assert result.estimate_trust == "normal"


def test_stage_zero_sets_low_confidence_and_not_eligible() -> None:
    result = score_confidence(stage=0, ...)
    assert result.confidence == 0.10
    assert result.price_recommendation_eligible is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_search.py -k "confidence or eligible" -v`
Expected: FAIL because the deterministic confidence formula is not implemented.

- [ ] **Step 3: Implement minimal confidence/recommendation logic**

```python
def score_confidence(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_search.py -k "confidence or eligible" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/hybrid_search.py tests/unit/test_ml_v3_hybrid_search.py
git commit -m "feat: add hybrid confidence policy"
```

### Task 7: Train Residual and Prior Artifacts

**Files:**
- Modify: `poe_trade/ml/v3/train.py`
- Modify: `tests/unit/test_ml_v3_train.py`

- [ ] **Step 1: Write failing training-artifact tests**

```python
def test_train_route_v3_writes_hybrid_bundle_contents(tmp_path) -> None:
    result = train_route_v3(...)
    bundle = joblib.load(tmp_path / "v3" / "Mirage" / "sparse_retrieval" / "bundle.joblib")
    assert "search_config" in bundle
    assert "fair_value_residual_model" in bundle
    assert "route_family_priors" in bundle
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_train.py -k hybrid_bundle -v`
Expected: FAIL because current bundles only contain vectorizer/models/fallback multiplier metadata.

- [ ] **Step 3: Implement minimal hybrid bundle training changes**

```python
bundle = {
    "search_config": search_config,
    "route_family_priors": priors,
    "fair_value_residual_model": fair_model,
    "fast_sale_residual_model": fast_model,
    ...
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_train.py -k hybrid_bundle -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/train.py tests/unit/test_ml_v3_train.py
git commit -m "feat: train hybrid v3 artifacts"
```

### Task 7b: Residual Caps and Dual-Output Training Targets

**Files:**
- Modify: `poe_trade/ml/v3/train.py`
- Modify: `tests/unit/test_ml_v3_train.py`

- [ ] **Step 1: Write failing residual-cap and fast-sale-target tests**

```python
def test_hybrid_training_persists_fast_sale_target_metadata() -> None:
    bundle = train_route_v3(...)
    assert bundle["metadata"]["has_fast_sale_target"] is True


def test_residual_caps_follow_spec_thresholds() -> None:
    capped = apply_residual_cap(anchor_price=100.0, confidence=0.20, fair_residual=20.0, fast_residual=20.0)
    assert capped.fair_value == 8.0
    assert capped.fast_sale == 6.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_train.py -k "residual_cap or fast_sale_target" -v`
Expected: FAIL because the cap logic/metadata are not explicit yet.

- [ ] **Step 3: Implement minimal residual-cap and target metadata logic**

```python
def apply_residual_cap(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_train.py -k "residual_cap or fast_sale_target" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/train.py tests/unit/test_ml_v3_train.py
git commit -m "feat: cap hybrid residual adjustments"
```

### Task 8: Replace Serving Path with Hybrid Estimator

**Files:**
- Modify: `poe_trade/ml/v3/serve.py`
- Modify: `tests/unit/test_ml_v3_serve.py`

- [ ] **Step 1: Write failing serving tests for anchor + residual + stage zero behavior**

```python
def test_predict_one_v3_returns_hybrid_prediction_source(monkeypatch) -> None:
    payload = serve.predict_one_v3(...)
    assert payload["prediction_source"] == "v3_hybrid"


def test_predict_one_v3_uses_stage_zero_prior_when_no_comparables(monkeypatch) -> None:
    payload = serve.predict_one_v3(...)
    assert payload["estimate_trust"] == "low"
    assert payload["searchDiagnostics"]["stage"] == 0


def test_predict_one_v3_does_not_apply_residual_on_stage_zero_prior(monkeypatch) -> None:
    payload = serve.predict_one_v3(...)
    assert payload["comparablesSummary"]["anchorPrice"] == payload["fair_value_p50"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_serve.py -v`
Expected: FAIL because serving still uses direct model or median fallback.

- [ ] **Step 3: Implement minimal hybrid serving orchestration**

```python
route = routes.select_route(parsed)
search = hybrid_search.search_comparables(...)
anchor = hybrid_anchor.build_anchor(search.candidates)
prediction = apply_residual_models(...)
return hybrid_explain.build_response(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_serve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/serve.py tests/unit/test_ml_v3_serve.py poe_trade/ml/v3/routes.py poe_trade/ml/v3/hybrid_search.py poe_trade/ml/v3/hybrid_anchor.py
git commit -m "feat: serve hybrid value pricing"
```

### Task 8b: Preserve Fast-Sale and Sale-Probability Outputs in Serving

**Files:**
- Modify: `poe_trade/ml/v3/serve.py`
- Modify: `tests/unit/test_ml_v3_serve.py`

- [ ] **Step 1: Write failing serving tests for dual outputs**

```python
def test_predict_one_v3_returns_fast_sale_and_sale_probability_from_hybrid_path(monkeypatch) -> None:
    payload = serve.predict_one_v3(...)
    assert payload["fast_sale_24h_price"] is not None
    assert payload["sale_probability_24h"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_serve.py -k "fast_sale or sale_probability" -v`
Expected: FAIL because the hybrid path is not yet protecting those outputs explicitly.

- [ ] **Step 3: Implement minimal dual-output serving preservation**

```python
# keep fair value, fast sale, and sale probability populated in hybrid responses
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_serve.py -k "fast_sale or sale_probability" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/serve.py tests/unit/test_ml_v3_serve.py
git commit -m "feat: preserve hybrid dual outputs"
```

### Task 9: Add Explanation and Scenario Payloads

**Files:**
- Create: `poe_trade/ml/v3/hybrid_explain.py`
- Modify: `poe_trade/ml/v3/serve.py`
- Test: `tests/unit/test_ml_v3_hybrid_explain.py`

- [ ] **Step 1: Write failing explanation-payload tests**

```python
def test_build_response_includes_value_drivers_and_search_diagnostics() -> None:
    payload = build_hybrid_response(...)
    assert payload["searchDiagnostics"]["stage"] == 2
    assert payload["valueDrivers"]["positive"]


def test_stage_zero_response_omits_alternate_scenarios() -> None:
    payload = build_hybrid_response(...)
    assert payload["scenarioPrices"]["weakerRolls"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_explain.py -v`
Expected: FAIL because the explanation module does not exist.

- [ ] **Step 3: Implement minimal explanation/scenario builder**

```python
def build_hybrid_response(...):
    return {
        "searchDiagnostics": ...,
        "comparablesSummary": ...,
        "valueDrivers": ...,
        "scenarioPrices": ...,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_hybrid_explain.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/hybrid_explain.py poe_trade/ml/v3/serve.py tests/unit/test_ml_v3_hybrid_explain.py
git commit -m "feat: add hybrid pricing explanations"
```

### Task 10: Preserve Evaluation and Promotion Surfaces

**Files:**
- Modify: `poe_trade/ml/v3/eval.py`
- Modify: `tests/unit/test_ml_v3_eval.py`
- Modify: `tests/unit/test_service_ml_trainer.py`

- [ ] **Step 1: Write failing evaluation tests for hybrid outputs**

```python
def test_evaluate_run_keeps_dual_output_metrics_for_hybrid_predictions() -> None:
    payload = evaluate_run(...)
    assert payload["metrics"]["global_fair_value_mdape"] is not None
    assert payload["metrics"]["global_fast_sale_24h_mdape"] is not None


def test_evaluate_run_compares_anchor_model_and_hybrid_metrics() -> None:
    payload = evaluate_run(...)
    assert payload["summary"]["serving_path_parity_ok"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_eval.py tests/unit/test_service_ml_trainer.py -k hybrid -v`
Expected: FAIL because hybrid-specific fields/behavior are not reflected yet.

- [ ] **Step 3: Implement minimal eval/runtime compatibility changes**

```python
eval_row["serving_path_parity_ok"] = 1 if payload_shape_matches_hybrid else 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_eval.py tests/unit/test_service_ml_trainer.py -k hybrid -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/eval.py tests/unit/test_ml_v3_eval.py tests/unit/test_service_ml_trainer.py
git commit -m "feat: evaluate hybrid pricing artifacts"
```

### Task 11: Align Trainer and Ops Surfaces with Hybrid Artifacts

**Files:**
- Modify: `poe_trade/services/ml_trainer.py`
- Modify: `poe_trade/api/ops.py`
- Modify: `tests/unit/test_service_ml_trainer.py`
- Modify: `tests/unit/test_api_ml_routes.py`

- [ ] **Step 1: Write failing trainer/ops alignment tests**

```python
def test_ml_trainer_persists_hybrid_run_metadata() -> None:
    payload = run_trainer(...)
    assert payload["prediction_source"] == "v3_hybrid"


def test_ops_price_check_can_expose_hybrid_comparable_summary() -> None:
    body = get_price_check(...)
    assert "comparablesSummary" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_service_ml_trainer.py tests/unit/test_api_ml_routes.py -k "hybrid or comparablesSummary" -v`
Expected: FAIL because trainer/ops surfaces are not yet aligned.

- [ ] **Step 3: Implement minimal trainer/ops compatibility changes**

```python
# keep current trainer + automation endpoints working with hybrid bundle metadata
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_service_ml_trainer.py tests/unit/test_api_ml_routes.py -k "hybrid or comparablesSummary" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/services/ml_trainer.py poe_trade/api/ops.py tests/unit/test_service_ml_trainer.py tests/unit/test_api_ml_routes.py
git commit -m "feat: align hybrid trainer and ops surfaces"
```

### Task 12: Unify API Contract Around Hybrid Response

**Files:**
- Modify: `poe_trade/api/ml.py`
- Modify: `tests/unit/test_api_ml_routes.py`

- [ ] **Step 1: Write failing API contract tests**

```python
def test_predict_one_returns_hybrid_diagnostics_and_scenarios() -> None:
    body = call_predict_one(...)
    assert body["searchDiagnostics"]["stage"] == 1
    assert "scenarioPrices" in body


def test_predict_one_keeps_compatibility_fields_during_cutover() -> None:
    body = call_predict_one(...)
    assert "price_p50" in body
    assert body["estimateTrust"] in {"high", "normal", "low"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_api_ml_routes.py -k "hybrid or predict_one" -v`
Expected: FAIL because the normalized API payload does not include the new objects.

- [ ] **Step 3: Implement minimal API normalization changes**

```python
return {
    **compat_fields,
    "searchDiagnostics": ...,
    "comparablesSummary": ...,
    "valueDrivers": ...,
    "scenarioPrices": ...,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_api_ml_routes.py -k "hybrid or predict_one" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/api/ml.py tests/unit/test_api_ml_routes.py
git commit -m "feat: expose hybrid pricing contract"
```

### Task 13: Frontend Hybrid Rendering and Single-Response Cutover

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/components/tabs/PriceCheckTab.tsx`
- Create: `frontend/src/components/tabs/PriceCheckTab.test.tsx`
- Modify: `frontend/src/services/api.test.ts`

- [ ] **Step 1: Write failing frontend normalization/render tests**

```tsx
it('normalizes hybrid search diagnostics and scenarios', () => {
  const payload = normalizeMlPredictOneResponse(fixture)
  expect(payload.searchDiagnostics?.stage).toBe(2)
})

it('renders value drivers without a second predict-one merge', async () => {
  render(<PriceCheckTab />)
  expect(screen.getByText(/value drivers/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- src/services/api.test.ts src/components/tabs/PriceCheckTab.test.tsx`
Expected: FAIL because the frontend types and UI do not support the new contract yet.

- [ ] **Step 3: Implement minimal frontend hybrid contract support**

```ts
export interface SearchDiagnostics { stage: 0 | 1 | 2 | 3 | 4; ... }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- src/services/api.test.ts src/components/tabs/PriceCheckTab.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/services/api.ts frontend/src/services/api.test.ts frontend/src/components/tabs/PriceCheckTab.tsx frontend/src/components/tabs/PriceCheckTab.test.tsx
git commit -m "feat: render hybrid pricing diagnostics"
```

### Task 13b: Remove Second Predict-One Merge from Price Check UI

**Files:**
- Modify: `frontend/src/components/tabs/PriceCheckTab.tsx`
- Modify: `frontend/src/components/tabs/PriceCheckTab.test.tsx`

- [ ] **Step 1: Write the failing UI cutover test**

```tsx
it('uses the unified price-check response without calling mlPredictOne', async () => {
  vi.spyOn(api, 'mlPredictOne')
  render(<PriceCheckTab />)
  expect(api.mlPredictOne).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- src/components/tabs/PriceCheckTab.test.tsx`
Expected: FAIL because the component still makes the extra call.

- [ ] **Step 3: Implement minimal UI cutover**

```tsx
// remove secondary mlPredictOne merge and render from unified response only
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- src/components/tabs/PriceCheckTab.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tabs/PriceCheckTab.tsx frontend/src/components/tabs/PriceCheckTab.test.tsx
git commit -m "refactor: remove extra price-check predict call"
```

### Task 14: Remove Obsolete Runtime Dependencies Only After Hybrid Cutover

**Files:**
- Modify: `poe_trade/ml/workflows.py`
- Modify: `poe_trade/ml/cli.py`
- Modify: `tests/unit/test_ml_cli.py`
- Modify: `tests/unit/test_migrations.py`

- [ ] **Step 1: Write failing cleanup regression tests**

```python
def test_public_predict_path_no_longer_uses_legacy_workflow_predictors() -> None:
    ...


def test_cleanup_does_not_drop_tables_still_required_by_hybrid_runtime() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_ml_cli.py tests/unit/test_migrations.py -k cleanup -v`
Expected: FAIL because some legacy internals and cleanup assumptions remain transitional.

- [ ] **Step 3: Implement minimal legacy cleanup after replacement**

```python
# remove dead workflow helpers only after hybrid path owns public serving
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_ml_cli.py tests/unit/test_migrations.py -k cleanup -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/workflows.py poe_trade/ml/cli.py tests/unit/test_ml_cli.py tests/unit/test_migrations.py
git commit -m "refactor: remove obsolete pricing runtime code"
```

### Task 15: Full Verification

**Files:**
- Test: `tests/unit/test_ml_v3_routes.py`
- Test: `tests/unit/test_ml_v3_hybrid_search.py`
- Test: `tests/unit/test_ml_v3_hybrid_anchor.py`
- Test: `tests/unit/test_ml_v3_hybrid_explain.py`
- Test: `tests/unit/test_ml_v3_features.py`
- Test: `tests/unit/test_ml_v3_train.py`
- Test: `tests/unit/test_ml_v3_serve.py`
- Test: `tests/unit/test_ml_v3_eval.py`
- Test: `tests/unit/test_api_ml_routes.py`
- Test: `tests/unit/test_service_ml_trainer.py`
- Test: `frontend/src/services/api.test.ts`
- Test: `frontend/src/components/tabs/PriceCheckTab.test.tsx`

- [ ] **Step 1: Run the focused backend suite**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_routes.py tests/unit/test_ml_v3_hybrid_search.py tests/unit/test_ml_v3_hybrid_anchor.py tests/unit/test_ml_v3_hybrid_explain.py tests/unit/test_ml_v3_features.py tests/unit/test_ml_v3_train.py tests/unit/test_ml_v3_serve.py tests/unit/test_ml_v3_eval.py tests/unit/test_api_ml_routes.py tests/unit/test_service_ml_trainer.py -v`
Expected: PASS.

- [ ] **Step 2: Run any frontend tests/typechecks covering the new contract**

Run: `npm --prefix frontend run test -- src/services/api.test.ts src/components/tabs/PriceCheckTab.test.tsx && npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 3: Run migration verification if schema changed**

Run: `poe-migrate --status --dry-run`
Expected: pending/clean output consistent with the new migration set.

- [ ] **Step 4: Commit final verification-only fixes if needed**

```bash
git add .
git commit -m "test: verify hybrid value pricing cutover"
```
