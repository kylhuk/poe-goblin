# Opportunity Pipeline Contract Parity

## TL;DR
> **Summary**: Replace coarse non-bulk opportunity sourcing with listing-level feature-aware inputs, unify SQL and ML opportunities under one versioned scanner contract, and make deployed frontend/backend revisions visible and comparable from the same ops surface.
> **Deliverables**:
> - Additive item-feature extraction layer and family reference marts for non-bulk strategies
> - Unified scanner recommendation contract with provenance and version stamping
> - ML-backed scanner candidate path and real price-check comparables
> - Backend/frontend deployment metadata banner plus stale-row invalidation workflow
> **Effort**: XL
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7

## Context
### Original Request
- Plan one delivery that fixes four linked issues: coarse non-bulk sourcing from `gold_listing_ref_hour`, live frontend/backend contract drift, ML opportunities not reaching scanner recommendations, and `price_check_payload()` still returning empty comparables.

### Interview Summary
- Repo exploration confirmed `poe_trade.gold_listing_ref_hour` is grouped only by `time_bucket`, `realm`, `league`, `category`, `base_type`, and `price_currency`, so non-bulk packs still price off base-type medians rather than item-level structure.
- `schema/migrations/0025_psapi_silver_current_views.sql` already exposes `ilvl`, `corrupted`, `fractured`, `synthesised`, parsed price notes, and `category`, but not parsed affix/notable/passive/enchant features.
- `dashboard_payload()` intentionally counts only five core services, while frontend currently has no deployment/version banner and backend contract payloads expose no build SHA metadata.
- ML plumbing already exists in `schema/migrations/0032_ml_pricing_v1.sql` and `poe_trade/ml/workflows.py`, including `ml_comps_v1`, `ml_route_candidates_v1`, and `ml_price_predictions_v1`, but scanner and price-check APIs do not surface those artifacts as opportunities/comparables.
- User decision: implement real comparables now; do not ship `comparables_supported=false` as the end state for this slice.
- Default applied: use tests-after with the existing `pytest`, `vitest`, Playwright, QA, and CI surfaces.

### Metis Review (gaps addressed)
- Added an explicit feature extraction layer below new non-bulk marts so the plan does not pretend `v_ps_items_enriched` already contains affix/notable/passive/enchant signals.
- Chose listing-level candidate generation for non-bulk strategies instead of mart-only medians so emitted opportunities remain searchable and actionable.
- Added scanner provenance/version columns to both `scanner_recommendations` and `scanner_alert_log` so stale recommendations and cooldown rows cannot survive contract changes.
- Treated ML as a recommendation producer that flows through the existing scanner contract rather than as a second feed with different pagination/sorting semantics.
- Treated frontend HTML no-cache as an explicit deployment/runbook requirement if hosting config is outside this repo.

## Work Objectives
### Core Objective
- Make every non-bulk strategy emit listing-level, searchable opportunities from feature-aware sources, while keeping bulk strategies on coarse hourly marts and exposing one consistent deployment/recommendation contract across backend API, frontend UI, and scanner storage.

### Deliverables
- Additive feature extraction storage/view layer derived from public-stash item JSON.
- Additive family reference marts for flasks, cluster jewels/jewels, and rares.
- Migrated non-bulk SQL strategy packs that no longer read only `poe_trade.gold_listing_ref_hour`.
- Additive scanner recommendation provenance/version columns and invalidation workflow.
- ML-backed scanner candidate path that can surface gem/rare anomalies in `/api/v1/ops/scanner/recommendations`.
- Real price-check comparables returned from ML-backed comparable rows.
- Deployment metadata surfaced in `/api/v1/ops/contract` and rendered on the homepage with matching SHA/banner behavior.

### Definition of Done (verifiable conditions with commands)
- `poe-migrate --status --dry-run` shows only the newly planned additive migrations and no modified shipped migrations.
- `.venv/bin/pytest tests/unit/test_migrations.py tests/unit/test_strategy_scanner.py tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py` passes with assertions covering feature marts, recommendation provenance/version fields, invalidation behavior, and mixed SQL/ML rows.
- `.venv/bin/pytest tests/unit/test_ml_*.py` passes with assertions covering comparable lookup and ML candidate preparation.
- `npm --prefix frontend run test` passes after the planned frontend contract/banner assertions are added.
- `make qa-up && make qa-seed && make qa-frontend` followed by `npx --prefix frontend playwright test` passes with evidence showing the deployment banner, opportunities list, and price-check comparables.
- `curl -s -H "Authorization: Bearer qa-operator-token" http://127.0.0.1:18080/api/v1/ops/contract` returns non-empty backend/frontend SHA fields, a recommendation contract version, and a deterministic match/mismatch state.
- `curl -s -X POST -H "Authorization: Bearer qa-operator-token" -H "Content-Type: application/json" --data '{"itemText":"Item Class: Helmets\nRarity: Rare\nGrim Veil\nHubris Circlet\n--------\nItem Level: 84"}' http://127.0.0.1:18080/api/v1/ops/leagues/Mirage/price-check` returns a non-empty `comparables` array for a supported item and a concrete fallback reason for low-support cases.
- `make ci-deterministic` passes as the final regression gate.

### Must Have
- Bulk/category strategies remain on coarse marts such as `poe_trade.gold_listing_ref_hour` and `poe_trade.gold_bulk_premium_hour`.
- Every non-bulk strategy currently reading `poe_trade.gold_listing_ref_hour` gets a declared replacement input and no longer depends only on base-type/category medians.
- SQL-derived and ML-derived recommendations land in the same `poe_trade.scanner_recommendations` contract and page/sort together.
- Scanner rows and alert-log rows are version-stamped so stale rows from older contracts cannot affect live API behavior or cooldown logic.
- Price-check comparables come from real comparable rows, not frontend mocks or fabricated placeholders.
- Frontend and backend deployment metadata come from explicit revision/build inputs and render without changing the dashboard’s five-service summary semantics.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No destructive edits to shipped migrations.
- No attempt to build a universal PoE parser for every item family; parse only features required by the in-scope non-bulk packs.
- No migration of bulk strategies such as `bulk_essence`, `bulk_fossils`, `fossil_scarcity`, `fragment_sets`, `map_logbook_packages`, `scarab_reroll`, or `cx_market_making` off their current coarse marts.
- No second opportunities feed or alternate ML-only API contract.
- No continued `comparables: []` stub for supported price-check cases.
- No frontend-owned hardcoded service denominator or SHA comparison logic that can drift from backend contract payloads.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with existing `pytest`, migration tests, frontend `vitest`, Playwright, QA compose, and `make ci-deterministic`.
- QA policy: every task includes one happy-path and one failure/edge-path agent-executed scenario.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Extract shared dependencies first, then parallelize dependent migrations/integrations.

Wave 1: contract/version scaffolding, feature extraction layer, family marts, non-bulk SQL migration
Wave 2: ML scanner integration, price-check comparables, deployment metadata/banner/invalidation

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 4, 5, 6, and 7.
- Task 2 blocks Tasks 3, 4, and 6.
- Task 3 blocks Task 4.
- Task 4 blocks final scanner parity verification.
- Task 5 depends on Task 1 and uses existing ML tables; it feeds final recommendation verification.
- Task 6 depends on Task 1 and Task 2 and may reuse outputs populated for Task 5.
- Task 7 depends on Task 1 and must run after scanner invalidation/version fields exist.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 4 tasks -> `deep`, `unspecified-high`
- Wave 2 -> 3 tasks -> `deep`, `unspecified-high`
- Final Verification -> 4 tasks -> `oracle`, `unspecified-high`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Lock the unified recommendation contract and additive scanner row metadata

  **What to do**: Add failing-then-passing tests for additive scanner recommendation provenance/version fields and the backend deployment contract shape. Introduce a new recommendation contract constant (`2`) and additive columns on both `poe_trade.scanner_recommendations` and `poe_trade.scanner_alert_log` for `recommendation_source`, `recommendation_contract_version`, `producer_version`, and `producer_run_id`. Update the scanner insert path, cooldown queries, and API mapping so legacy rows remain readable while new rows expose provenance/version metadata in JSON responses.
  **Must NOT do**: Do not change the existing service-summary denominator logic, do not delete historical rows in this task, and do not split ML recommendations into a second API contract.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: cross-cuts ClickHouse schema, scanner storage, API mapping, and regression tests.
  - Skills: [`protocol-compat`] - Use additive schema evolution and legacy-row read safety.
  - Omitted: [`docs-specialist`] - No documentation-only work yet.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 5, 6, 7 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `schema/migrations/0029_scanner_tables.sql` - Existing scanner storage contract that must be evolved additively.
  - Pattern: `poe_trade/strategy/scanner.py` - Current scanner insert path for recommendations and alert log rows.
  - Pattern: `poe_trade/strategy/policy.py` - Evidence snapshot and compatibility-key behavior that must remain backward-safe.
  - Pattern: `poe_trade/api/ops.py` - Current recommendation mapping, cursoring, and dashboard payload wiring.
  - Test: `tests/unit/test_strategy_scanner.py` - Existing scanner contract and insert-query assertions.
  - Test: `tests/unit/test_api_ops_analytics.py` - Existing recommendation API mapping assertions and dashboard summary lock.
  - Test: `tests/unit/test_api_ops_routes.py` - Existing route-forwarding/error handling assertions.
  - External: `https://github.com/ClickHouse/ClickHouse/blob/master/docs/en/sql-reference/statements/create/view.md` - MV/additive migration guardrail.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `poe-migrate --status --dry-run` shows one new additive migration for scanner row metadata and no edited historical migrations.
  - [ ] `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py` passes with assertions for additive `recommendationSource`, `contractVersion`, and legacy-row compatibility.
  - [ ] `curl -s -H "Authorization: Bearer qa-operator-token" http://127.0.0.1:18080/api/v1/ops/scanner/recommendations?limit=2` returns rows whose JSON includes recommendation provenance/version fields for new rows and does not 500 on legacy rows.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```bash
  Scenario: New recommendation rows expose additive provenance metadata
    Tool: Bash
    Steps: Run `poe-migrate --status --dry-run`; run `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_api_ops_analytics.py tests/unit/test_api_ops_routes.py`; if QA stack is running, call `curl -s -H "Authorization: Bearer qa-operator-token" "http://127.0.0.1:18080/api/v1/ops/scanner/recommendations?limit=2" > .sisyphus/evidence/task-1-contract.json`
    Expected: Pytest exits 0; saved JSON contains additive provenance/version keys and recommendation pagination remains valid.
    Evidence: .sisyphus/evidence/task-1-contract.json

  Scenario: Legacy recommendation rows remain readable
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k legacy` after adding a fixture row without the new columns; save pytest output to `.sisyphus/evidence/task-1-contract-legacy.txt`
    Expected: Exit code 0; API serialization assertions prove missing new fields do not cause a 500 or cursor failure.
    Evidence: .sisyphus/evidence/task-1-contract-legacy.txt
  ```

  **Commit**: YES | Message: `test(contract): lock recommendation metadata expectations` | Files: [`schema/migrations`, `poe_trade/strategy/scanner.py`, `poe_trade/api/ops.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_api_ops_analytics.py`, `tests/unit/test_api_ops_routes.py`]

- [ ] 2. Add the item-feature extraction layer for non-bulk families

  **What to do**: Add additive silver/current-layer feature storage derived from public-stash item JSON so non-bulk strategies can depend on parsed item structure instead of base-type medians. Create a feature table/view pair keyed to current listings that captures only the in-scope fields required by non-bulk packs: `ilvl_band`, `corrupted`, `fractured`, `synthesised`, `mod_token_signature`, `enchant_signature`, `cluster_passive_count`, `cluster_notable_signature`, and family-safe lookup keys for current listings. Reuse existing item identity rules from `ml_latest_items_v1` so current-item joins are deterministic.
  **Must NOT do**: Do not attempt a universal parser for every PoE item mechanic, do not backfill by mutating shipped MVs in place, and do not make strategies read raw `item_json` directly.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: schema design plus feature extraction must balance item fidelity with ClickHouse cardinality.
  - Skills: [`protocol-compat`] - Additive ClickHouse evolution and rebuild/backfill guardrails are mandatory.
  - Omitted: [`docs-specialist`] - This task is schema/runtime work, not documentation-first.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 4, 6 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `schema/migrations/0025_psapi_silver_current_views.sql` - Current silver/raw/current PS item surfaces and pricing/category parsing.
  - Pattern: `schema/migrations/0032_ml_pricing_v1.sql` - Existing ML dataset/current-item modeling and `ml_latest_items_v1` view structure.
  - Pattern: `poe_trade/ml/workflows.py` - Existing item identity and comparable table helpers that already assume current-item semantics.
  - Pattern: `schema/migrations/0027_gold_reference_marts.sql` - Naming, ordering, grants, and additive gold/silver migration style.
  - Test: `tests/unit/test_migrations.py` - Migration validation patterns.
  - External: `https://github.com/ClickHouse/ClickHouse/blob/master/docs/en/sql-reference/statements/create/view.md` - MV insert-trigger behavior and rebuild caveat.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `poe-migrate --status --dry-run` lists a new additive migration for the item-feature layer and grants.
  - [ ] `.venv/bin/pytest tests/unit/test_migrations.py` passes with assertions covering new table/view names and additive DDL only.
  - [ ] `clickhouse-client --query "DESCRIBE TABLE poe_trade.silver_ps_item_features_v1"` and `clickhouse-client --query "DESCRIBE TABLE poe_trade.v_ps_latest_feature_items_v1"` succeed after migration/apply in QA or local ClickHouse.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```bash
  Scenario: Feature layer exposes required family-safe fields
    Tool: Bash
    Steps: Run `poe-migrate --status --dry-run`; after apply in QA/local, run `clickhouse-client --query "DESCRIBE TABLE poe_trade.silver_ps_item_features_v1" > .sisyphus/evidence/task-2-feature-describe.txt` and `clickhouse-client --query "SELECT * FROM poe_trade.v_ps_latest_feature_items_v1 LIMIT 3 FORMAT JSONEachRow" > .sisyphus/evidence/task-2-feature-sample.json`
    Expected: Describe output includes the planned family feature columns; sample rows contain current-item keys and parsed feature fields without raw JSON-only dependency.
    Evidence: .sisyphus/evidence/task-2-feature-sample.json

  Scenario: Unsupported/missing features are excluded instead of guessed
    Tool: Bash
    Steps: Add a targeted migration/unit fixture and run `.venv/bin/pytest tests/unit/test_migrations.py -k feature`; save output to `.sisyphus/evidence/task-2-feature-missing.txt`
    Expected: Exit code 0; assertions prove missing family features remain null/absent rather than silently backfilled with fake defaults.
    Evidence: .sisyphus/evidence/task-2-feature-missing.txt
  ```

  **Commit**: YES | Message: `feat(schema): add item feature extraction layer` | Files: [`schema/migrations`, `poe_trade/ml/workflows.py`, `tests/unit/test_migrations.py`]

- [ ] 3. Add family reference marts and gold refresh wiring for non-bulk pricing

  **What to do**: Create additive family reference marts that aggregate the new feature layer by only the dimensions required for actionable non-bulk pricing. Add `poe_trade.gold_flask_feature_ref_hour`, `poe_trade.gold_cluster_feature_ref_hour`, and `poe_trade.gold_rare_feature_ref_hour` plus their refresh SQL assets under `poe_trade/sql/gold/`. Wire them into the existing gold refresh discovery so `refresh gold --group refs --dry-run` lists the new assets. Keep the marts reference-oriented: they are fair-value inputs for candidate joins, not the final candidate feed.
  **Must NOT do**: Do not replace `poe_trade.gold_listing_ref_hour`, do not add raw affix text to GROUP BY keys, and do not make these marts store current listing identity.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: requires ClickHouse aggregation design and careful cardinality control.
  - Skills: [`protocol-compat`] - New marts must be additive, grant-safe, and refreshable.
  - Omitted: [`docs-specialist`] - Documentation update happens after runtime behavior is in place.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4 | Blocked By: 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `schema/migrations/0027_gold_reference_marts.sql` - Existing gold mart naming/order/grant conventions.
  - Pattern: `poe_trade/sql/gold/110_listing_ref_hour.sql` - Current refresh-asset structure and grouping style to imitate only where appropriate.
  - Pattern: `poe_trade/sql/gold/120_liquidity_ref_hour.sql` - Existing asset layout under `poe_trade/sql/gold/`.
  - Pattern: `poe_trade/cli.py` - Gold refresh CLI/asset discovery path.
  - Test: `tests/unit/test_analytics_reports.py` - Existing report/mart query coverage patterns.
  - Test: `tests/unit/test_api_ops_analytics.py` - Existing gold diagnostics assertions.
  - External: `https://github.com/ClickHouse/ClickHouse/blob/master/docs/en/engines/table-engines/mergetree-family/aggregatingmergetree.md` - Aggregate-state guidance for additive marts.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `poe-migrate --status --dry-run` lists a new additive migration creating the three family marts and grants.
  - [ ] `.venv/bin/python -m poe_trade.cli refresh gold --group refs --dry-run` lists refresh assets for the three new marts.
  - [ ] `.venv/bin/pytest tests/unit/test_analytics_reports.py tests/unit/test_api_ops_analytics.py -k "gold or diagnostics"` passes with assertions covering the new marts where applicable.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```bash
  Scenario: Gold refresh discovery includes family marts
    Tool: Bash
    Steps: Run `.venv/bin/python -m poe_trade.cli refresh gold --group refs --dry-run > .sisyphus/evidence/task-3-refresh-dry-run.txt`
    Expected: Output includes refresh assets for `gold_flask_feature_ref_hour`, `gold_cluster_feature_ref_hour`, and `gold_rare_feature_ref_hour` in addition to existing coarse marts.
    Evidence: .sisyphus/evidence/task-3-refresh-dry-run.txt

  Scenario: Feature marts keep cardinality-safe grouped rows
    Tool: Bash
    Steps: After refresh in QA/local, run `clickhouse-client --query "SELECT count() AS rows, uniqExact(base_type) AS base_types FROM poe_trade.gold_cluster_feature_ref_hour WHERE league = 'Mirage'" > .sisyphus/evidence/task-3-cluster-counts.txt`
    Expected: Query succeeds and row counts reflect grouped feature buckets rather than one row per live listing.
    Evidence: .sisyphus/evidence/task-3-cluster-counts.txt
  ```

  **Commit**: YES | Message: `feat(schema): add non-bulk family reference marts` | Files: [`schema/migrations`, `poe_trade/sql/gold`, `poe_trade/cli.py`, `tests/unit/test_analytics_reports.py`, `tests/unit/test_api_ops_analytics.py`]

- [ ] 4. Migrate non-bulk strategy packs to listing-level feature-aware candidate sources

  **What to do**: Rewrite the current non-bulk strategy candidate/discover SQL so each pack reads current listings plus the new family reference marts, rather than only hourly category/base-type medians. Migrate these in-scope packs: `advanced_rare_finish`, `cluster_basic`, `corruption_ev`, `dump_tab_reprice`, `flask_basic`, `high_dim_jewels`, and `rog_basic`. Each rewritten `candidate.sql` must emit searchable/listing-level fields (`item_name`, `search_hint`, `max_buy`, `semantic_key`, feature evidence fields, and a deterministic `item_or_market_key`) while preserving the scanner policy minima contract and current scanner pagination/sort behavior.
  **Must NOT do**: Do not touch bulk strategy inputs, do not leave any of the seven in-scope non-bulk packs reading only `poe_trade.gold_listing_ref_hour`, and do not emit opportunities for rows missing required family features.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: coordinated SQL contract migration across multiple strategy packs with scanner compatibility requirements.
  - Skills: [] - Existing repo strategy patterns are the main source of truth.
  - Omitted: [`protocol-compat`] - Schema design is complete by this point; this task is strategy/runtime migration.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: final scanner parity verification | Blocked By: 1, 3

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/sql/strategy/flask_basic/candidate.sql` - Current coarse non-bulk anti-pattern to replace.
  - Pattern: `poe_trade/sql/strategy/cluster_basic/candidate.sql` - Current cluster-jewel coarse anti-pattern.
  - Pattern: `poe_trade/sql/strategy/high_dim_jewels/candidate.sql` - Current high-dimensional jewel coarse anti-pattern.
  - Pattern: `poe_trade/sql/strategy/advanced_rare_finish/candidate.sql` - Current rare-item coarse anti-pattern.
  - Pattern: `poe_trade/sql/strategy/corruption_ev/candidate.sql` - Existing corruption-focused pack that needs explicit state-aware sourcing.
  - Pattern: `poe_trade/sql/strategy/dump_tab_reprice/candidate.sql` - Existing stale-listing pack that should join current listings to feature refs.
  - Pattern: `poe_trade/sql/strategy/rog_basic/candidate.sql` - Existing rare-pack coarse-source consumer.
  - Pattern: `poe_trade/strategy/policy.py` - Required candidate aliases, semantic-key handling, sample-count rules, and evidence snapshot preservation.
  - Pattern: `poe_trade/strategy/scanner.py` - Scanner source-row ingestion and field preservation into recommendation rows.
  - Test: `tests/unit/test_strategy_scanner.py` - Candidate SQL contract tests and scanner insertion assertions.
  - Test: `tests/unit/test_cli_scan.py` - CLI `scan plan` expectations for actionable fields.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `rg -n "FROM poe_trade\.gold_listing_ref_hour" poe_trade/sql/strategy/{advanced_rare_finish,cluster_basic,corruption_ev,dump_tab_reprice,flask_basic,high_dim_jewels,rog_basic}` returns no matches in `candidate.sql` or `discover.sql` after migration.
  - [ ] `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_cli_scan.py` passes with assertions covering listing-level fields and feature evidence.
  - [ ] `.venv/bin/python -m poe_trade.cli scan plan --league Mirage --limit 20` prints rows whose columns include non-empty `item_name`/`search_hint` semantics and actionable `max_buy`/plan text for migrated packs.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```bash
  Scenario: Non-bulk packs emit actionable listing-level candidates
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_cli_scan.py`; run `.venv/bin/python -m poe_trade.cli scan plan --league Mirage --limit 20 > .sisyphus/evidence/task-4-scan-plan.txt`
    Expected: Pytest exits 0; scan-plan output contains migrated non-bulk rows with actionable search/buy fields and no fallback-only base-type medians.
    Evidence: .sisyphus/evidence/task-4-scan-plan.txt

  Scenario: Rows missing required family features are filtered out
    Tool: Bash
    Steps: Add targeted fixtures for a missing-feature flask/cluster/rare row and run `.venv/bin/pytest tests/unit/test_strategy_scanner.py -k missing`; save output to `.sisyphus/evidence/task-4-missing-features.txt`
    Expected: Exit code 0; scanner decisions reject those rows instead of emitting misleading candidates.
    Evidence: .sisyphus/evidence/task-4-missing-features.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): migrate non-bulk packs to feature-aware candidates` | Files: [`poe_trade/sql/strategy/advanced_rare_finish`, `poe_trade/sql/strategy/cluster_basic`, `poe_trade/sql/strategy/corruption_ev`, `poe_trade/sql/strategy/dump_tab_reprice`, `poe_trade/sql/strategy/flask_basic`, `poe_trade/sql/strategy/high_dim_jewels`, `poe_trade/sql/strategy/rog_basic`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_cli_scan.py`]

- [ ] 5. Add an ML anomaly producer that feeds the existing scanner recommendations table

  **What to do**: Add an additive ML scanner-candidate input surface that joins `ml_latest_items_v1`, `ml_route_candidates_v1`, `ml_price_predictions_v1`, and `ml_comps_v1` into one scanner-ready source. Add one new enabled strategy pack, `ml_anomaly`, whose `candidate.sql` reads that source and emits the same scanner contract fields used by SQL packs, including `recommendation_source = ml_anomaly`, searchable item fields, comparable-count evidence, and producer/model version metadata. Keep all API pagination, sorting, and semantic-key logic inside the existing scanner recommendation pipeline.
  **Must NOT do**: Do not expose a second opportunities endpoint, do not bypass `poe_trade.scanner_recommendations`, and do not emit ML rows with null sort/pagination fields that break cursoring.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: unifies ML tables, scanner strategy packs, provenance metadata, and ranking invariants.
  - Skills: [] - Repo ML/scanner contracts are the authoritative patterns.
  - Omitted: [`docs-specialist`] - This is runtime/data-path work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: final mixed-feed verification | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `schema/migrations/0032_ml_pricing_v1.sql` - Existing ML tables: `ml_route_candidates_v1`, `ml_comps_v1`, `ml_price_predictions_v1`, and `ml_latest_items_v1`.
  - Pattern: `poe_trade/ml/workflows.py` - Existing `build_comps()`, `predict_batch()`, and prediction fields such as `comp_count`, `base_comp_price_p50`, and `prediction_explainer_json`.
  - Pattern: `poe_trade/strategy/registry.py` - Strategy pack discovery and `candidate.sql` loading.
  - Pattern: `poe_trade/strategy/scanner.py` - Shared insert path that all recommendation producers must use.
  - Pattern: `poe_trade/api/ops.py` - Unified recommendation mapping, cursoring, and mixed-feed sorting surface.
  - Test: `tests/unit/test_api_ops_analytics.py` - Existing recommendation payload mapping and sorting assertions.
  - Test: `tests/unit/test_strategy_scanner.py` - Scanner insertion/query contract assertions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_api_ops_analytics.py` passes with new assertions covering mixed SQL + ML recommendation rows, stable cursor ordering, and additive provenance fields.
  - [ ] `curl -s -H "Authorization: Bearer qa-operator-token" "http://127.0.0.1:18080/api/v1/ops/scanner/recommendations?sort=expected_profit_per_minute_chaos&limit=10"` returns at least one `ml_anomaly` row in seeded QA evidence when ML candidate fixtures are present.
  - [ ] The mixed-feed response preserves `semanticKey`, `searchHint`, `itemName`, `effectiveConfidence`, and pagination metadata for both SQL and ML rows.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```bash
  Scenario: ML and SQL opportunities page together under one contract
    Tool: Bash
    Steps: Seed QA fixtures that include one SQL opportunity and one ML anomaly, then call `curl -s -H "Authorization: Bearer qa-operator-token" "http://127.0.0.1:18080/api/v1/ops/scanner/recommendations?sort=expected_profit_per_minute_chaos&limit=10" > .sisyphus/evidence/task-5-mixed-recommendations.json`
    Expected: Saved JSON contains both recommendation sources, stable sort order, and one contract shape.
    Evidence: .sisyphus/evidence/task-5-mixed-recommendations.json

  Scenario: ML rows with thin support do not break cursor pagination
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "cursor or ml" > .sisyphus/evidence/task-5-ml-cursor.txt`
    Expected: Exit code 0; tests prove thin-support ML rows either serialize safely or are filtered before cursor generation.
    Evidence: .sisyphus/evidence/task-5-ml-cursor.txt
  ```

  **Commit**: YES | Message: `feat(scanner): unify ml anomaly candidates with scanner recommendations` | Files: [`schema/migrations`, `poe_trade/ml/workflows.py`, `poe_trade/strategy/scanner.py`, `poe_trade/strategy/registry.py`, `poe_trade/sql/strategy`, `strategies`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_api_ops_analytics.py`]

- [ ] 6. Return real price-check comparables from ML-backed lookup paths

  **What to do**: Extend the price-check path so pasted clipboard items resolve to real comparable listings instead of an empty stub. Derive a comparable lookup target from parsed clipboard fields and the new feature layer/current-item surfaces, then retrieve the nearest comparable rows from `ml_comps_v1` and supporting listing metadata from `ml_price_dataset_v1` or `ml_latest_items_v1`. Keep the existing `comparables` array shape used by the frontend, populate it with deterministic ordering, and preserve `fallbackReason` for low-support cases where no real comparable rows exist.
  **Must NOT do**: Do not fabricate comparables, do not change `comparables` into a different JSON shape, and do not hide unsupported cases behind silent empty arrays without a concrete fallback reason.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: combines API behavior, ML retrieval logic, and frontend contract stability.
  - Skills: [] - Existing ML and API code define the integration seam.
  - Omitted: [`protocol-compat`] - This task consumes existing schema rather than defining the core migration layout.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: final price-check verification | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/api/ops.py` - Current `price_check_payload()` stub and fallback fields.
  - Pattern: `poe_trade/api/ml.py` - Current `fetch_predict_one()` request/response mapping.
  - Pattern: `poe_trade/ml/workflows.py` - Existing `predict_one()`, `build_comps()`, and `ml_price_predictions_v1`/`ml_comps_v1` field meanings.
  - Pattern: `schema/migrations/0032_ml_pricing_v1.sql` - Comparable storage and price-prediction schema.
  - Pattern: `frontend/src/components/tabs/PriceCheckTab.tsx` - Existing comparables rendering behavior and fallback copy.
  - Pattern: `frontend/src/types/api.ts` - Existing `PriceCheckResponse` contract.
  - Test: `frontend/src/services/api.test.ts` - Existing API serialization test patterns.
  - External: `https://github.com/facebookresearch/faiss/blob/master/README.md` - Nearest-neighbor retrieval tradeoff guidance.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `.venv/bin/pytest tests/unit/test_api_ops_routes.py tests/unit/test_api_ops_analytics.py tests/unit/test_ml_*.py` passes with new assertions for comparable lookup, fallback reasons, and API stability.
  - [ ] `curl -s -X POST -H "Authorization: Bearer qa-operator-token" -H "Content-Type: application/json" --data '{"itemText":"Item Class: Helmets\nRarity: Rare\nGrim Veil\nHubris Circlet\n--------\nItem Level: 84"}' http://127.0.0.1:18080/api/v1/ops/leagues/Mirage/price-check` returns a non-empty `comparables` array for a supported fixture item.
  - [ ] Low-support clipboard requests return `comparables: []` only together with a non-empty `fallbackReason` documenting why retrieval could not produce real comps.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```bash
  Scenario: Supported clipboard item returns real comparables
    Tool: Bash
    Steps: Call `curl -s -X POST -H "Authorization: Bearer qa-operator-token" -H "Content-Type: application/json" --data '{"itemText":"Item Class: Helmets\nRarity: Rare\nGrim Veil\nHubris Circlet\n--------\nItem Level: 84"}' http://127.0.0.1:18080/api/v1/ops/leagues/Mirage/price-check > .sisyphus/evidence/task-6-price-check.json`
    Expected: Saved JSON has `comparables | length >= 1`; first comparable contains non-empty `name`, numeric `price`, and non-empty `currency`.
    Evidence: .sisyphus/evidence/task-6-price-check.json

  Scenario: Low-support lookup stays explicit and non-fake
    Tool: Bash
    Steps: Call the same route with a thin-support clipboard fixture and save output to `.sisyphus/evidence/task-6-price-check-fallback.json`
    Expected: Saved JSON has `comparables: []` and a non-empty `fallbackReason`; it does not invent placeholder comparables.
    Evidence: .sisyphus/evidence/task-6-price-check-fallback.json
  ```

  **Commit**: YES | Message: `feat(api): return real price-check comparables` | Files: [`poe_trade/api/ops.py`, `poe_trade/api/ml.py`, `poe_trade/ml/workflows.py`, `tests/unit`, `frontend/src/components/tabs/PriceCheckTab.tsx`, `frontend/src/services/api.test.ts`, `frontend/src/types/api.ts`]

- [ ] 7. Surface deployment revisions in API/UI and invalidate stale recommendation rows on version changes

  **What to do**: Add explicit deploy metadata plumbing for backend Git SHA, frontend build SHA, and recommendation contract version. Extend backend settings/env handling so `/api/v1/ops/contract` and `dashboard_payload()` return a single backend-owned `deployment` object with backend version/SHA, frontend build SHA, recommendation contract version, and a deterministic match state. Inject frontend build metadata through Vite `VITE_*` env vars and render a visible homepage banner in `frontend/src/pages/Index.tsx` with a stable selector. Add scanner startup/deploy invalidation logic that deletes or excludes stale rows from both `poe_trade.scanner_recommendations` and `poe_trade.scanner_alert_log` whenever `recommendation_contract_version` or `producer_version` changes. Update runbook/docs with the out-of-repo HTML `Cache-Control: no-cache` requirement.
  **Must NOT do**: Do not change the dashboard’s five-service summary semantics, do not leave stale alert-log cooldown rows active across contract bumps, and do not hide frontend/backend SHA mismatches.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: backend settings, API, scanner invalidation, frontend shell, and runbook changes must land together.
  - Skills: [`docs-specialist`] - Use for minimal, accurate ops/runbook diffs once the runtime contract is defined.
  - Omitted: [`protocol-compat`] - Core schema shape is already established; this task is rollout/invalidation and UI surfacing.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: final deployment parity verification | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/api/ops.py` - Current ops contract payload and dashboard summary implementation.
  - Pattern: `poe_trade/api/app.py` - Route registration for `/api/v1/ops/contract` and `/api/v1/ops/dashboard`.
  - Pattern: `poe_trade/config/settings.py` - Shared env parsing path; new env vars must be wired here with tests.
  - Pattern: `poe_trade/services/scanner_worker.py` - Scanner startup loop and the best place to enforce stale-row cleanup before new cycles.
  - Pattern: `poe_trade/__init__.py` and `pyproject.toml` - Existing backend version sources.
  - Pattern: `frontend/src/pages/Index.tsx` - Current homepage header with no version banner.
  - Pattern: `frontend/src/services/api.ts` - Current `/api/v1/ops/contract` fetch/caching behavior.
  - Pattern: `frontend/package.json` - Current placeholder frontend version.
  - Test: `tests/unit/test_api_ops_analytics.py` - Dashboard summary lock and scanner payload behavior.
  - Test: `tests/unit/test_settings_aliases.py` - Env/config regression patterns.
  - Test: `frontend/src/test/playwright/happy.spec.ts` - Existing top-level page smoke patterns.
  - External: `https://github.com/vitejs/vite/blob/f8c8fd154fd32bb7ed17e35e31836648532a2128/docs/guide/env-and-mode.md` - Safe `VITE_*` metadata injection.
  - External: `https://github.com/vitejs/vite/blob/f8c8fd154fd32bb7ed17e35e31836648532a2128/docs/guide/build.md` - HTML no-cache guidance after deploy.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `.venv/bin/pytest tests/unit/test_api_ops_analytics.py tests/unit/test_settings_aliases.py` passes with assertions for deployment metadata fields, five-service summary preservation, and stale-row invalidation behavior.
  - [ ] `npm --prefix frontend run test` passes with assertions for banner/rendered metadata and contract fetch behavior.
  - [ ] `curl -s -H "Authorization: Bearer qa-operator-token" http://127.0.0.1:18080/api/v1/ops/contract` returns non-empty backend/frontend SHA values plus recommendation contract version and match status.
  - [ ] Playwright against the QA frontend shows `[data-testid="deployment-contract-banner"]` on the homepage and displays mismatch state without breaking tab navigation.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```bash
  Scenario: API and homepage expose matching deployment metadata
    Tool: Playwright
    Steps: Start QA stack and frontend; visit `/`; capture the banner `[data-testid="deployment-contract-banner"]`; fetch `/api/v1/ops/contract`; save screenshots/JSON to `.sisyphus/evidence/task-7-deployment-banner.png` and `.sisyphus/evidence/task-7-ops-contract.json`
    Expected: Banner is visible; API payload contains the same backend/frontend SHA pair and contract version shown in the UI; five-service summary cards still render.
    Evidence: .sisyphus/evidence/task-7-ops-contract.json

  Scenario: SHA mismatch warns but stale rows are excluded
    Tool: Bash
    Steps: Seed one stale recommendation row with an old contract/producer version in QA, start scanner worker cleanup path, then call `/api/v1/ops/scanner/recommendations` and `/api/v1/ops/contract`; save outputs to `.sisyphus/evidence/task-7-stale-filter.json` and `.sisyphus/evidence/task-7-sha-mismatch.json`
    Expected: Old-version rows are absent from the recommendations payload and the contract/banner surface an explicit mismatch state instead of hiding it.
    Evidence: .sisyphus/evidence/task-7-stale-filter.json
  ```

  **Commit**: YES | Message: `feat(ops): expose deployed revisions and invalidate stale recommendations` | Files: [`poe_trade/config/settings.py`, `poe_trade/api/ops.py`, `poe_trade/api/app.py`, `poe_trade/services/scanner_worker.py`, `tests/unit/test_api_ops_analytics.py`, `tests/unit/test_settings_aliases.py`, `frontend/src/pages/Index.tsx`, `frontend/src/services/api.ts`, `frontend/src/test/playwright/happy.spec.ts`, `docs/ops-runbook.md`, `README.md`]

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit - oracle
- [ ] F2. Code Quality Review - unspecified-high
- [ ] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check - deep

## Commit Strategy
- `test(contract): lock recommendation and deployment metadata expectations`
- `feat(schema): add item feature extraction layer`
- `feat(schema): add non-bulk family reference marts`
- `refactor(strategy): migrate non-bulk packs to feature-aware candidates`
- `feat(scanner): unify ml anomaly candidates with scanner recommendations`
- `feat(api): return real price-check comparables`
- `feat(ops): expose deployed revisions and invalidate stale recommendations`

## Success Criteria
- Non-bulk strategies emit listing-level candidates with `item_name`, `search_hint`, `max_buy`, and feature-specific evidence.
- No non-bulk strategy candidate/discover SQL depends only on `category`/`base_type` aggregates from `poe_trade.gold_listing_ref_hour`.
- `/api/v1/ops/scanner/recommendations` can page through both SQL and ML opportunities under one contract without mixed-version stale rows.
- Live-facing contract/API responses expose deployment/build metadata that the frontend renders and compares consistently.
- Price-check responses return real comparables for supported items and a deterministic fallback reason for low-support requests.
