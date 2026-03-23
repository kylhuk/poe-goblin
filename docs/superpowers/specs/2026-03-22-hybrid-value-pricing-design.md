# Hybrid Value Pricing Specification

## Goal

Build a comparables-first pricing system that always returns an estimated value for a pasted item, uses a learned residual model to correct the market anchor, degrades confidence honestly as match quality worsens, and explains which affixes and roll values drive the estimate.

## Current Implementation Snapshot

The shipped code does not implement the target hybrid yet.

- `poe_trade/ml/v3/train.py` trains route-local sklearn models with `DictVectorizer`, `GradientBoostingRegressor`, and `LogisticRegression`.
- `poe_trade/ml/v3/serve.py` serves those bundles directly and falls back to a simple median by `league + route + base_type + rarity` when no bundle exists.
- `schema/migrations/0053_ml_v3_training_and_serving_store.sql` defines `poe_trade.ml_v3_retrieval_candidates`, but the live v3 serving path does not use it.
- `poe_trade/ml/workflows.py` still contains older comparable-selection and anchor helpers, but they are not the current public predict path.

This specification replaces the current direct-model-plus-median-fallback behavior with a true hybrid estimator.

## Problem Statement

The current pricing path is weak for real item valuation because:

- it predicts directly from route-local models instead of grounding estimates in the actual market,
- it does not use a real comparable-search ladder for affix tiers and roll values,
- it does not preserve expensive and rare affixes as primary signals during search relaxation,
- it cannot explain price impact in a user-facing way,
- its median fallback can produce values that are available but not credible.

## Product Objective

For each item, return a value estimate that is:

- anchored in current comparable listings,
- adjusted for meaningful affix and roll differences,
- still available when exact matches are thin,
- accompanied by confidence and search-quality diagnostics,
- explainable in the frontend with concrete value drivers and what-if scenarios.

## Non-Goals

- Predicting the exact eventual sale price for every rare item.
- Building a full SHAP-style general ML explanation framework.
- Replacing all pricing-related frontend panels in one step.
- Removing every legacy ML helper before the new hybrid path is proven in tests.

## Design Overview

The new pricing path is split into explicit stages:

1. Normalize the item into structured search features.
2. Retrieve and score comparable candidates with a deterministic relaxation ladder.
3. Build a robust market anchor from the best candidate set.
4. Run a residual model that adjusts the anchor up or down.
5. Compute confidence from support, match quality, relaxation depth, and dispersion.
6. Return explanation data for value-driving affixes and what-if pricing views.

The comparables anchor is the primary estimate. The model is a correction layer, not the foundation.

## Stage 1: Item Normalization

### Route Selection Contract

Before retrieval, the serving and training path must assign a canonical route using the same deterministic route-selection function.

- The initial implementation should preserve the current v3 route families unless tests prove a route remap is required.
- Route selection runs before affix-importance ranking, bundle lookup, retrieval, priors, and evaluation.
- The chosen route must be persisted in training/eval artifacts so offline and online paths resolve the same bundle and priors.

### Inputs

- league
- parsed item payload from clipboard text
- base type, rarity, item state, item level, stack size
- explicit and implicit affixes, tier labels, numeric rolls, special states

### Behavior

- Normalize affixes into canonical mod keys.
- Preserve tier labels and numeric roll positions when available.
- Derive affix importance signals from market evidence rather than presentation order.
- Split affixes into:
  - core expensive or rare drivers,
  - medium-impact supporting affixes,
  - common or low-impact affixes.

### Deterministic Affix-Importance Contract

- Importance evidence is derived from recent training-example cohorts for the same `league + route + base_type + rarity + compatible item state`.
- Default evidence window is the latest `30d` of rows from `poe_trade.ml_v3_training_examples`.
- Per-affix importance score is based on a blend of:
  - presence lift versus cohort median price,
  - tier lift versus neighboring tiers when tier data exists,
  - scarcity of the affix within the cohort,
  - stability penalty when support is too thin.
- Tie-breakers for equal importance scores are:
  - larger absolute price lift,
  - lower cohort frequency,
  - stable canonical affix key sort.
- The same deterministic importance calculation must be usable in both offline training and online serving.
- If the default `30d` cohort is too thin to rank stably, the fallback order is:
  - same `league + route + base_type + rarity + compatible item state` over latest `90d`,
  - same `league + route + rarity + compatible item state` over latest `90d`,
  - route-family prior from persisted training artifacts.
- If all cohort fallbacks are still too thin, importance ordering falls back to stable route-family priors plus canonical affix-key ordering for ties.

### Item-State Taxonomy

The search and training path must normalize parsed fields into a deterministic item-state key.

- Core state dimensions:
  - `corrupted`: true or false
  - `fractured`: true or false
  - `synthesised`: true or false
  - `stacked`: true when stack size is materially relevant
  - `rarity`
  - route-family-specific state when present, such as cluster-jewel shape or fungible item family
- Material item-state compatibility means candidates must match all core state dimensions that materially affect value for that route family.
- Initial route-family rules:
  - fungible routes require same base type and same fungible family; stack size may differ but price normalization must compare per-unit value when appropriate
  - rare and unique equipment routes require exact match on corrupted, fractured, and synthesised flags
  - cluster-jewel routes require exact cluster-jewel topology fields when those fields are available in parsed features
- The normalized item-state key must be written into training/search artifacts so serving and offline evaluation use the same grouping.

### Required Output

- base search identity
- route family
- affix signature
- per-affix importance metadata
- per-affix tier and roll descriptors

## Stage 2: Comparable Retrieval

### Retrieval Principle

Search starts strict and relaxes only as needed. Relaxation must preserve rare and valuable affixes longer than common or weak ones.

### Search Order

1. Same base type, rarity, key item state, same important affix tiers, nearby roll values.
2. Same base type and important affixes, allow adjacent tiers on those affixes.
3. Drop low-value or common affixes while preserving important affixes and item state.
4. Broaden to base-type and item-state comparables with strong penalties for missing important affixes.

### Stage Contract

- Stage 1 effective support minimum: `8` candidates.
- Stage 2 effective support minimum: `12` candidates.
- Stage 3 effective support minimum: `18` candidates.
- Stage 4 effective support target: `24` candidates.
- Maximum returned candidates for anchor calculation: top `64` by final score.
- Important affixes are the top `min(4, affix_count)` by deterministic importance score.
- Low-value/common affix dropping begins only after all exact-tier and adjacent-tier searches fail to meet support minimum.
- `effective support` means the count of winning comparable rows with final non-zero anchor weight after score clamping and weighting.
- If Stage 4 has non-zero effective support but does not meet its target, serving should still use that Stage 4 set as the winning comparable set and mark the result low-confidence; only a zero-effective-support Stage 4 result moves to the prior-only path.

### Candidate Scoring

Each candidate gets a weighted similarity score using:

- exact base type and item-state compatibility,
- important-affix overlap,
- tier proximity on important affixes,
- roll closeness within matched tiers,
- preservation of rare and expensive affixes,
- recency,
- listing-quality and market-support signals.

### Deterministic Retrieval Contract

- Candidate universe starts from `league + route + base_type + rarity + compatible item state`.
- Default recency window is `14d` for active candidate selection, with older rows excluded unless an explicit late-stage broadening rule allows them.
- Candidate score is a weighted sum of:
  - base/item-state compatibility,
  - important-affix overlap,
  - tier proximity on important affixes,
  - normalized roll-distance on matched tiers,
  - rare-affix preservation bonus,
  - recency decay,
  - listing-quality support.
- Every stage must define exact required filters, penalties, and minimum support thresholds.
- Final ordering tie-breakers are:
  - higher candidate score,
  - newer observation,
  - stable identity key.
- The serving path should use either pre-materialized rows from `poe_trade.ml_v3_retrieval_candidates` or a deterministic rebuild path that produces the same ordering.

### Initial Scoring Weights

- base/item-state compatibility: `0.25`
- important-affix overlap: `0.30`
- tier proximity on important affixes: `0.15`
- normalized roll-distance on matched tiers: `0.10`
- rare-affix preservation bonus: `0.10`
- recency decay: `0.05`
- listing-quality support: `0.05`

Missing-important-affix penalties:

- missing highest-importance affix: `-0.35`
- missing second highest-importance affix: `-0.20`
- missing later important affix: `-0.10` each

Penalty application rules:

- Penalties apply to the pre-normalized similarity score.
- Final similarity score is clamped into `[0.0, 1.0]` before anchor weighting and confidence calculations.
- Weighted anchor statistics must never use negative weights.

Stage rules:

- Stage 1 requires exact match on base type, rarity, material item state, and important-affix tiers; roll-distance penalty allowed up to `0.15` total.
- Stage 2 keeps the same hard filters but allows adjacent tiers on important affixes with `-0.08` penalty per adjacent-tier step.
- Stage 3 preserves the top 2 important affixes as mandatory, then drops low-value/common affixes one at a time in ascending importance order.
- Stage 4 preserves base type, rarity, and material item state, but allows important-affix absence under the penalties above.

### Hard Rules

- Never mix incompatible core states such as corrupted/non-corrupted where the state materially affects price.
- Never discard expensive or rare affixes before weaker/common affixes at the same relaxation depth.
- If an affix is absent from the candidate but marked high-importance for the target item, apply a major penalty.

### Required Diagnostics

- relaxation stage reached
- candidate count before and after filtering
- which affixes were dropped to widen search
- which important affixes remained required
- final comparable support count

## Stage 3: Robust Anchor Estimation

### Objective

Convert the comparable set into a market-grounded estimate and credible interval.

### Core Logic

- Use the scored comparable set, not raw unweighted listings.
- Downweight stale, suspicious, or weakly matched rows.
- Use weighted robust statistics to compute:
  - anchor price,
  - low interval bound,
  - high interval bound,
  - support and dispersion metrics.

### Initial Estimator Contract

- Anchor = weighted median of candidate prices after filtering.
- Interval = weighted lower and upper quantiles after filtering.
- Candidate weight = final clamped candidate score only.
- Rows with large penalties from missing important affixes remain eligible only in late relaxation stages and contribute little to the anchor.

Recency decay and listing-quality support are incorporated once in candidate scoring and must not be multiplied again during anchor estimation.

### Last-Resort Estimate Policy

- The system should still return an estimate when exact support is poor.
- The estimate may come from late-stage relaxed comparables.
- Confidence must drop sharply when the system relies on late-stage or weakly matched candidates.
- The old route median fallback should be removed from the public serving path once the relaxed comparable ladder can produce a final low-confidence estimate.
- If Stage 4 still yields zero compatible comparables, the system should build a last-resort anchor from a deterministic route-family prior persisted in training artifacts for the same `league + route + rarity + material item state`.
- This zero-comparable path must set numeric `confidence` to `0.10`, set `estimateTrust` to `low`, mark the degradation reason explicitly, and set `priceRecommendationEligible = false`.
- If that route-family prior is unavailable, the system should fall back to a deterministic league-level base-type prior, and if that is unavailable, to a global route-family prior stored in the trained artifact. This final path still returns an estimate but must carry the lowest confidence bucket and an explicit warning.

## Stage 4: Residual Model Adjustment

### Objective

Learn how much to move the comparable anchor up or down when the comparable set does not fully capture the target item's value.

### Training Target

- Predict residual delta from anchor to observed price target, not absolute price from scratch.
- Fair-value observed target remains the current primary observed price target used by the v3 training flow.
- Fast-sale observed target uses the current `target_fast_sale_24h_price` training label from `poe_trade.ml_v3_training_examples`.
- `anchor_fast_sale` is derived from the same winning comparable set as fair value, but using the comparable rows' fast-sale target when available; if comparable fast-sale labels are sparse, use the fair-value anchor multiplied by the route-calibrated fast-sale ratio learned from the training cohort.

### Model Inputs

- anchor price and anchor interval statistics,
- support count and match-quality metrics,
- relaxation stage,
- per-affix importance features,
- tier and roll features for important affixes,
- item-level and route-family features,
- missing-important-affix indicators for the chosen comparable set.

### Output

- residual adjustment amount,
- fair-value residual adjustment,
- fast-sale residual adjustment,
- sale-probability estimate or calibrated sale-probability adjustment,
- calibrated confidence features for downstream policy.

### Guardrails

- Residual adjustment must be capped relative to anchor confidence and support.
- The weaker the comparable set, the less freedom the residual model has to move the anchor aggressively.
- If the comparable set is very weak, the final estimate should stay close to the anchor and surface low confidence.

### Deterministic Residual Policy

- Residual target is `observed_price - anchor_price` for fair value and `observed_fast_sale - anchor_fast_sale` for fast sale.
- Residual cap for fair value is:
  - `+/- 8%` of anchor when confidence `< 0.35`
  - `+/- 15%` of anchor when confidence is `0.35` to `< 0.60`
  - `+/- 25%` of anchor when confidence `>= 0.60`
- Residual cap for fast sale is:
  - `+/- 6%` of anchor when confidence `< 0.35`
  - `+/- 12%` of anchor when confidence is `0.35` to `< 0.60`
  - `+/- 20%` of anchor when confidence `>= 0.60`
- If the chosen comparable stage is Stage 4, residual output must be shrunk by `50%` before capping.
- If the chosen path is Stage 0 prior-only fallback, residual adjustment must be skipped and the prior anchor becomes the final estimate.

### Dual-Output Contract

- The hybrid path must preserve the current public dual-price behavior:
  - `fair_value_p50` as the best-value estimate,
  - `fast_sale_24h_price` as the faster-exit estimate,
  - `sale_probability_24h` and `sale_probability_percent`.
- Both fair-value and fast-sale outputs should be anchored in the same comparable search, then adjusted by separate residual heads or a shared model with separate outputs.
- The fast-sale output is not optional in the shipped contract and must remain part of training, evaluation, serving, and API normalization.

## Stage 5: Confidence and Quality Policy

### Confidence Inputs

- comparable support count,
- weighted match score,
- relaxation depth,
- price dispersion,
- residual magnitude relative to anchor,
- route-family reliability.

### Output Contract

- `confidence`
- `estimateTrust`
- `estimateWarning`
- `priceRecommendationEligible`

### Policy

- Always emit a price estimate.
- Mark low-confidence estimates clearly when support is thin or relaxation is deep.
- Recommendation eligibility should depend on both confidence and search-quality diagnostics, not confidence alone.

### Deterministic Confidence Contract

- Confidence score is computed as:
  - `0.30 * support_score`
  - `+ 0.25 * match_score`
  - `+ 0.15 * dispersion_score`
  - `+ 0.10 * stage_score`
  - `+ 0.10 * route_reliability_score`
  - `+ 0.10 * residual_stability_score`
- Component definitions:
  - `weighted_candidate_score = weighted average of final clamped similarity scores across the winning comparable set, using the same non-negative candidate weights used for anchor estimation`
  - `support_score = min(candidate_count, 32) / 32`
  - `match_score = max(0, min(1, weighted_candidate_score))`
  - `dispersion_score = max(0, 1 - min(interval_width / max(anchor_price, 0.1), 1.5) / 1.5)`
  - `stage_score = 1.0` for Stage 1, `0.8` for Stage 2, `0.55` for Stage 3, `0.25` for Stage 4
  - `route_reliability_score = persisted route-family calibration score in [0, 1] from offline evaluation`
  - `residual_stability_score = max(0, 1 - min(abs(residual_adjustment) / max(anchor_price, 0.1), 0.30) / 0.30)`
- Trust buckets:
  - `high` when confidence `>= 0.70`
  - `normal` when confidence `>= 0.45` and `< 0.70`
  - `low` when confidence `< 0.45`
- `estimateTrust` keeps the current compatibility-oriented value set `high | normal | low` during cutover.
- `priceRecommendationEligible = true` only when:
  - confidence `>= 0.40`, and
  - final stage is not Stage 4, and
  - at least one important affix remains matched in the winning comparable set.
- `estimateWarning` should explicitly describe the primary degradation reason in this priority order:
  - missing important affixes,
  - deep relaxation stage,
  - high price dispersion,
  - low candidate support.

## Stage 6: Explanation Payload

### User-Facing Goal

Show why the item is priced this way and which mods matter.

### Required Explanation Fields

- top positive value-driving affixes,
- top negative or missing value-driving affixes,
- tier and roll commentary for important affixes,
- comparable examples that most influenced the anchor,
- search stage and dropped-affix summary,
- scenario prices for:
  - current item,
  - weaker roll on an important affix,
  - stronger roll on an important affix,
  - dropping one or more weak/common affixes.

### Scenario Generation Contract

- Scenario prices are generated from a lightweight deterministic rerun of the same retrieval, anchor, residual, and confidence logic using a modified in-memory item payload.
- The initial serving contract should cap scenarios to at most `3` alternates per request:
  - one weaker-roll scenario,
  - one stronger-roll scenario,
  - one dropped-weak-affix scenario.
- Scenario generation reuses the already loaded bundle/config and does not require a second API round-trip.
- If scenario generation exceeds the serving budget, the backend may omit lower-priority scenarios but must still return the base estimate and explanation payload.
- Stage 0 prior-only fallback may omit alternate scenarios entirely; in that case the response should return only the `current` scenario and explain that no comparable-backed what-if analysis was available.

### Frontend Behavior

- Price check should show value drivers and comparable-support context.
- Low-confidence results should include scenario pricing and a plain-language reason for uncertainty.
- The frontend should stop depending on a second legacy-style predict call just to enrich trust metadata.
- The current two-call merge in the price-check UI should be removed. Any metadata worth keeping must come from the unified hybrid prediction response.
- `shadowComparison` is intentionally dropped unless there is a real hybrid-era shadow deployment that produces a meaningful candidate-vs-incumbent comparison.
- `servingModelVersion` may remain if it reflects the actual promoted hybrid artifact version.

### Canonical Explanation Shape

The canonical response should expose these camelCase objects:

- `searchDiagnostics`
  - `stage`: `0 | 1 | 2 | 3 | 4`
  - `candidateCount`: number
  - `matchedImportantAffixes`: string[]
  - `droppedAffixes`: string[]
  - `degradationReason`: string | null

Where `stage = 0` represents the prior-only no-comparables path.
- `comparablesSummary`
  - `anchorPrice`: number
  - `anchorLow`: number | null
  - `anchorHigh`: number | null
  - `supportCount`: number
  - `topComparables`: array of rows with `identityKey`, `price`, `currency`, `score`, `matchedAffixes`, `missingAffixes`, `observedAt`
- `valueDrivers`
  - `positive`: array of `{ affixKey, label, impact, reason }`
  - `negative`: array of `{ affixKey, label, impact, reason }`
- `scenarioPrices`
  - `current`: `{ fairValue, fastSale, confidence }`
  - `weakerRolls`: array of `{ label, fairValue, fastSale }`
  - `strongerRolls`: array of `{ label, fairValue, fastSale }`
  - `withoutWeakAffixes`: array of `{ label, fairValue, fastSale }`

If snake_case compatibility is needed during cutover, backend normalization should emit both forms for the new objects, but the frontend should treat camelCase as canonical.

## API Contract Changes

The public prediction response should include:

- final fair-value estimate and interval,
- final fast-sale estimate,
- sale probability outputs,
- comparable support and relaxation metadata,
- explanation payload,
- scenario pricing payload,
- confidence and recommendation policy outputs,
- optional serving model/version metadata only if it reflects the new hybrid artifacts.

Backward-compatibility fields may be preserved temporarily, but the canonical frontend contract should move to the hybrid explanation shape.

The canonical response should remain compatible with the current ML/UI surfaces by continuing to populate the current fair-value, fast-sale, sale-probability, confidence, and recommendation fields while adding hybrid explanation metadata.

Compatibility fields that must continue to be populated during cutover:

- `predictedValue`
- `interval.p10` and `interval.p90`
- `fair_value_p10`, `fair_value_p50`, `fair_value_p90`
- `fast_sale_24h_price`
- `sale_probability_24h` and `sale_probability_percent`
- `confidence` and `confidence_percent`
- `prediction_source`
- `fallback_reason` or its hybrid successor semantics for degraded search
- `ml_predicted`
- `price_recommendation_eligible`
- `estimateTrust`
- `estimateWarning`

During cutover, `prediction_source` should distinguish the hybrid path from the current direct-model path, and degraded-search behavior should replace the old median-fallback semantics rather than silently reusing them.

## Data and Storage Changes

The training and serving stores should support:

- normalized comparable-search keys,
- comparable candidate materialization or deterministic rebuild,
- affix importance features,
- anchor diagnostics for offline evaluation,
- residual-model training artifacts,
- explanation/scenario metadata needed at serve time.

The storage contract must also capture enough information to reproduce serving-time search and explanation behavior offline, including:

- chosen relaxation stage,
- dropped-affix sequence,
- winning comparable set,
- anchor statistics,
- residual outputs for fair value and fast sale.

`poe_trade.ml_v3_retrieval_candidates` should either become the real candidate source for the serving path or be replaced by a clearer, actively used store.

### Artifact Layout

The initial hybrid artifact layout should remain compatible with the current per-route registry and trainer runtime.

- Canonical runtime contract: `Path(model_dir) / "v3" / league / route / "bundle.joblib"`
- Example: if `--model-dir artifacts/ml/mirage_v3`, the bundle path remains `artifacts/ml/mirage_v3/v3/<league>/<route>/bundle.joblib`.
- Bundle contents:
  - search configuration and scoring weights
  - normalized item-state rules for the route
  - affix-importance metadata or references required for deterministic serving
  - residual model for fair value
  - residual model for fast sale
  - sale-probability model or calibrator
  - confidence calibration config
- ClickHouse stores:
  - keep `poe_trade.ml_v3_training_examples`
  - keep `poe_trade.ml_v3_retrieval_candidates` as the candidate/search store unless implementation proves a replacement is cleaner
  - keep current v3 registry/eval/prediction tables, extending them only as needed for hybrid diagnostics

This keeps deployment compatible with the current per-route model registry and automation surfaces while changing the contents and serving logic of each route bundle.

## Cutover Rules

- The live predict path should switch to the hybrid estimator only after training, serving, API, and tests agree on the same contract.
- Hybrid training must continue to register promoted artifacts through the current v3 model registry/runtime surfaces so that `poe_trade/services/ml_trainer.py`, `poe_trade/api/ml.py`, and automation endpoints keep working during the transition.
- Hybrid evaluation must write into the existing v3 evaluation and promotion flow so promotion gates compare current live behavior against the new hybrid artifacts instead of inventing a parallel control plane.
- Legacy helper code in `poe_trade/ml/workflows.py` should be removed only after the new hybrid path fully replaces the old behavior.
- Cleanup migrations that drop old ML tables should not race ahead of runtime code that still depends on them.

## Testing Requirements

### Unit Tests

- affix importance ranking
- search relaxation order
- dropped-affix prioritization
- candidate scoring and penalties
- robust anchor calculation
- residual adjustment caps
- confidence degradation with weaker support
- explanation payload content
- scenario-price generation

### Integration Tests

- CLI and service flow for hybrid training and serving
- API predict-one contract including explanation fields
- price-check frontend consumption of the unified response
- migration safety for legacy cleanup after cutover

### Evaluation Requirements

- compare anchor-only, model-only, and hybrid predictions offline
- verify that hybrid improves over the current live path for target cohorts
- score exact serving behavior, not proxy metrics only
- verify both fair-value and fast-sale outputs through the same promotion/eval surfaces already used by the v3 trainer and automation APIs

## Success Criteria

The work is successful when:

- the live pricing path uses comparables-first anchoring instead of direct route-local prediction,
- rare and expensive affixes are preserved longer during search relaxation,
- every prediction includes honest confidence and explanation data,
- low-support items still receive an estimate without pretending certainty,
- the frontend can show users what drives price and how key affixes change value,
- obsolete legacy pricing code can be removed without breaking the public contract.
