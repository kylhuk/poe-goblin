# Bootstrap Trade Opportunity Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an operation-aware opportunity engine that ranks realistic bootstrap-friendly trade opportunities, persists accepted/rejected decision diagnostics, and exposes structured execution guidance to the frontend.

**Architecture:** Keep the existing scanner pipeline and `/api/v1/ops/scanner/recommendations` route, but insert a focused opportunity-scoring layer between candidate discovery and published recommendations. Roll the change out in four stages: schema-first, writer-compatible scanner changes, reader-compatible API enrichment, then the final default-switch to operation-aware ranking once both sides are live. Treat higher-capital read profiles as a follow-up; this plan ships the bootstrap feed, legacy-safe analytics, and decision visibility first.

**Tech Stack:** Python 3.11, ClickHouse migrations, existing `poe_trade` strategy/API modules, pytest, React, TypeScript, Vitest.

---

## Implementation notes

- Apply `@superpowers:test-driven-development` discipline to every task: write the failing test first, run it, implement the minimum change, rerun the focused test, then commit.
- Before any "done" claim, use `@superpowers:verification-before-completion` and capture the exact command output.
- Keep schema evolution additive. Do not remove legacy recommendation fields or break legacy `scanner_recommendations` rows.
- Keep the default feed bootstrap-focused. Use analytics to explain why higher-capital or high-friction plays were rejected; do not add a `profile` read path in this implementation plan.

## File map

- Create: `schema/migrations/0057_scanner_opportunity_analytics_v1.sql` - additive recommendation columns plus `scanner_candidate_decisions` table/grants.
- Create: `poe_trade/strategy/opportunity.py` - normalized evidence adapter, operation heuristics, score helpers, terminal reason helpers.
- Modify: `poe_trade/config/constants.py` - bootstrap defaults now; recommendation contract version bump during the final default-switch task.
- Modify: `poe_trade/strategy/registry.py` - load new strategy metadata params with safe defaults.
- Modify: `poe_trade/strategy/policy.py` - align dedupe/evaluation flow with operation-aware ranking and explicit terminal reasons.
- Modify: `poe_trade/strategy/scanner.py` - row-level source isolation, opportunity scoring, decision-log persistence, mixed-schema insert fallback.
- Modify: `poe_trade/api/ops.py` - recommendation payload enrichment, staged sort handling, dashboard ranking, analytics queries.
- Modify: `poe_trade/api/app.py` - request parsing for new sort inputs and analytics kind routing.
- Modify: `strategies/advanced_rare_finish/strategy.toml` - advanced-manual gating defaults.
- Modify: `strategies/bulk_essence/strategy.toml` - bootstrap-friendly thresholds and staleness/whisper caps.
- Modify: `strategies/bulk_fossils/strategy.toml` - bootstrap-friendly thresholds and staleness/whisper caps.
- Modify: `strategies/cluster_basic/strategy.toml` - complexity and feasibility thresholds.
- Modify: `strategies/corruption_ev/strategy.toml` - advanced-manual gating defaults.
- Modify: `strategies/cx_market_making/strategy.toml` - direct-flip thresholds and bootstrap defaults.
- Modify: `strategies/dump_tab_reprice/strategy.toml` - repricing-heavy thresholds.
- Modify: `strategies/flask_basic/strategy.toml` - complexity and feasibility thresholds.
- Modify: `strategies/fossil_scarcity/strategy.toml` - direct/light-transform thresholds.
- Modify: `strategies/fragment_sets/strategy.toml` - bootstrap-friendly thresholds and caps.
- Modify: `strategies/high_dim_jewels/strategy.toml` - advanced-manual gating defaults.
- Modify: `strategies/map_logbook_packages/strategy.toml` - light-transform thresholds.
- Modify: `strategies/rog_basic/strategy.toml` - advanced-manual gating defaults.
- Modify: `strategies/scarab_reroll/strategy.toml` - light-transform thresholds.
- Modify: `poe_trade/sql/strategy/bulk_essence/candidate.sql` - emit direct-flip evidence inputs.
- Modify: `poe_trade/sql/strategy/bulk_fossils/candidate.sql` - emit direct-flip evidence inputs.
- Modify: `poe_trade/sql/strategy/cx_market_making/candidate.sql` - emit currency-market evidence inputs.
- Modify: `poe_trade/sql/strategy/dump_tab_reprice/candidate.sql` - emit repricing-step evidence.
- Modify: `poe_trade/sql/strategy/fossil_scarcity/candidate.sql` - emit direct-flip evidence inputs.
- Modify: `poe_trade/sql/strategy/fragment_sets/candidate.sql` - emit light-transform evidence inputs.
- Modify: `poe_trade/sql/strategy/map_logbook_packages/candidate.sql` - emit package-size and transform evidence.
- Modify: `poe_trade/sql/strategy/scarab_reroll/candidate.sql` - emit reroll-step evidence.
- Modify: `tests/unit/test_migrations.py` - migration contract coverage for the additive scanner schema.
- Modify: `tests/unit/test_strategy_registry.py` - metadata parsing and default coverage.
- Create: `tests/unit/test_strategy_opportunity.py` - normalized evidence/scoring coverage.
- Modify: `tests/unit/test_strategy_policy.py` - new evaluation order and terminal reason coverage.
- Modify: `tests/unit/test_strategy_scanner.py` - row isolation, decision logging, insert fallback, scoring order.
- Modify: `tests/unit/test_api_ops_analytics.py` - recommendation payload fields, legacy fallback, sort fallback, analytics payloads.
- Modify: `tests/unit/test_api_ops_routes.py` - route/query forwarding for explicit operation sort and staged defaults.
- Modify: `tests/test_app_new_analytics_routes.py` - explicit analytics route coverage for opportunities diagnostics.
- Modify: `frontend/src/types/api.ts` - additive recommendation/analytics types.
- Modify: `frontend/src/services/api.ts` - request params for the new sort default.
- Modify: `frontend/src/services/api.test.ts` - service serialization/normalization coverage.
- Modify: `frontend/src/components/tabs/OpportunitiesTab.tsx` - operation-aware default sort and execution-brief rendering.
- Modify: `frontend/src/components/tabs/OpportunitiesTab.test.tsx` - UI coverage for new fields and sort behavior.
- Modify: `frontend/src/components/tabs/DashboardTab.tsx` - top-opportunity summary copy/fields.
- Modify: `frontend/src/components/tabs/DashboardTab.test.tsx` - dashboard sort/default rendering coverage.
- Modify: `docs/ops-runbook.md` - operator-facing commands for the new ranking and diagnostics endpoints.

### Task 1: Add deterministic strategy metadata and shared opportunity-scoring helpers

**Files:**
- Create: `poe_trade/strategy/opportunity.py`
- Modify: `poe_trade/strategy/registry.py`
- Modify: `tests/unit/test_strategy_registry.py`
- Create: `tests/unit/test_strategy_opportunity.py`

- [ ] **Step 1: Write failing tests for metadata defaults and operation-aware scoring inputs**

Add focused tests covering new registry fields and a normalized scoring helper:

```python
def test_strategy_pack_loads_opportunity_gate_defaults() -> None:
    bulk_essence = next(pack for pack in registry.list_strategy_packs() if pack.strategy_id == "bulk_essence")
    assert bulk_essence.max_staleness_minutes == 30
    assert bulk_essence.max_estimated_whispers == 12
    assert bulk_essence.max_estimated_operations == 8


def test_score_opportunity_prefers_higher_profit_per_operation() -> None:
    direct = OpportunitySnapshot(
        expected_profit_chaos=24.0,
        estimated_operations=3,
        estimated_whispers=4,
        liquidity_score=0.8,
        confidence=0.75,
    )
    cumbersome = OpportunitySnapshot(
        expected_profit_chaos=60.0,
        estimated_operations=12,
        estimated_whispers=14,
        liquidity_score=0.5,
        confidence=0.7,
    )
    assert score_opportunity(direct).expected_profit_per_operation_chaos > score_opportunity(cumbersome).expected_profit_per_operation_chaos
```

- [ ] **Step 2: Run the focused registry/opportunity tests and verify they fail**

Run: `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_opportunity.py -v`
Expected: FAIL because the new `StrategyPack` fields and `poe_trade.strategy.opportunity` module do not exist yet.

- [ ] **Step 3: Implement the shared metadata/scoring primitives**

Create a focused module instead of burying new heuristics in `scanner.py`:

```python
@dataclass(frozen=True)
class OpportunitySnapshot:
    expected_profit_chaos: float | None
    estimated_operations: int
    estimated_whispers: int
    liquidity_score: float | None
    confidence: float | None


def expected_profit_per_operation(snapshot: OpportunitySnapshot) -> float | None:
    if snapshot.expected_profit_chaos is None or snapshot.estimated_operations <= 0:
        return None
    return snapshot.expected_profit_chaos / snapshot.estimated_operations
```

Extend `StrategyPack` and `list_strategy_packs()` to load safe defaults for:

- `max_staleness_minutes`
- `min_liquidity_score`
- `max_estimated_whispers`
- `max_estimated_operations`
- `advanced_override_profit_per_operation_chaos`

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_opportunity.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_strategy_registry.py tests/unit/test_strategy_opportunity.py poe_trade/strategy/registry.py poe_trade/strategy/opportunity.py
git commit -m "feat: add opportunity scoring primitives"
```

### Task 2: Schema-first rollout for additive scanner opportunity storage

**Files:**
- Create: `schema/migrations/0057_scanner_opportunity_analytics_v1.sql`
- Modify: `tests/unit/test_migrations.py`

- [ ] **Step 1: Write failing tests for the additive migration contract**

Add focused migration coverage like:

```python
def test_0057_scanner_opportunity_migration_creates_decision_table_and_columns() -> None:
    sql = Path("schema/migrations/0057_scanner_opportunity_analytics_v1.sql").read_text(encoding="utf-8")
    assert "scanner_candidate_decisions" in sql
    assert "expected_profit_per_operation_chaos" in sql
    assert "GRANT SELECT ON poe_trade.scanner_candidate_decisions TO poe_api_reader" in sql
```

- [ ] **Step 2: Run the focused migration test and verify it fails**

Run: `.venv/bin/pytest tests/unit/test_migrations.py -k scanner_opportunity -v`
Expected: FAIL because migration `0057_scanner_opportunity_analytics_v1.sql` does not exist yet.

- [ ] **Step 3: Add the schema-first migration only**

Migration `0057_scanner_opportunity_analytics_v1.sql` should:

- add nullable recommendation columns needed for the new sort/payload,
- create `poe_trade.scanner_candidate_decisions`,
- grant `SELECT` on the new table to `poe_api_reader`,
- include the minimum diagnostics columns from the spec: `accepted`, `decision_reason`, `strategy_id`, `league`, `item_or_market_key`, `complexity_tier`, `required_capital_chaos`, `estimated_operations`, `estimated_whispers`, `expected_profit_chaos`, `expected_profit_per_operation_chaos`, `feasibility_score`, `evidence_snapshot`, and `recorded_at`,
- keep storage additive and short-lived, without changing any writer or reader defaults yet.

- [ ] **Step 4: Run the focused migration test and dry-run the migration runner**

Run: `.venv/bin/pytest tests/unit/test_migrations.py -k scanner_opportunity -v && .venv/bin/python -m poe_trade.db.migrations --status --dry-run`
Expected: PASS for pytest; migration status lists the new file as pending without SQL parse errors.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_migrations.py schema/migrations/0057_scanner_opportunity_analytics_v1.sql
git commit -m "feat: add scanner opportunity schema"
```

### Task 3: Writer-compatible scanner scoring, dedupe, and decision logging

**Files:**
- Modify: `poe_trade/strategy/policy.py`
- Modify: `poe_trade/strategy/scanner.py`
- Modify: `tests/unit/test_strategy_policy.py`
- Modify: `tests/unit/test_strategy_scanner.py`

- [ ] **Step 1: Write failing tests for evaluation order, row isolation, and explicit V3 insert fallback**

Add tests that lock down the new writer behavior:

```python
def test_evaluate_candidates_dedupes_after_operation_scoring() -> None:
    fast = _candidate(key="dup", ts=BASE_TS, expected_profit_chaos=18.0, evidence={"estimated_operations": 3})
    slow = _candidate(key="dup", ts=BASE_TS, expected_profit_chaos=40.0, evidence={"estimated_operations": 10})
    evaluation = policy.evaluate_candidates([slow, fast], policy=policy.StrategyPolicy(), requested_league="Mirage")
    assert evaluation.eligible[0].expected_profit_chaos == 18.0


def test_run_scan_once_records_invalid_source_row_and_continues_pack(...) -> None:
    assert decision_rows[0]["decision_reason"] == "invalid_source_row"
    assert recommendation_rows[0]["item_or_market_key"] == "surviving-key"


def test_recommendation_insert_falls_back_from_v3_to_v2_columns(...) -> None:
    assert any("expected_profit_per_operation_chaos" in query for query in client.queries)
```

- [ ] **Step 2: Run the focused writer tests and verify they fail**

Run: `.venv/bin/pytest tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py -k "dedupe or invalid_source_row or decision or v3_to_v2" -v`
Expected: FAIL because the scanner still dedupes on raw metrics, can fail a whole pack on a bad row, and does not write V3 decision/recommendation rows safely.

- [ ] **Step 3: Implement writer-compatible scoring and decision persistence without changing read defaults**

Refactor scanner flow to:

```python
for source_row in source_rows:
    try:
        candidate = candidate_from_source_row(...)
    except ValueError:
        decision_rows.append(invalid_source_row_decision(...))
        continue
    staged_candidates.append(score_candidate(candidate, source_row=source_row, pack=pack))

evaluation = evaluate_candidates(...)
decision_rows.extend(decision_rows_from_evaluation(evaluation, ...))
```

Keep mixed-schema safety by adding explicit V3 -> V2 -> V1 insert fallback tuples in `scanner.py` rather than assuming generic ClickHouse tolerance. Do not change API defaults in this task.

- [ ] **Step 4: Run the focused writer tests and verify they pass**

Run: `.venv/bin/pytest tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py poe_trade/strategy/policy.py poe_trade/strategy/scanner.py
git commit -m "feat: add writer-compatible opportunity scoring"
```

### Task 4: Reader-compatible API enrichment with legacy-row fallback

**Files:**
- Modify: `poe_trade/api/ops.py`
- Modify: `poe_trade/api/app.py`
- Modify: `tests/unit/test_api_ops_analytics.py`
- Modify: `tests/unit/test_api_ops_routes.py`

- [ ] **Step 1: Write failing API tests for enriched rows, legacy rows, and explicit operation sort**

Add tests that prove both enriched and legacy rows remain readable and that the full spec contract is exposed additively:

```python
def test_scanner_recommendations_payload_exposes_execution_brief_fields() -> None:
    recommendation = scanner_recommendations_payload(client, sort_by="expected_profit_per_operation_chaos")["recommendations"][0]
    assert recommendation["opportunityType"] == "flip"
    assert recommendation["complexityTier"] == "direct_flip"
    assert recommendation["requiredCapitalChaos"] == 24.0
    assert recommendation["estimatedOperations"] == 3
    assert recommendation["estimatedSearches"] == 1
    assert recommendation["estimatedWhispers"] == 4
    assert recommendation["freshnessMinutes"] == 2
    assert recommendation["estimatedTimeToAcquireMinutes"] == 4
    assert recommendation["estimatedTimeToExitMinutes"] == 12
    assert recommendation["estimatedTotalCycleMinutes"] == 16
    assert recommendation["expectedProfitPerOperationChaos"] == 8.0
    assert recommendation["feasibilityScore"] == 0.86
    assert recommendation["liquidityScore"] == 0.81
    assert recommendation["riskScore"] == 0.2
    assert recommendation["competitionScore"] == 0.4
    assert recommendation["whyNow"] == "Bulk spread widened in the latest scan"
    assert recommendation["warnings"] == []
    assert recommendation["executionPlan"]["searchQuery"] == "Deafening Essence of Greed"
    assert recommendation["executionPlan"]["targetListPrice"] == 32.0
    assert recommendation["evidence"]["sampleCount"] == 40
    assert recommendation["evidence"]["strategySource"] == "bulk_essence"


def test_scanner_recommendations_payload_keeps_legacy_rows_readable_with_null_operation_fields() -> None:
    recommendation = scanner_recommendations_payload(client)["recommendations"][0]
    assert recommendation["expectedProfitPerOperationChaos"] is None
    assert recommendation["executionPlan"]["searchQuery"] == recommendation["searchHint"]


def test_scanner_recommendations_route_forwards_explicit_operation_sort(...) -> None:
    assert captured["sort_by"] == "expected_profit_per_operation_chaos"
```

- [ ] **Step 2: Run the focused reader tests and verify they fail**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py -k "execution_brief or legacy_rows or operation_sort" -v`
Expected: FAIL because the API does not yet emit the new fields or explicit operation sort safely.

- [ ] **Step 3: Implement additive payload shaping and explicit sort fallback**

Additive payload example:

```python
{
    "opportunityType": _optional_string(row.get("opportunity_type")) or "flip",
    "complexityTier": _optional_string(row.get("complexity_tier")),
    "requiredCapitalChaos": _coerce_float(row.get("required_capital_chaos")),
    "expectedProfitPerOperationChaos": row.get("expected_profit_per_operation_chaos"),
    "estimatedOperations": _as_int(row.get("estimated_operations")),
    "estimatedSearches": _as_int(row.get("estimated_searches")),
    "estimatedWhispers": _as_int(row.get("estimated_whispers")),
    "freshnessMinutes": freshness_minutes,
    "estimatedTimeToAcquireMinutes": _coerce_float(row.get("estimated_time_to_acquire_minutes")),
    "estimatedTimeToExitMinutes": _coerce_float(row.get("estimated_time_to_exit_minutes")),
    "estimatedTotalCycleMinutes": _coerce_float(row.get("estimated_total_cycle_minutes")),
    "feasibilityScore": _coerce_float(row.get("feasibility_score")),
    "liquidityScore": _coerce_float(row.get("liquidity_score")),
    "riskScore": _coerce_float(row.get("risk_score")),
    "competitionScore": _coerce_float(row.get("competition_score")),
    "whyNow": _optional_string(row.get("why_now")) or why_it_fired,
    "warnings": _warnings_from_snapshot(evidence_snapshot),
    "executionPlan": {
        "searchQuery": search_hint,
        "targetItem": item_name,
        "buySteps": [buy_plan],
        "transformSteps": [step for step in [transform_plan] if step],
        "sellSteps": [exit_plan],
        "maxBuyPrice": row.get("max_buy"),
        "targetListPrice": _coerce_float(row.get("target_list_price")),
        "minimumAcceptableExit": _coerce_float(row.get("minimum_acceptable_exit")),
        "targetQuantity": _as_int(row.get("target_quantity")),
        "preferredBulkSize": _as_int(row.get("preferred_bulk_size")),
        "stopConditions": _stop_conditions_from_snapshot(evidence_snapshot),
    },
    "evidence": {
        "sampleCount": row.get("sample_count"),
        "marketDepth": _coerce_float(row.get("market_depth")),
        "liquidityScore": _coerce_float(row.get("liquidity_score")),
        "competitionScore": _coerce_float(row.get("competition_score")),
        "spreadObserved": _coerce_float(row.get("spread_observed")),
        "freshnessMinutes": freshness_minutes,
        "strategySource": row.get("strategy_id"),
        "mlInfluenceScore": ml_influence_score,
        "mlInfluenceReason": ml_influence_reason,
    },
}
```

Update `_validate_scanner_sort()` to accept `expected_profit_per_operation_chaos`, but keep route and dashboard defaults unchanged in this task. Read-side SQL must fall back cleanly when V3 columns are absent.

- [ ] **Step 4: Run the focused reader tests and verify they pass**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py poe_trade/api/ops.py poe_trade/api/app.py
git commit -m "feat: add reader-compatible opportunity payloads"
```

### Task 5: Tune strategy metadata and normalized evidence before switching defaults

**Files:**
- Modify: `poe_trade/strategy/opportunity.py`
- Modify: `tests/unit/test_strategy_opportunity.py`
- Modify: `strategies/advanced_rare_finish/strategy.toml`
- Modify: `strategies/bulk_essence/strategy.toml`
- Modify: `strategies/bulk_fossils/strategy.toml`
- Modify: `strategies/cluster_basic/strategy.toml`
- Modify: `strategies/corruption_ev/strategy.toml`
- Modify: `strategies/cx_market_making/strategy.toml`
- Modify: `strategies/dump_tab_reprice/strategy.toml`
- Modify: `strategies/flask_basic/strategy.toml`
- Modify: `strategies/fossil_scarcity/strategy.toml`
- Modify: `strategies/fragment_sets/strategy.toml`
- Modify: `strategies/high_dim_jewels/strategy.toml`
- Modify: `strategies/map_logbook_packages/strategy.toml`
- Modify: `strategies/rog_basic/strategy.toml`
- Modify: `strategies/scarab_reroll/strategy.toml`
- Modify: `poe_trade/sql/strategy/bulk_essence/candidate.sql`
- Modify: `poe_trade/sql/strategy/bulk_fossils/candidate.sql`
- Modify: `poe_trade/sql/strategy/cx_market_making/candidate.sql`
- Modify: `poe_trade/sql/strategy/dump_tab_reprice/candidate.sql`
- Modify: `poe_trade/sql/strategy/fossil_scarcity/candidate.sql`
- Modify: `poe_trade/sql/strategy/fragment_sets/candidate.sql`
- Modify: `poe_trade/sql/strategy/map_logbook_packages/candidate.sql`
- Modify: `poe_trade/sql/strategy/scarab_reroll/candidate.sql`
- Modify: `tests/unit/test_strategy_registry.py`
- Modify: `tests/unit/test_strategy_scanner.py`

- [ ] **Step 1: Write failing tests for normalized adapter coverage and full-strategy review**

Add coverage that matches the spec's Python-side normalization approach:

```python
def test_normalize_strategy_source_row_maps_sparse_advanced_rows() -> None:
    normalized = normalize_strategy_source_row("advanced_rare_finish", {"league": "Mirage", "semantic_key": "rare-key"})
    assert normalized.complexity_tier == "advanced_manual"
    assert normalized.estimated_searches >= 1


def test_direct_flip_candidate_sql_contracts_emit_required_evidence_columns() -> None:
    for path in direct_flip_sql_paths:
        sql = path.read_text(encoding="utf-8").upper()
        assert "AS REQUIRED_CAPITAL_CHAOS" in sql
        assert "AS ESTIMATED_SEARCHES" in sql
        assert "AS ESTIMATED_WHISPERS" in sql


def test_all_strategy_packs_define_opportunity_gate_params() -> None:
    for pack in registry.list_strategy_packs():
        assert pack.max_estimated_whispers > 0
        assert pack.max_estimated_operations > 0
```

- [ ] **Step 2: Run the focused strategy/adapter tests and verify they fail**

Run: `.venv/bin/pytest tests/unit/test_strategy_opportunity.py tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py -k "normalize_strategy_source_row or required_evidence_columns or opportunity_gate_params" -v`
Expected: FAIL because the adapter coverage, strategy metadata, and direct-flip SQL evidence are incomplete.

- [ ] **Step 3: Implement normalized adapters plus strategy-specific evidence where it matters**

Keep heterogeneous SQL and move shared semantics into Python:

```python
def normalize_strategy_source_row(strategy_id: str, source_row: Mapping[str, object]) -> NormalizedOpportunityInput:
    if strategy_id in DIRECT_FLIP_STRATEGIES:
        return normalize_direct_flip_row(source_row)
    return normalize_high_friction_row(strategy_id, source_row)
```

Only direct/light-transform packs should be forced to emit richer SQL evidence. Advanced/manual packs should rely on stricter metadata plus adapter defaults instead of a fake homogeneous SQL contract.

- [ ] **Step 4: Run the focused strategy/adapter tests and the broader scanner contract tests**

Run: `.venv/bin/pytest tests/unit/test_strategy_opportunity.py tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_strategy_opportunity.py tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py poe_trade/strategy/opportunity.py strategies/advanced_rare_finish/strategy.toml strategies/bulk_essence/strategy.toml strategies/bulk_fossils/strategy.toml strategies/cluster_basic/strategy.toml strategies/corruption_ev/strategy.toml strategies/cx_market_making/strategy.toml strategies/dump_tab_reprice/strategy.toml strategies/flask_basic/strategy.toml strategies/fossil_scarcity/strategy.toml strategies/fragment_sets/strategy.toml strategies/high_dim_jewels/strategy.toml strategies/map_logbook_packages/strategy.toml strategies/rog_basic/strategy.toml strategies/scarab_reroll/strategy.toml poe_trade/sql/strategy/bulk_essence/candidate.sql poe_trade/sql/strategy/bulk_fossils/candidate.sql poe_trade/sql/strategy/cx_market_making/candidate.sql poe_trade/sql/strategy/dump_tab_reprice/candidate.sql poe_trade/sql/strategy/fossil_scarcity/candidate.sql poe_trade/sql/strategy/fragment_sets/candidate.sql poe_trade/sql/strategy/map_logbook_packages/candidate.sql poe_trade/sql/strategy/scarab_reroll/candidate.sql
git commit -m "feat: tune strategy evidence for bootstrap opportunities"
```

### Task 6: Add decision-log analytics and perform the final default switch

**Files:**
- Modify: `poe_trade/api/ops.py`
- Modify: `poe_trade/api/app.py`
- Modify: `poe_trade/config/constants.py`
- Modify: `tests/unit/test_api_ops_analytics.py`
- Modify: `tests/unit/test_api_ops_routes.py`
- Modify: `tests/test_app_new_analytics_routes.py`

- [ ] **Step 1: Write failing tests for analytics summaries and the final default-switch behavior**

Add coverage like:

```python
def test_analytics_scanner_reports_gate_rejections_and_complexity_mix() -> None:
    payload = analytics_scanner(client)
    assert payload["summary"]["rejectedByReason"]["over_whisper_budget"] == 4
    assert payload["summary"]["complexityTiers"]["direct_flip"] == 7
    assert payload["summary"]["suppressedStrategies"][0]["strategyId"] == "advanced_rare_finish"


def test_analytics_opportunities_exposes_distributions_and_top_opportunities() -> None:
    payload = analytics_opportunities(client)
    assert payload["distributions"]["expectedProfitPerOperationChaos"]
    assert payload["summary"]["suppressionReasons"]["over_capital_ceiling"] == 6


def test_dashboard_payload_uses_operation_aware_top_opportunities(monkeypatch) -> None:
    dashboard_payload(client, snapshots=[])
    assert captured["sort_by"] == "expected_profit_per_operation_chaos"


def test_scanner_recommendations_route_default_switches_after_v3_rollout(...) -> None:
    assert captured["sort_by"] == "expected_profit_per_operation_chaos"
```

- [ ] **Step 2: Run the focused analytics/default-switch tests and verify they fail**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py tests/test_app_new_analytics_routes.py -k "rejectedByReason or suppressionReasons or distributions or operation_aware_top_opportunities or default_switches" -v`
Expected: FAIL because scanner analytics still only group recommendation counts and the dashboard/default route sort have not switched.

- [ ] **Step 3: Implement analytics queries and the final default switch**

Keep the API additive and operator-focused:

```python
def analytics_opportunities(client: ClickHouseClient) -> dict[str, Any]:
    return {
        "summary": _opportunity_summary(client),
        "distributions": _opportunity_distributions(client),
        "topOpportunities": scanner_recommendations_payload(client, sort_by="expected_profit_per_operation_chaos", limit=10)["recommendations"],
        "rejections": _rejection_counts(client),
    }
```

In this task:

- bump `constants.RECOMMENDATION_CONTRACT_VERSION`,
- switch `dashboard_payload()` to `expected_profit_per_operation_chaos`,
- switch the route default sort only after the strategy review task is complete.

- [ ] **Step 4: Run the focused analytics/default-switch tests and verify they pass**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py tests/test_app_new_analytics_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py tests/test_app_new_analytics_routes.py poe_trade/api/ops.py poe_trade/api/app.py poe_trade/config/constants.py
git commit -m "feat: add opportunity analytics and default ranking"
```

### Task 7: Update frontend types, clients, and opportunity surfaces for execution guidance

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/services/api.test.ts`
- Modify: `frontend/src/components/tabs/OpportunitiesTab.tsx`
- Modify: `frontend/src/components/tabs/OpportunitiesTab.test.tsx`
- Modify: `frontend/src/components/tabs/DashboardTab.tsx`
- Modify: `frontend/src/components/tabs/DashboardTab.test.tsx`

- [ ] **Step 1: Write failing frontend tests for operation-aware requests and execution-brief rendering**

Add tests like:

```ts
test('defaults the opportunities tab to operation-aware sorting', async () => {
  render(<OpportunitiesTab />);
  await waitFor(() => {
    expect(getScannerRecommendationsMock).toHaveBeenCalledWith({ sort: 'expected_profit_per_operation_chaos', limit: 50 });
  });
});


test('renders execution-plan and feasibility fields', async () => {
  expect(await screen.findByText('Search Query')).toBeTruthy();
  expect(screen.getByText('flip')).toBeTruthy();
  expect(screen.getByText('Estimated Ops')).toBeTruthy();
  expect(screen.getByText('Freshness')).toBeTruthy();
  expect(screen.getByText('8c/op')).toBeTruthy();
});
```

- [ ] **Step 2: Run the focused frontend tests and verify they fail**

Run: `npm test -- src/services/api.test.ts src/components/tabs/OpportunitiesTab.test.tsx src/components/tabs/DashboardTab.test.tsx`
Working dir: `frontend/`
Expected: FAIL because the new type fields, sort option, and UI elements do not exist yet.

- [ ] **Step 3: Implement additive frontend contracts and rendering**

Extend the existing types instead of replacing them:

```ts
export interface ScannerRecommendation {
  // existing fields...
  opportunityType: string | null;
  complexityTier: string | null;
  requiredCapitalChaos: number | null;
  expectedProfitPerOperationChaos: number | null;
  estimatedOperations: number | null;
  estimatedSearches: number | null;
  estimatedWhispers: number | null;
  freshnessMinutes: number | null;
  feasibilityScore: number | null;
  riskScore: number | null;
  competitionScore: number | null;
  whyNow: string;
  warnings: string[];
  executionPlan?: {
    searchQuery: string;
    targetItem: string;
    buySteps: string[];
    transformSteps: string[];
    sellSteps: string[];
    stopConditions: string[];
  } | null;
}
```

Keep the current card layout, but add one execution section and one realism section instead of redesigning the whole tab.

- [ ] **Step 4: Run the focused frontend tests and verify they pass**

Run: `npm test -- src/services/api.test.ts src/components/tabs/OpportunitiesTab.test.tsx src/components/tabs/DashboardTab.test.tsx`
Working dir: `frontend/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/services/api.ts frontend/src/services/api.test.ts frontend/src/components/tabs/OpportunitiesTab.tsx frontend/src/components/tabs/OpportunitiesTab.test.tsx frontend/src/components/tabs/DashboardTab.tsx frontend/src/components/tabs/DashboardTab.test.tsx
git commit -m "feat: show structured trade execution guidance"
```

### Task 8: Update docs and run end-to-end verification

**Files:**
- Modify: `docs/ops-runbook.md`
- Modify: `docs/superpowers/specs/2026-03-21-bootstrap-trade-opportunity-analytics-design.md` only if implementation realities force a narrow follow-up note

- [ ] **Step 1: Write the failing docs assertions by listing the commands the runbook must document**

Record the exact commands to verify after implementation:

```text
curl -i -H "Authorization: Bearer $POE_API_OPERATOR_TOKEN" "http://127.0.0.1:8080/api/v1/ops/scanner/recommendations?sort=expected_profit_per_operation_chaos&limit=5"
curl -i -H "Authorization: Bearer $POE_API_OPERATOR_TOKEN" "http://127.0.0.1:8080/api/v1/ops/analytics/opportunities"
```

- [ ] **Step 2: Run the full backend/frontend verification suite before editing docs**

Run: `.venv/bin/pytest tests/unit/test_migrations.py tests/unit/test_strategy_registry.py tests/unit/test_strategy_opportunity.py tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py tests/test_app_new_analytics_routes.py`
Expected: PASS.

Run: `npm test -- src/services/api.test.ts src/components/tabs/OpportunitiesTab.test.tsx src/components/tabs/DashboardTab.test.tsx`
Working dir: `frontend/`
Expected: PASS. If either command fails, fix code first and only then update docs.

- [ ] **Step 3: Update the runbook with shipped commands and route semantics**

Document only implemented behavior:

```md
- `curl -i -H "Authorization: Bearer $POE_API_OPERATOR_TOKEN" "http://127.0.0.1:8080/api/v1/ops/scanner/recommendations?sort=expected_profit_per_operation_chaos&limit=5"` to inspect operation-aware opportunity ranking.
- `curl -i -H "Authorization: Bearer $POE_API_OPERATOR_TOKEN" "http://127.0.0.1:8080/api/v1/ops/analytics/opportunities"` to inspect rejection reasons and complexity-tier summaries.
```

- [ ] **Step 4: Run the lightweight final verification commands and capture output**

Run: `.venv/bin/python -m poe_trade.cli --help && .venv/bin/python -m poe_trade.db.migrations --status --dry-run`
Expected: CLI help prints successfully; migration status is readable and mentions no SQL parse errors.

- [ ] **Step 5: Commit**

```bash
git add docs/ops-runbook.md docs/superpowers/specs/2026-03-21-bootstrap-trade-opportunity-analytics-design.md
git commit -m "docs: add opportunity analytics runbook guidance"
```
