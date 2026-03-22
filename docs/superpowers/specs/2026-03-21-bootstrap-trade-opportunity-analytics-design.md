# Bootstrap Trade Opportunity Analytics Design

## Goal

Improve the backend opportunity engine so it surfaces realistic, feasible, high-value trade opportunities for a bootstrap flipper, ranks them by return per user operation, and exposes enough API detail for the frontend to tell the user exactly what to do.

## Problem Statement

The current scanner and analytics surface already expose trade recommendations through `poe_trade.scanner_recommendations` and `/api/v1/ops/scanner/recommendations`, but the published contract is still too shallow for the user goal.

Today the system mainly exposes:

- raw opportunity descriptors such as `buyPlan`, `transformPlan`, and `exitPlan`,
- headline metrics such as `expectedProfitChaos`, `expectedRoi`, and `expectedProfitPerMinuteChaos`,
- lightweight evidence fields such as liquidity, freshness, and ML influence extracted from `evidence_snapshot`.

That is useful for operator visibility, but it does not yet answer the actual trading question well enough:

- which opportunities are realistic for a low-bank player,
- which trades are worth the number of searches, whispers, buys, listings, and repricing touches they require,
- which advanced plays are still good enough to justify their extra friction,
- what exact steps the user should take to execute the trade.

The current scanner ranking is still too close to raw profit, ROI, and recency. That can overvalue cumbersome plays that look good on paper but are weak once manual effort, fill friction, market depth, or exit difficulty are included.

## User-Facing Outcome

From the opportunities surface, the user should be able to:

1. see opportunities ranked by realistic return per operation rather than only raw upside,
2. focus on opportunities that are executable for a bootstrap flipper with limited capital,
3. still see advanced or slower plays when their payoff is strong enough to justify the work,
4. understand why a recommendation ranks highly and what risks make it weaker,
5. follow a structured execution brief that explains exactly what to search, buy, transform, list, and when to stop.

## Non-Goals

- building a full auto-trading or messaging bot,
- integrating a live whisper sender or external trade execution service,
- replacing the existing opportunities route with an unrelated new product surface,
- removing legacy recommendation fields that current frontend code already consumes,
- making destructive schema changes to current scanner tables.

## Design Overview

The design keeps the current scanner pipeline centered on `poe_trade/strategy/scanner.py`, `poe_trade/strategy/policy.py`, `poe_trade.scanner_recommendations`, and `/api/v1/ops/scanner/recommendations`, but upgrades the opportunity model in three ways.

1. Recommendation ranking moves from mostly raw upside toward net expected profit per operation.
2. Strategy evidence is expanded so the backend can estimate execution friction, capital fit, and realism.
3. The API contract grows from a lightweight recommendation row into a structured execution brief with explicit user instructions and diagnostics.

The design also adds a persisted decision log for accepted and rejected candidates so scanner analytics can explain why opportunities surfaced or were filtered out.

This preserves the existing architecture and frontend route structure while making the opportunities feature much more useful as a real trading assistant.

## Existing Foundations To Reuse

- `poe_trade/strategy/scanner.py` already fetches candidate rows, evaluates them, and writes scanner recommendations and alerts.
- `poe_trade/strategy/policy.py` already applies minima, cooldown, journal gates, and dedupe.
- `poe_trade/strategy/registry.py` and `strategies/*/strategy.toml` already define per-strategy metadata and thresholds.
- `poe_trade/sql/strategy/*/candidate.sql` already acts as the strategy-specific source of evidence for each opportunity.
- `poe_trade/api/ops.py` already shapes recommendation payloads and dashboard top opportunities.
- `frontend/src/types/api.ts` and `frontend/src/components/tabs/OpportunitiesTab.tsx` already consume and render scanner recommendations.

## Architecture

### 1. Opportunity Scoring Model

The recommendation engine should adopt an operations-aware scoring model.

The primary ranking metric should become `expected_profit_per_operation_chaos`, defined as expected net trade profit divided by the number of required user operations.

An operation should be modeled explicitly. At minimum the backend should estimate:

- searches,
- whisper batches,
- completed buys,
- transform steps,
- listing steps,
- repricing touches,
- final sell completion.

Each candidate should be evaluated through three layers:

1. `gross upside` - expected profit, ROI, and capital efficiency,
2. `execution cost` - expected operations, whispers, sourcing delay, and exit delay,
3. `reality adjustment` - confidence, sample depth, freshness, liquidity, spread stability, and strategy-specific risk.

The final ranking should favor the best realistic trade per unit of human effort, not simply the largest nominal spread.

For the initial bootstrap-flipper profile, the design should use concrete defaults rather than leaving the core ranking inputs undefined.

Recommended initial defaults:

- bootstrap capital ceiling: `100c` preferred, with candidates above `150c` rejected for the default feed,
- one search action per distinct market query,
- one whisper batch per `3` expected seller contacts,
- one buy action per completed seller fill,
- one list action per sell listing wave,
- one repricing action when the strategy evidence indicates a likely refresh or relist touch,
- one transform action per explicit crafting, assembly, reroll, or packaging step.

These heuristics should be configurable later, but the first implementation needs stable defaults so ranking and hard gates are deterministic.

To preserve the full strategy spectrum, this capital ceiling should be profile-aware rather than globally destructive. The default opportunities feed should use the bootstrap profile, while analytics and a future request parameter such as `profile=mid_bank|rich_operator` can expose higher-capital opportunities without weakening the default bootstrap experience.

### 2. Hard Feasibility Gates

Before ranking, the backend should reject candidates that fail basic realism checks.

Recommended hard gates:

- stale or incomplete market evidence,
- insufficient sample depth,
- weak liquidity or poor turnover proxy,
- estimated operations too high for the projected profit,
- estimated whisper load too high for a bootstrap player,
- required capital above the bootstrap-friendly ceiling,
- advanced manual workflows that do not clear a materially higher payoff bar.

This keeps the full strategy spectrum available in principle, but prevents low-quality paper edges from crowding out actionable flips.

Recommended bootstrap defaults:

- reject when `requiredCapitalChaos > 150`,
- reject when `estimatedOperations > 8` unless complexity is `advanced_manual` and profit-per-operation is above the advanced override threshold,
- reject when `estimatedWhispers > 12`,
- reject when freshness exceeds the strategy-specific market tolerance,
- reject when sample depth or liquidity falls below the per-strategy floor.

These strategy-specific gates should live in strategy metadata, not in scattered code constants.

Recommended additive `strategy.toml` params:

- `max_staleness_minutes`,
- `min_liquidity_score`,
- `max_estimated_whispers`,
- `max_estimated_operations`,
- `advanced_override_profit_per_operation_chaos`.

`poe_trade/strategy/registry.py` should load these values with safe defaults so every strategy resolves to a deterministic gate profile.

### 3. Strategy Complexity Tiers

All strategies should still be allowed to contribute candidates, but each opportunity should be classified into a complexity tier.

Recommended tiers:

- `direct_flip` - buy and resell with little or no transformation,
- `light_transform` - a small number of extra steps such as set assembly or single reroll workflows,
- `advanced_manual` - rarer or more manual strategies such as crafting-heavy or journal-dependent plays.

The complexity tier should affect both ranking and filtering. Advanced plays should remain visible only when their operation-adjusted payoff is clearly superior.

### 4. Candidate Evidence Contract

The current candidate SQL shape is too sparse for realistic opportunity ranking. Strategy candidate outputs should be expanded so each row can support execution-cost estimation.

Recommended evidence additions at the candidate layer:

- required capital or target buy-in,
- target quantity or preferred bulk size,
- market depth and listing depth,
- sell-velocity or liquidity proxy,
- expected sourcing difficulty,
- expected resale difficulty,
- expected search count,
- expected whisper count,
- expected transform count,
- explicit complexity tier,
- strategy-specific risk markers.

These values do not all need dedicated table columns immediately. They can first be carried in `evidence_snapshot`, then promoted to additive nullable columns where query performance or API clarity justifies it.

Because the current candidate SQL files are heterogeneous, the design should not rely on every strategy producing identical raw columns directly from SQL. Instead, implementation should introduce a normalized evidence adapter layer between source rows and final opportunity scoring.

Recommended normalized adapter contract:

- `market_query`,
- `target_item`,
- `required_capital_chaos`,
- `target_quantity`,
- `preferred_bulk_size`,
- `market_depth`,
- `liquidity_score`,
- `competition_score`,
- `estimated_searches`,
- `estimated_whispers`,
- `estimated_completed_buys`,
- `estimated_transforms`,
- `estimated_listing_actions`,
- `estimated_reprice_actions`,
- `estimated_exit_actions`,
- `complexity_tier`,
- `strategy_risk_flags`.

Each strategy should map its source row into this contract in Python, with SQL remaining responsible for domain-specific market facts and Python responsible for consistent opportunity semantics.

### 5. Scanner Evaluation Flow

The current scanner flow should be refactored so there is a clearer separation between:

- raw strategy candidate discovery,
- policy eligibility checks,
- opportunity realism scoring,
- API payload shaping.

`poe_trade/strategy/policy.py` should continue to own generic eligibility rules such as minima, dedupe, cooldown, and journal requirements.

However, the current dedupe logic ranks winners by raw profit, ROI, confidence, and sample depth. That is incompatible with an operation-aware engine. Dedupe should therefore move after opportunity scoring, or it should be updated to use the new final rank tuple so low-friction winners are not discarded before scoring completes.

Recommended evaluation order:

1. normalize the source row into the shared evidence adapter contract,
2. compute operation-aware derived metrics and preliminary rank fields,
3. apply source-row validation, policy minima, and bootstrap feasibility gates,
4. dedupe remaining candidates on semantic key using the final operation-aware rank tuple,
5. apply journal and cooldown checks to the dedupe winner for the semantic key,
6. persist exactly one terminal decision reason per candidate.

Reason precedence should be explicit:

- row validation failures win first,
- minima and bootstrap-feasibility failures come next,
- `dedupe_loser` applies to non-winning candidates that survived earlier gates,
- journal and cooldown are evaluated on the surviving representative candidate for the semantic key.

This keeps duplicate suppression aligned with the existing alert model, where only one effective candidate per semantic key should be able to generate a published recommendation or alert.

Recommended terminal reason taxonomy:

- `accepted`,
- `invalid_source_row`,
- `league_mismatch`,
- `below_min_expected_profit_chaos`,
- `below_min_expected_roi`,
- `below_min_confidence`,
- `below_min_sample_count`,
- `below_min_liquidity_score`,
- `stale_market`,
- `over_capital_ceiling`,
- `over_operations_budget`,
- `over_whisper_budget`,
- `journal_state_required`,
- `cooldown_active`,
- `dedupe_loser`.

Analytics should aggregate these terminal reasons directly so counts stay stable and interpretable.

The current scanner implementation also needs row-level isolation. A malformed candidate source row should no longer fail the whole strategy pack during `candidate_from_source_row` construction. Instead, source-row parsing should happen in a per-row loop that logs the row failure, persists an `invalid_source_row` decision when possible, and continues evaluating the rest of the pack.

A new opportunity scoring layer should then calculate:

- `estimated_operations`,
- `estimated_searches`,
- `estimated_whispers`,
- `estimated_time_to_acquire_minutes`,
- `estimated_time_to_exit_minutes`,
- `estimated_total_cycle_minutes`,
- `expected_profit_per_operation_chaos`,
- `feasibility_score`,
- `risk_score`,
- `competition_score`.

Only then should the candidate be inserted into `poe_trade.scanner_recommendations`.

The scanner should also persist a decision record for every evaluated candidate, including rejected ones.

Recommended new additive table: `poe_trade.scanner_candidate_decisions`.

Minimum fields:

- scanner run and strategy identity,
- league and semantic key,
- accepted boolean,
- rejection reason or acceptance state,
- complexity tier,
- required capital,
- estimated operations and whispers,
- expected profit, profit per operation, and feasibility score,
- evidence snapshot,
- recorded timestamp.

Recommended ClickHouse shape:

- engine: `MergeTree()`,
- partition by `toYYYYMMDD(recorded_at)`,
- order by `(strategy_id, accepted, scanner_run_id, recorded_at)`,
- retention target: short-lived operational analytics window such as `14` to `30` days,
- explicit `GRANT SELECT ON poe_trade.scanner_candidate_decisions TO poe_api_reader`.

`analytics_scanner` and the proposed opportunity diagnostics endpoint should read from this decision table rather than attempting to infer rejected counts from published recommendation rows.

### 6. Strategy Pack Review and Pruning

Current strategy packs should be reviewed under the new realism model.

Expected keep-or-improve set:

- `bulk_essence`,
- `bulk_fossils`,
- `fragment_sets`,
- `cx_market_making`,
- other bulk or spread strategies that can expose good depth and execution evidence.

Expected rework-or-demote set:

- `advanced_rare_finish`,
- `cluster_basic`,
- `flask_basic`,
- `rog_basic`,
- `corruption_ev`,
- other manual or variance-heavy strategies that currently lack strong feasibility signals.

If a strategy cannot provide enough evidence to estimate realistic execution for a bootstrap flipper, it should be disabled, filtered more aggressively, or ranked far below straightforward flips.

## API Design

### `GET /api/v1/ops/scanner/recommendations`

The route should remain the primary opportunity feed.

The existing payload shape should remain backward-compatible, but new opportunity fields should be added additively.

The default sort behavior should change with the new ranking model.

Recommended contract changes:

- backend default sort becomes `expected_profit_per_operation_chaos`,
- frontend opportunities tab default sort should match that backend default,
- dashboard `topOpportunities` should also request `expected_profit_per_operation_chaos`,
- existing `expected_profit_chaos` and `expected_profit_per_minute_chaos` sorts should remain available as secondary options.

Recommended new top-level fields per recommendation:

- `opportunityType`,
- `complexityTier`,
- `requiredCapitalChaos`,
- `estimatedOperations`,
- `estimatedSearches`,
- `estimatedWhispers`,
- `estimatedTimeToAcquireMinutes`,
- `estimatedTimeToExitMinutes`,
- `estimatedTotalCycleMinutes`,
- `expectedProfitPerOperationChaos`,
- `feasibilityScore`,
- `riskScore`,
- `competitionScore`,
- `freshnessMinutes`,
- `whyNow`,
- `warnings`.

Recommended structured nested objects:

- `executionPlan`
  - `searchQuery`,
  - `targetItem`,
  - `buySteps`,
  - `transformSteps`,
  - `sellSteps`,
  - `maxBuyPrice`,
  - `targetListPrice`,
  - `minimumAcceptableExit`,
  - `targetQuantity`,
  - `preferredBulkSize`,
  - `stopConditions`
- `evidence`
  - `sampleCount`,
  - `marketDepth`,
  - `liquidityScore`,
  - `competitionScore`,
  - `spreadObserved`,
  - `freshnessMinutes`,
  - `strategySource`,
  - `mlInfluenceScore`,
  - `mlInfluenceReason`

The existing fields such as `buyPlan`, `transformPlan`, `exitPlan`, `expectedProfitChaos`, `expectedRoi`, and `expectedProfitPerMinuteChaos` should stay so the frontend can migrate incrementally.

### `GET /api/v1/ops/analytics/scanner`

The current `analytics_scanner` payload is only a recommendation count grouped by strategy. That is too shallow for opportunity tuning.

It should evolve into an operator-facing diagnostics response that explains:

- candidates discovered by strategy,
- candidates rejected by gate and reason,
- surviving opportunities by complexity tier,
- top strategies by profit per operation,
- how many opportunities were filtered out for bootstrap feasibility reasons.

This endpoint should help developers and operators understand why the engine is surfacing the opportunities it surfaces.

### `GET /api/v1/ops/analytics/opportunities`

Add a new analytics endpoint for opportunity diagnostics and ranking transparency.

Recommended response sections:

- summary counts by complexity tier,
- distributions for profit per operation, total profit, ROI, liquidity, and feasibility,
- top rejected-reason counts,
- top opportunities by rank score,
- strategy contribution and suppression details.

This endpoint is for analysis and product tuning, not the main feed consumed by the opportunities tab.

## Data Contract and Schema Evolution

Schema changes should remain additive.

Recommended approach:

- keep `poe_trade.scanner_recommendations` as the published recommendation table,
- add `poe_trade.scanner_candidate_decisions` for accepted and rejected candidate diagnostics,
- add nullable columns only for fields that materially improve filtering, sorting, or downstream query clarity,
- continue to store richer per-row evidence in `evidence_snapshot`,
- preserve legacy-row readability in `scanner_recommendations_payload`.

Mixed-schema deployments need an explicit compatibility plan.

Recommended rollout safety rules:

- add new columns and the decision table in migrations before code depends on them,
- keep insert fallback behavior for newly added recommendation columns the same way current metadata-column fallback works,
- derive missing additive fields from `evidence_snapshot` when legacy rows are read,
- avoid making new analytics routes depend on columns that may be absent during rolling deploys.

Recommended staged compatibility plan:

1. `schema-first`: add nullable recommendation columns plus `scanner_candidate_decisions`, grants, and any read-side views; do not change API defaults yet,
2. `writer-compatible`: deploy scanner code that writes new fields when columns exist and falls back cleanly when they do not,
3. `reader-compatible`: deploy API code that can read the new fields when present, derive them from `evidence_snapshot` when possible, and fall back to legacy sort fields when the new metric is unavailable,
4. `default-switch`: only after migrations and both read/write paths are live, change the route and frontend defaults to `expected_profit_per_operation_chaos`.

Until phase `4`, the API should keep `expected_profit_per_minute_chaos` as the default dashboard ranking fallback and should reject an explicit `expected_profit_per_operation_chaos` sort only if neither the direct column nor a safe derived expression is available.

This avoids destructive migrations while still allowing richer analytics and frontend guidance.

## Frontend Implications

The frontend does not need a new primary route. `frontend/src/components/tabs/OpportunitiesTab.tsx` can evolve in place.

Recommended UI behavior once the new contract exists:

- keep the current card or list presentation,
- add realism-oriented fields such as operation count, whispers, capital, and feasibility,
- render a structured execution brief so the user sees exactly what to search and how to exit,
- show warnings for slow, thin, or high-friction markets,
- keep backward compatibility while new fields are adopted progressively.

The dashboard can keep using `topOpportunities`, but those rows should improve automatically once the ranking engine becomes operations-aware.

## Error Handling and Degraded Behavior

The opportunities API should remain conservative when evidence is missing.

Recommended behavior:

- if a candidate lacks required execution evidence, either reject it or assign a strong feasibility penalty,
- if derived metrics cannot be computed for legacy rows, keep those fields nullable rather than fabricating values,
- if analytics detail queries fail, preserve the main recommendations route when possible,
- sanitize backend failures through the existing API error mapping.

This keeps the user from acting on fake precision.

## Testing Strategy

Testing should verify both ranking correctness and contract safety.

### Backend tests

- unit tests for operation-aware scoring,
- unit tests for bootstrap feasibility gates,
- unit tests showing low-friction trades outrank bigger but cumbersome trades,
- unit tests for advanced-play penalties,
- unit tests for legacy-row compatibility,
- unit tests for new API payload fields and nullable behavior,
- unit tests for analytics rejection-reason summaries.

### API tests

- route tests for additive recommendation fields,
- route tests for new analytics endpoint shape,
- route tests for sort and filter behavior based on operation-aware metrics,
- route tests that preserve existing contract fields.

### Strategy tests

- targeted tests for strategy evidence extraction from candidate rows,
- tests that disable or demote strategies lacking realistic execution evidence,
- tests that confirm bootstrap-friendly strategies remain highly ranked when all else is equal.

## Rollout Plan

Recommended rollout order:

1. add additive schema support for new recommendation fields plus `scanner_candidate_decisions`,
2. add the normalized evidence adapter layer and operation-aware scoring model,
3. move dedupe to the final score tuple and persist full candidate decisions,
4. enrich `scanner_recommendations_payload` with additive fields and new default sort behavior,
5. upgrade scanner analytics and add opportunity diagnostics,
6. review and re-tune every current strategy under the new scoring model,
7. update the frontend to render the new execution brief and realism context.

This sequencing keeps the public API stable while the opportunity engine becomes more useful.

## Scope Checklist For Strategy Review

The implementation plan should review every live strategy candidate source, not only the most obvious bulk and manual packs.

At minimum the review set should include:

- `bulk_essence`,
- `bulk_fossils`,
- `fragment_sets`,
- `cx_market_making`,
- `scarab_reroll`,
- `map_logbook_packages`,
- `fossil_scarcity`,
- `dump_tab_reprice`,
- `high_dim_jewels`,
- `advanced_rare_finish`,
- `cluster_basic`,
- `flask_basic`,
- `rog_basic`,
- `corruption_ev`.

## Remaining Planning Decisions

These are still worth deciding during implementation planning, but they no longer block the design itself:

- which additive metrics deserve first-class columns immediately versus remaining in `evidence_snapshot`,
- whether advanced-manual opportunities should be hidden by default in the frontend or merely ranked lower,
- whether bootstrap-profile parameters should later become operator-configurable per league or environment.
