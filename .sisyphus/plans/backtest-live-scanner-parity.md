# Unify Backtest and Live Scanner Candidate Parity

## TL;DR
> **Summary**: Replace the split `discover.sql`/`backtest.sql` runtime with one canonical per-strategy `candidate.sql` contract, then route scanner and backtest through the same typed policy helpers so both paths emit the same eligible keys and counts for the same snapshot.
> **Deliverables**:
> - Canonical `candidate.sql` contract for every strategy pack
> - Explicit scanner-safe `discover.sql` bridge contracts for enabled non-journal strategies until the final scanner cutover lands
> - Shared Python policy layer for league, minima, `requires_journal`, cooldown, dedupe, and evidence shaping
> - Scanner/backtest parity tests, seeded QA fixtures, and refreshed non-dry-run evidence
> **Effort**: Large
> **Parallel**: YES - 4 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 6 -> Tasks 3/4/5 -> Tasks 7/8 -> Tasks 9/10

## Context
### Original Request
P0 — backtests and the live scanner are still evaluating different logic. `run_backtest()` inserts rows from `backtest.sql` directly into `research_backtest_detail`, and `backtest.py` does not reference `min_expected_profit_chaos`, `min_confidence`, or `requires_journal`. Meanwhile, the live scanner uses `discover.sql` plus runtime minima filters. Example: `bulk_essence/backtest.sql` computes `expected_profit_chaos`, `expected_roi`, and `confidence`, but the live scanner reads a different contract from `discover.sql`. So backtests are not validating the same logic that production uses. The committed Mirage 14-day artifact is also still all zero rows, which means the current backtest output has not yet demonstrated working parity with the live path.

### Interview Summary
- Exploration confirmed the report: `poe_trade/strategy/backtest.py` consumes `backtest.sql`, applies only league/lookback filtering, and writes raw rows to `poe_trade.research_backtest_detail`, while `poe_trade/strategy/scanner.py` consumes `discover.sql`, applies minima at runtime, skips `requires_journal` packs, and applies cooldown only when writing `poe_trade.scanner_alert_log`.
- All 14 `poe_trade/sql/strategy/*/discover.sql` files are raw `SELECT *`, while all 14 paired `backtest.sql` files already emit typed candidate metrics.
- `poe_trade/strategy/registry.py` already centralizes minima, cooldown, and journal metadata, so policy drift should be eliminated by sharing helpers rather than duplicating config parsing.
- Existing evidence is stale for parity purposes: `backtest_latest_results_mirage_14d.tsv` is all zero-row, `backtest_run_ids_all.tsv` has only run IDs/statuses, and `.sisyphus/evidence/task-backtest-all-command.txt` is dry-run only.

### Metis Review (gaps addressed)
- Cooldown parity is defined against candidate snapshot time (`time_bucket`), not insert time, to keep backtest replay deterministic.
- `item_or_market_key` must become a stable semantic contract, but scanner cooldown checks need a compatibility window so a semantic-key cutover does not blindly reopen recently-alerted hashed rows.
- `no_data` vs `no_opportunities` must be derived from the shared candidate pipeline, not from regex source-table extraction.
- Journal-gated packs stay parity-safe by using the same hard gate in both paths for this change; without seeded journal state they emit zero eligible candidates and backtests summarize them as policy-rejected opportunities rather than introducing a new persisted status.
- Imported scanner-discover tasks are preserved here as explicit bridge work: enabled `discover.sql` files must stop using raw `SELECT *` and current scanner tests must lock the direct-column contract until the final `candidate.sql` cutover lands.
- Scope is frozen to candidate contract unification, shared policy parity, deterministic QA/evidence, and documentation refresh. No UI redesign, no historical backfill, no speculative SQL framework.

## Work Objectives
### Core Objective
Make scanner and backtest consume the same normalized per-strategy candidate contract and the same typed policy rules so both paths produce the same eligible `item_or_market_key` set and count for a fixed strategy, league, and snapshot window.

### Deliverables
- New canonical `candidate.sql` file for every strategy pack under `poe_trade/sql/strategy/<strategy_id>/`
- Enabled non-journal `discover.sql` files emit explicit scanner-contract aliases instead of raw `SELECT *` while scanner still consumes them during transition
- Shared runtime helpers for loading candidates and applying league, minima, `requires_journal`, dedupe, cooldown, and evidence shaping
- Scanner updated to persist only post-policy eligible candidates in `poe_trade.scanner_recommendations`
- Backtest updated to replay the same policy over historical candidate rows and persist only post-policy eligible rows in `poe_trade.research_backtest_detail`
- Deterministic unit and QA evidence proving scanner/backtest key parity and count parity
- Refreshed package-local QA/evidence outputs that no longer rely on dry-run or zero-row parity placeholders

### Definition of Done (verifiable conditions with commands)
- All strategy packs expose canonical candidate contracts and contract tests pass:
  - `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py -q`
- Enabled non-journal `discover.sql` bridge queries no longer use raw `SELECT *` and expose the scanner contract aliases required by the current scanner path.
- Scanner runtime-filter SQL no longer depends on JSON extraction for required metrics (`expected_profit_chaos`, `expected_roi`, `confidence`) and supports `bulk_listing_count` for sample-count compatibility while preserving optional descriptive fallbacks only as legacy safety.
- Scanner and backtest parity tests pass with deterministic keys, cooldown timing, journal gating, and league scoping:
  - `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_strategy_backtest.py tests/unit/test_cli_scan.py tests/unit/test_cli_research.py -q`
- QA fixtures seed non-zero candidate data and package-local parity evidence is reproducible:
  - `.venv/bin/python -m poe_trade.qa_contract seed --output poe_trade/evidence/qa/seed.json`
  - `.venv/bin/python -m poe_trade.evidence_bundle`
  - `.venv/bin/python -m poe_trade.cli scan plan --league Mirage --limit 20`
  - `.venv/bin/python -m poe_trade.cli research backtest --strategy bulk_essence --league Mirage --days 14`
- Same-snapshot keys match after policy is applied:
  - `clickhouse-client --query "SELECT arraySort(groupArray(item_or_market_key)) FROM poe_trade.scanner_recommendations WHERE scanner_run_id = '<scanner_run_id>'"`
  - `clickhouse-client --query "SELECT arraySort(groupArray(item_or_market_key)) FROM poe_trade.research_backtest_detail WHERE run_id = '<backtest_run_id>'"`
- Refreshed package-local evidence is non-dry-run and no longer empty/placeholder-only:
  - `.venv/bin/python -m poe_trade.evidence_bundle`

### Must Have
- One canonical SQL contract per strategy pack, used by both scanner and backtest runtime
- One shared typed policy layer for league, minima, journal gate, cooldown, dedupe, and evidence serialization
- Stable semantic `item_or_market_key` values supplied by candidate contracts
- Deterministic parity proof based on seeded non-zero data and exact key-array comparisons
- Compatibility-safe cooldown lookup during key migration so recent hashed alert history is not ignored

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No schema migration unless implementation proves parity cannot be achieved with existing tables
- No API payload shape redesign and no CLI output shape redesign
- No continued runtime dependence on raw `SELECT *` `discover.sql` files
- No regex source-table parsing for backtest status classification
- No parity claim based on current dry-run or zero-row Mirage artifacts
- No historical backfill of old alert/backtest rows in this pass
- No deletion campaign for legacy `discover.sql`/`backtest.sql` files during this parity fix; mark them legacy in docs instead

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after with deterministic unit coverage plus seeded QA CLI verification
- QA policy: Every task includes agent-executed happy-path and failure-path checks
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: parity tests, discover-contract guards, registry wiring, and shared policy primitives
Wave 2: per-mart-family `candidate.sql` authoring plus enabled-strategy `discover.sql` bridge rewrites
Wave 3: scanner/backtest runtime cutover to the canonical candidate pipeline with explicit discover-column compatibility during transition
Wave 4: seeded QA parity evidence, docs refresh, and artifact refresh

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 6, 7, 8, 9, 10
- Task 2 blocks Tasks 3, 4, 5, 7, 8
- Task 3 blocks Tasks 7, 8
- Task 4 blocks Tasks 7, 8
- Task 5 blocks Tasks 7, 8
- Task 6 blocks Tasks 7, 8, 9
- Task 7 blocks Tasks 9, 10
- Task 8 blocks Tasks 9, 10
- Task 9 blocks Task 10 and the final verification wave
- Task 10 blocks the final verification wave

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 -> 3 tasks -> `quick`, `deep`, `unspecified-low`
- Wave 2 -> 3 tasks -> `quick`, `unspecified-low`
- Wave 3 -> 2 tasks -> `deep`, `unspecified-high`
- Wave 4 -> 2 tasks -> `writing`, `unspecified-low`
- Final Verification -> 4 tasks -> `oracle`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Lock the parity contract with deterministic tests first

  **What to do**: Add failing tests that define the canonical candidate contract and exact parity expectations before changing runtime code. Cover registry discovery of canonical SQL, enabled-only discover-contract guards (`SELECT *` rejection plus required aliases), scanner direct-column filter assertions, `bulk_listing_count` sample compatibility, source-provided `item_or_market_key` preference, typed minima boundaries, league scoping, cooldown replay by timestamp, journal-gated zero-eligibility behavior, semantic key stability, populated API/CLI recommendation fields, and same-snapshot key/count parity between scanner and backtest for seeded rows.
  **Must NOT do**: Do not refactor production runtime in this task, and do not use Mirage dry-run or zero-row artifacts as proof fixtures.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: test-only changes with explicit fixture assertions and no production behavior edits.
  - Skills: `[]` — No extra skill required.
  - Omitted: [`protocol-compat`] — No schema evolution in this task.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 7, 8, 9, 10] | Blocked By: []

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `tests/unit/test_strategy_registry.py:80` — Existing shared backtest-contract assertion; mirror this style for canonical candidate contracts.
  - Pattern: `tests/unit/test_strategy_scanner.py` — Existing query/assertion coverage for scanner SQL and cooldown behavior.
  - Pattern: `tests/unit/test_strategy_backtest.py` — Existing status and insert-path tests to extend with parity scenarios.
  - Pattern: `tests/unit/test_api_ops_analytics.py:240` — Existing recommendation payload fixture/output assertions to extend with populated-field regressions.
  - Pattern: `tests/unit/test_cli_scan.py` — Existing scanner CLI dry-run and output-shape assertions.
  - Pattern: `tests/unit/test_cli_research.py` — Existing backtest CLI dry-run and summary contract assertions.
  - API/Type: `poe_trade/strategy/registry.py` — Current source of minima, cooldown, and `requires_journal` metadata.
  - API/Type: `poe_trade/strategy/scanner.py:29` — Current scanner insert SQL and JSON-based minima path to lock down with tests.
  - API/Type: `poe_trade/api/ops.py:239` — Recommendation payload/search shaping that must stay populated after the scanner contract shift.
  - API/Type: `poe_trade/cli.py:443` — CLI scan output contract that depends on populated recommendation fields.

  **Acceptance Criteria** (agent-executable only):
  - [x] New/updated tests define the canonical candidate columns and exact parity expectations using concrete fixture keys and timestamps.
  - [x] `tests/unit/test_strategy_registry.py` rejects raw `SELECT *` discover queries and missing required aliases for enabled non-journal strategies while preserving existing backtest-contract assertions.
  - [x] `tests/unit/test_strategy_scanner.py` asserts direct `source.` column usage for required metrics, `bulk_listing_count` sample compatibility, source-provided `item_or_market_key` preference, and legacy fallback behavior only for optional descriptive fields.
  - [x] API and CLI regression tests explicitly cover populated recommendation metrics and descriptive fields, including semantic/search output, after the scanner contract shift.
  - [x] Test coverage includes minima boundary values, cross-league filtering, cooldown suppression at `+179m` vs `+181m`, duplicate semantic-key tie-breaks, and `requires_journal` rejection with empty journal state.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py tests/unit/test_strategy_backtest.py tests/unit/test_cli_scan.py tests/unit/test_cli_research.py -q` exits 0 after the rest of the plan lands.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Deterministic parity tests pass
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py tests/unit/test_strategy_backtest.py tests/unit/test_cli_scan.py tests/unit/test_cli_research.py -q`
    Expected: Exit code 0; parity-specific tests pass for keys, counts, cooldown timing, journal gating, and league scoping.
    Evidence: .sisyphus/evidence/task-1-parity-tests.txt

  Scenario: Failure path proves policy rejection
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_policy.py tests/unit/test_strategy_backtest.py -q -k "journal or minima or no_opportunities"`
    Expected: Exit code 0; exact-boundary minima and empty-journal fixtures prove candidates are rejected without producing false `no_data`.
    Evidence: .sisyphus/evidence/task-1-parity-tests-negative.txt

  Scenario: Scanner bridge-contract tests stay explicit
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py tests/unit/test_api_ops_analytics.py tests/unit/test_cli_scan.py -q`
    Expected: Exit code 0; enabled discover-contract assertions, direct-column scanner assertions, and populated API/CLI consumer regressions all pass together.
    Evidence: .sisyphus/evidence/task-1-scanner-bridge-tests.txt
  ```

  **Commit**: YES | Message: `test(strategy): codify candidate contract and parity fixtures` | Files: [`tests/unit/test_strategy_registry.py`, `tests/unit/test_strategy_policy.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_strategy_backtest.py`, `tests/unit/test_cli_scan.py`, `tests/unit/test_cli_research.py`]

- [x] 2. Add canonical candidate contract loading to strategy registry/runtime

  **What to do**: Extend strategy pack discovery so canonical SQL lives at `poe_trade/sql/strategy/<strategy_id>/candidate.sql` and runtime code can load it explicitly. Add a dedicated loader/helper instead of spreading path logic between scanner and backtest. Keep legacy `discover.sql`/`backtest.sql` files on disk for reference only, but stop treating them as the business-logic source of truth.
  **Must NOT do**: Do not introduce Python SQL code generation, and do not delete legacy SQL files in this task.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` — Reason: small runtime API shape change touching registry and shared loading helpers.
  - Skills: `[]` — No special skill required.
  - Omitted: [`protocol-compat`] — No schema change required.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [3, 4, 5, 7, 8] | Blocked By: []

  **References** (executor has NO interview context — be exhaustive):
  - API/Type: `poe_trade/strategy/registry.py` — Strategy pack path resolution and metadata loading live here.
  - Pattern: `tests/unit/test_strategy_registry.py:6` — Existing discovery assertions for pack ordering, enabled flags, and SQL path existence.
  - API/Type: `poe_trade/strategy/scanner.py` — Current loader/consumer of `discover.sql`.
  - API/Type: `poe_trade/strategy/backtest.py` — Current loader/consumer of `backtest.sql`.
  - External: `https://github.com/dbt-labs/dbt-metrics/blob/d59d3b0272125ad1b2d8d5bf2972920755cf64b3/macros/get_metric_sql.sql` — Example of centralized SQL source reused by multiple consumers.
  - External: `https://github.com/ClickHouse/clickhouse-docs/blob/0b10411b4e857edbc018ff31346494d8fdb080e2/docs/materialized-view/incremental-materialized-view.md#L1098-L1186` — ClickHouse CTEs are inlined, so `candidate.sql` is a readability/reuse contract, not a materialized cache.

  **Acceptance Criteria** (agent-executable only):
  - [x] Strategy discovery exposes canonical candidate SQL paths and a shared loader function used by both runtime consumers.
  - [x] Runtime code no longer has to decide separately between `discover.sql` and `backtest.sql` when loading strategy business logic.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_registry.py -q` exits 0 with explicit assertions for `candidate.sql` path discovery.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Canonical contract path discovery passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py -q`
    Expected: Exit code 0; tests prove every pack resolves a canonical `candidate.sql` path.
    Evidence: .sisyphus/evidence/task-2-candidate-loader.txt

  Scenario: Legacy files are no longer the runtime source of truth
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py -q -k candidate`
    Expected: Exit code 0; targeted assertions prove runtime wiring references `candidate.sql` instead of splitting logic across `discover.sql`/`backtest.sql`.
    Evidence: .sisyphus/evidence/task-2-candidate-loader-negative.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): add candidate contract loading` | Files: [`poe_trade/strategy/registry.py`, `poe_trade/strategy/scanner.py`, `poe_trade/strategy/backtest.py`, `tests/unit/test_strategy_registry.py`]

- [x] 3. Author canonical candidate contracts for bulk-premium strategies

  **What to do**: Create canonical `candidate.sql` files for `bulk_essence`, `bulk_fossils`, `fossil_scarcity`, and `scarab_reroll` using the existing derived formulas from their paired `backtest.sql` files. Emit explicit columns for `time_bucket`, `league`, `item_or_market_key`, `expected_profit_chaos`, `expected_roi`, `confidence`, canonical `sample_count`, descriptive scanner fields, and evidence-supporting source columns. In the same task, rewrite the enabled bulk `discover.sql` files (`bulk_essence`, `bulk_fossils`) so the current scanner path no longer relies on raw `SELECT *` and instead emits the same scanner-contract aliases while Task 7 is pending.
  **Must NOT do**: Do not use `SELECT *`, do not keep hashed-key dependencies, do not silently alter formulas beyond explicit column naming and evidence-field exposure, and do not touch disabled bulk packs in the discover rewrite portion.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: one mart family with closely related formulas and low coordination cost.
  - Skills: `[]` — No special skill required.
  - Omitted: [`protocol-compat`] — Existing marts already expose the needed columns.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [7, 8] | Blocked By: [2]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/sql/strategy/bulk_essence/backtest.sql` — Canonical formula source for essence bulk spread metrics.
  - Pattern: `poe_trade/sql/strategy/bulk_fossils/backtest.sql` — Canonical formula source for fossil bulk spread metrics.
  - Pattern: `poe_trade/sql/strategy/fossil_scarcity/backtest.sql` — Canonical formula source for scarcity metrics.
  - Pattern: `poe_trade/sql/strategy/scarab_reroll/backtest.sql` — Canonical formula source for scarab reroll metrics.
  - Pattern: `poe_trade/sql/strategy/bulk_essence/discover.sql` — Current raw-source anti-pattern to replace as business-logic authority.
  - API/Type: `schema/migrations/0027_gold_reference_marts.sql:43` — Available bulk-premium mart columns.
  - Pattern: `strategies/bulk_essence/strategy.toml` — Example minima/sample-count/cooldown metadata that the typed candidate columns must satisfy.

  **Acceptance Criteria** (agent-executable only):
  - [x] Canonical candidate SQL exists for all four bulk-premium strategies and exposes explicit typed contract columns with no `SELECT *`.
  - [x] Candidate SQL includes stable semantic keys and scanner-facing descriptive fields needed for downstream evidence/search hints.
  - [x] `poe_trade/sql/strategy/bulk_essence/discover.sql` and `poe_trade/sql/strategy/bulk_fossils/discover.sql` expose explicit scanner-contract aliases, alias `bulk_listing_count` to `sample_count`, and provide non-fallback `why_it_fired`, `buy_plan`, and `exit_plan` strings.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py -q` exits 0 after the files are added.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Bulk candidate contracts pass registry checks
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py -q`
    Expected: Exit code 0; bulk strategy candidate files satisfy canonical contract tests.
    Evidence: .sisyphus/evidence/task-3-bulk-candidates.txt

  Scenario: Bulk minima rejection stays deterministic
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_policy.py -q -k "bulk and minima"`
    Expected: Exit code 0; bulk fixture rows below threshold are rejected while exact-boundary rows survive.
    Evidence: .sisyphus/evidence/task-3-bulk-candidates-negative.txt

  Scenario: Bulk discover bridge contract passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_backtest.py tests/unit/test_strategy_scanner.py -q -k "discover or bulk"`
    Expected: Exit code 0; enabled bulk discover files satisfy the scanner-contract assertions and scanner bulk sample compatibility remains covered.
    Evidence: .sisyphus/evidence/task-3-bulk-discover-bridge.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): add canonical bulk candidate contracts` | Files: [`poe_trade/sql/strategy/bulk_essence`, `poe_trade/sql/strategy/bulk_fossils`, `poe_trade/sql/strategy/fossil_scarcity`, `poe_trade/sql/strategy/scarab_reroll`]

- [x] 4. Author canonical candidate contracts for listing-based strategies

  **What to do**: Create canonical `candidate.sql` files for `advanced_rare_finish`, `cluster_basic`, `corruption_ev`, `dump_tab_reprice`, `flask_basic`, `high_dim_jewels`, and `rog_basic`, using their current `backtest.sql` formulas as the source of truth. Expose explicit typed columns, stable semantic keys, scanner descriptive fields, and evidence-supporting source fields from `poe_trade.gold_listing_ref_hour`. In the same task, rewrite enabled listing `discover.sql` files (`cluster_basic`, `flask_basic`) with explicit scanner-contract aliases, `listing_count AS sample_count`, stable keys, and non-fallback descriptive fields while the current scanner path still uses them.
  **Must NOT do**: Do not keep raw `SELECT *` behavior, do not collapse multiple strategy formulas into one generic SQL file, do not redesign pricing logic beyond the canonical contract extraction, and do not change disabled listing strategies in the discover rewrite portion.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` — Reason: seven related SQL contracts sharing one mart family but different formulas and keys.
  - Skills: `[]` — No special skill required.
  - Omitted: [`protocol-compat`] — Existing listing mart columns are sufficient.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [7, 8] | Blocked By: [2]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/sql/strategy/advanced_rare_finish/backtest.sql` — Existing advanced-rare derived metrics.
  - Pattern: `poe_trade/sql/strategy/cluster_basic/backtest.sql` — Existing cluster-jewel derived metrics.
  - Pattern: `poe_trade/sql/strategy/corruption_ev/backtest.sql` — Existing corruption derived metrics.
  - Pattern: `poe_trade/sql/strategy/dump_tab_reprice/backtest.sql` — Existing dump-tab repricing metrics.
  - Pattern: `poe_trade/sql/strategy/flask_basic/backtest.sql` — Existing flask-derived metrics.
  - Pattern: `poe_trade/sql/strategy/high_dim_jewels/backtest.sql` — Existing journal-gated jewel metrics.
  - Pattern: `poe_trade/sql/strategy/rog_basic/backtest.sql` — Existing Rog-derived metrics.
  - API/Type: `schema/migrations/0027_gold_reference_marts.sql:16` — Listing mart column availability.
  - Pattern: `strategies/high_dim_jewels/strategy.toml` — Example journal-gated listing strategy metadata.

  **Acceptance Criteria** (agent-executable only):
  - [x] Canonical candidate SQL exists for all seven listing strategies and exposes explicit typed contract columns with no `SELECT *`.
  - [x] Journal-gated listing packs still expose the same candidate contract even though later policy gates may reject them.
  - [x] `poe_trade/sql/strategy/cluster_basic/discover.sql` and `poe_trade/sql/strategy/flask_basic/discover.sql` emit explicit scanner-contract aliases, alias `listing_count AS sample_count`, and populate non-fallback descriptive strings.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py -q` exits 0 after the files are added.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Listing candidate contracts pass registry checks
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py -q`
    Expected: Exit code 0; all listing strategy candidate files satisfy canonical contract tests.
    Evidence: .sisyphus/evidence/task-4-listing-candidates.txt

  Scenario: Journal-gated listing contracts remain policy-testable
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_policy.py -q -k "journal or listing"`
    Expected: Exit code 0; journal-gated listing candidates remain loadable and are rejected by policy only when journal state is absent.
    Evidence: .sisyphus/evidence/task-4-listing-candidates-negative.txt

  Scenario: Enabled listing discover bridge contract passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_backtest.py tests/unit/test_strategy_scanner.py -q -k "listing or sample_count"`
    Expected: Exit code 0; enabled listing discover files satisfy the scanner bridge contract and scanner tests continue to accept `sample_count` aliases.
    Evidence: .sisyphus/evidence/task-4-listing-discover-bridge.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): add canonical listing candidate contracts` | Files: [`poe_trade/sql/strategy/advanced_rare_finish`, `poe_trade/sql/strategy/cluster_basic`, `poe_trade/sql/strategy/corruption_ev`, `poe_trade/sql/strategy/dump_tab_reprice`, `poe_trade/sql/strategy/flask_basic`, `poe_trade/sql/strategy/high_dim_jewels`, `poe_trade/sql/strategy/rog_basic`]

- [x] 5. Author canonical candidate contracts for set and currency strategies

  **What to do**: Create canonical `candidate.sql` files for `fragment_sets`, `map_logbook_packages`, and `cx_market_making`, preserving their existing formulas while exposing the same typed contract used everywhere else. Include canonical `sample_count`, stable semantic keys, and scanner-facing descriptive/evidence fields. In the same task, rewrite enabled set `discover.sql` files (`fragment_sets`, `map_logbook_packages`) so they emit explicit scanner-contract aliases, `listing_count AS sample_count`, stable keys, and descriptive scanner text instead of relying on runtime defaults.
  **Must NOT do**: Do not leave category-dependent ambiguity in the key contract, do not introduce a separate currency-only policy path, and do not add new marts, views, or schema changes in the discover rewrite portion.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: three remaining strategy families with compact formulas and clear existing backtest logic.
  - Skills: `[]` — No special skill required.
  - Omitted: [`protocol-compat`] — No schema change required.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [7, 8] | Blocked By: [2]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/sql/strategy/fragment_sets/backtest.sql` — Existing set-assembly metrics.
  - Pattern: `poe_trade/sql/strategy/map_logbook_packages/backtest.sql` — Existing map/logbook package metrics.
  - Pattern: `poe_trade/sql/strategy/cx_market_making/backtest.sql` — Existing currency exchange metrics.
  - Pattern: `poe_trade/sql/strategy/fragment_sets/discover.sql` — Current raw-source anti-pattern.
  - Pattern: `poe_trade/sql/strategy/map_logbook_packages/discover.sql` — Current raw-source anti-pattern.
  - Pattern: `poe_trade/sql/strategy/cx_market_making/discover.sql` — Current raw-source anti-pattern.
  - API/Type: `schema/migrations/0027_gold_reference_marts.sql:1` — Currency mart column availability.
  - API/Type: `schema/migrations/0027_gold_reference_marts.sql:58` — Set mart column availability.

  **Acceptance Criteria** (agent-executable only):
  - [x] Canonical candidate SQL exists for the remaining set/currency strategies with explicit typed columns and stable semantic keys.
  - [x] `poe_trade/sql/strategy/fragment_sets/discover.sql` and `poe_trade/sql/strategy/map_logbook_packages/discover.sql` emit explicit scanner-contract aliases, alias `listing_count AS sample_count`, and provide non-fallback descriptive strings.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py -q` exits 0 after the files are added.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Set and currency candidate contracts pass registry checks
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_policy.py -q`
    Expected: Exit code 0; the remaining strategy packs satisfy canonical contract tests.
    Evidence: .sisyphus/evidence/task-5-set-currency-candidates.txt

  Scenario: Currency/set key semantics stay deterministic
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_policy.py -q -k "currency or set or semantic"`
    Expected: Exit code 0; tests prove semantic keys and sample-count fields are deterministic for non-listing marts.
    Evidence: .sisyphus/evidence/task-5-set-currency-candidates-negative.txt

  Scenario: Enabled set discover bridge contract passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_backtest.py tests/unit/test_api_ops_analytics.py tests/unit/test_cli_scan.py -q -k "set or scanner"`
    Expected: Exit code 0; enabled set discover files satisfy scanner-contract assertions and downstream search/semantic output remains populated.
    Evidence: .sisyphus/evidence/task-5-set-discover-bridge.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): add canonical set and currency candidate contracts` | Files: [`poe_trade/sql/strategy/fragment_sets`, `poe_trade/sql/strategy/map_logbook_packages`, `poe_trade/sql/strategy/cx_market_making`]

- [x] 6. Implement shared typed policy helpers and compatibility-safe key handling

  **What to do**: Add a shared policy module that accepts parsed candidate rows and strategy metadata, then applies league filtering, minima, journal gating, deterministic dedupe, cooldown replay by candidate timestamp, and evidence snapshot shaping. Define the stable semantic `item_or_market_key` contract and add a compatibility lookup so scanner cooldown checks consider recent legacy hashed keys during the cutover window. Keep the helpers pure and unit-testable.
  **Must NOT do**: Do not leave minima or cooldown logic split between raw SQL strings and Python JSON extraction, and do not hard-code strategy-specific policy outside metadata and canonical candidate rows.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: this is the core parity abstraction and carries the highest regression risk.
  - Skills: `[]` — No special skill required.
  - Omitted: [`protocol-compat`] — Additive logic change only unless implementation proves otherwise.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [7, 8, 9] | Blocked By: [1]

  **References** (executor has NO interview context — be exhaustive):
  - API/Type: `poe_trade/strategy/scanner.py` — Current runtime minima, hash-key creation, and cooldown split.
  - API/Type: `poe_trade/strategy/backtest.py` — Current league/lookback-only filtering and status classification.
  - API/Type: `poe_trade/strategy/registry.py` — Metadata source for minima, cooldown, and journal gate.
  - API/Type: `poe_trade/strategy/alerts.py` — Downstream alert identity depends on `item_or_market_key`.
  - API/Type: `poe_trade/strategy/journal.py` — Journal flows also depend on `item_or_market_key`.
  - External: `https://github.com/ClickHouse/clickhouse-docs/blob/0b10411b4e857edbc018ff31346494d8fdb080e2/docs/guides/developer/stored-procedures-and-prepared-statements.md#L411-L826` — Favor typed parameters and canonical query bodies over string-spliced logic.

  **Acceptance Criteria** (agent-executable only):
  - [x] One shared helper layer applies league, minima, journal gate, cooldown, dedupe, and evidence shaping for both scanner and backtest.
  - [x] Cooldown evaluation uses candidate timestamps rather than insert time.
  - [x] Compatibility logic exists so recent hashed alert keys are still recognized during semantic-key cutover.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py tests/unit/test_strategy_backtest.py -q` exits 0.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Shared policy helper tests pass
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py tests/unit/test_strategy_backtest.py -q`
    Expected: Exit code 0; one helper layer proves minima, cooldown, dedupe, and journal gate parity.
    Evidence: .sisyphus/evidence/task-6-policy-helpers.txt

  Scenario: Legacy-key compatibility stays covered
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_scanner.py -q -k "legacy or cooldown or semantic"`
    Expected: Exit code 0; tests prove a recent hashed alert record still suppresses a semantically equivalent candidate during cutover.
    Evidence: .sisyphus/evidence/task-6-policy-helpers-negative.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): add shared policy helpers` | Files: [`poe_trade/strategy`, `tests/unit/test_strategy_policy.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_strategy_backtest.py`]

- [x] 7. Route live scanner through the canonical candidate pipeline

  **What to do**: Refactor `poe_trade/strategy/scanner.py` so it loads canonical candidate rows, applies the shared policy helpers, and inserts only post-policy eligible rows into `poe_trade.scanner_recommendations`. During the transition, keep current enabled `discover.sql` bridge contracts compatible by requiring explicit discover columns for `expected_profit_chaos`, `expected_roi`, and `confidence`, sample-count compatibility across `source.sample_count`, `source.bulk_listing_count`, `source.listing_count`, and `source.observed_samples`, and source-provided `item_or_market_key` preference over the legacy hash path. Preserve downstream API/CLI payload fields by building `evidence_snapshot` from the canonical candidate row. Keep alert-log emission as a downstream side effect of already-eligible recommendations.
  **Must NOT do**: Do not leave JSON extraction as the source of required metrics, do not keep `cityHash64(source_row_json)` as the live identity, do not relabel cross-league raw rows as the requested league, and do not remove optional descriptive fallbacks except where the explicit discover/candidate contracts now supply them.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: core runtime change with downstream alert/API/CLI impact.
  - Skills: `[]` — No special skill required.
  - Omitted: [`docs-specialist`] — Documentation refresh belongs later.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [9, 10] | Blocked By: [1, 2, 3, 4, 5, 6]

  **References** (executor has NO interview context — be exhaustive):
  - API/Type: `poe_trade/strategy/scanner.py` — Current runtime path to replace.
  - API/Type: `schema/migrations/0029_scanner_tables.sql` — Scanner persistence contract must remain compatible.
  - API/Type: `poe_trade/strategy/alerts.py` — Alert dedupe/identity consumers.
  - API/Type: `poe_trade/api/ops.py:223` — Recommendation payload shaping depends on populated scanner fields.
  - API/Type: `poe_trade/cli.py:429` — `scan plan` reads `poe_trade.scanner_recommendations` and derives search hints from `evidence_snapshot`.
  - Pattern: `tests/unit/test_strategy_scanner.py` — Existing scanner query/behavior tests to update.
  - Pattern: `tests/unit/test_cli_scan.py` — Existing CLI contract tests to preserve.

  **Acceptance Criteria** (agent-executable only):
  - [x] Scanner uses canonical candidate SQL and shared policy helpers for eligibility decisions.
  - [x] Required scanner minima use explicit discover/candidate columns instead of JSON extraction for `expected_profit_chaos`, `expected_roi`, and `confidence`.
  - [x] Sample-count compatibility includes `bulk_listing_count` without regressing `sample_count`, `listing_count`, or `observed_samples` support.
  - [x] Scanner prefers source-provided `item_or_market_key` and retains `source_row_json` only for evidence/optional enrichment.
  - [x] `poe_trade.scanner_recommendations` contains only post-policy eligible rows for seeded parity fixtures.
  - [x] `evidence_snapshot` still carries the fields needed by API/CLI consumers.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_cli_scan.py tests/unit/test_api_ops_analytics.py -q` exits 0.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Scanner parity runtime passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_cli_scan.py tests/unit/test_api_ops_analytics.py -q`
    Expected: Exit code 0; scanner writes only eligible candidates and downstream payload/output contracts remain intact.
    Evidence: .sisyphus/evidence/task-7-scanner-cutover.txt

  Scenario: Cross-league and cooldown rejection stay covered
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_scanner.py -q -k "league or cooldown or alert"`
    Expected: Exit code 0; Mirage survives while Standard is filtered, and cooldown-suppressed rows do not become recommendations.
    Evidence: .sisyphus/evidence/task-7-scanner-cutover-negative.txt

  Scenario: Direct-column scanner contract path is exercised
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py tests/unit/test_strategy_backtest.py tests/unit/test_api_ops_analytics.py tests/unit/test_cli_scan.py -q -k "direct or item_or_market_key or bulk or scanner"`
    Expected: Exit code 0; direct-column filtering, stable-key preference, discover bridge contracts, API/CLI regressions, and bulk sample compatibility all pass together.
    Evidence: .sisyphus/evidence/task-7-scanner-direct-contract.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): route scanner through canonical candidate pipeline` | Files: [`poe_trade/strategy/scanner.py`, `poe_trade/strategy/alerts.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_cli_scan.py`, `tests/unit/test_api_ops_analytics.py`]

- [x] 8. Route backtests through the same canonical candidate pipeline

  **What to do**: Refactor `poe_trade/strategy/backtest.py` so it loads canonical candidate rows, replays the shared policy helpers over the lookback window, persists only post-policy eligible rows into `poe_trade.research_backtest_detail`, and computes `no_data` vs `no_opportunities` from explicit source/eligible counts instead of SQL-text regexes. Keep summary rows and CLI output shape stable, but allow gate-specific summary text for journal/minima/cooldown rejections.
  **Must NOT do**: Do not keep raw `backtest.sql` as the runtime logic source, do not use `_extract_source_table()` for status classification, and do not invent a new persisted status unless existing status values prove insufficient.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: stateful replay and status semantics make this riskier than a straight loader swap.
  - Skills: `[]` — No special skill required.
  - Omitted: [`protocol-compat`] — Existing backtest tables should remain sufficient.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [9, 10] | Blocked By: [1, 2, 3, 4, 5, 6]

  **References** (executor has NO interview context — be exhaustive):
  - API/Type: `poe_trade/strategy/backtest.py` — Current runtime path and regex source-table classification to replace.
  - API/Type: `schema/migrations/0031_research_backtest_summary_detail.sql` — Backtest persistence contract must remain compatible.
  - Pattern: `tests/unit/test_strategy_backtest.py` — Existing detail/summary status assertions.
  - Pattern: `tests/unit/test_cli_research.py` — Existing CLI dry-run and summary-output contract assertions.
  - Pattern: `backtest_latest_results_mirage_14d.tsv` — Current zero-row artifact proving the evidence gap this refactor must close.
  - Pattern: `backtest_run_ids_all.tsv` — Existing run-ID catalog that lacks parity counts.

  **Acceptance Criteria** (agent-executable only):
  - [x] Backtest runtime uses canonical candidate SQL and shared policy helpers.
  - [x] `no_data` is emitted only when source candidate rows are absent; policy-rejected rows produce `no_opportunities`.
  - [x] Journal-gated strategies without seeded journal state produce zero eligible rows and a gate-specific summary message while preserving existing status contracts.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_backtest.py tests/unit/test_cli_research.py -q` exits 0.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Backtest parity runtime passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_backtest.py tests/unit/test_cli_research.py -q`
    Expected: Exit code 0; backtest persists only eligible candidates and summary output remains contract-compatible.
    Evidence: .sisyphus/evidence/task-8-backtest-cutover.txt

  Scenario: no_data vs no_opportunities stays exact
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_strategy_backtest.py -q -k "no_data or no_opportunities or journal"`
    Expected: Exit code 0; empty-source fixtures return `no_data`, while policy-rejected fixtures return `no_opportunities` with gate-specific summary text.
    Evidence: .sisyphus/evidence/task-8-backtest-cutover-negative.txt
  ```

  **Commit**: YES | Message: `refactor(strategy): route backtest through canonical candidate pipeline` | Files: [`poe_trade/strategy/backtest.py`, `tests/unit/test_strategy_backtest.py`, `tests/unit/test_cli_research.py`]

- [x] 9. Seed deterministic parity fixtures and capture package-local QA evidence

  **What to do**: Extend `poe_trade/qa_contract.py` so package-owned QA seeding populates non-zero parity fixtures for scanner/backtest checks, including at least one enabled non-journal strategy and one journal-gated strategy. Add package-local evidence generation that runs scanner and backtest against the same seeded snapshot, records run IDs, compares sorted `item_or_market_key` arrays, and writes JSON/markdown outputs under a package-owned evidence directory.
  **Must NOT do**: Do not rely on live Mirage data, and do not leave evidence as dry-run-only or count-only without key-array comparison.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` — Reason: deterministic seed/evidence work inside package-owned QA tooling.
  - Skills: [`evidence-bundle`] — Reason: evidence output must be paste-ready and reproducible.
  - Omitted: [`docs-specialist`] — Docs update belongs to the next task.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: [10] | Blocked By: [1, 6, 7, 8]

  **References** (executor has NO interview context — be exhaustive):
  - API/Type: `poe_trade/qa_contract.py` — Existing QA seed entrypoint to extend.
  - API/Type: `poe_trade/evidence_bundle.py` — Existing package-owned evidence summary generator to repoint at package-local outputs.
  - Pattern: `poe_trade/cli.py` — Scanner/backtest CLI entry points the package-local QA flow must exercise.

  **Acceptance Criteria** (agent-executable only):
  - [x] QA seed creates deterministic non-zero candidate fixtures for scanner/backtest parity checks.
  - [x] Package-local evidence includes exact scanner/backtest run IDs, sorted key arrays, and count comparisons for the same seeded snapshot.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_scanner.py tests/unit/test_strategy_backtest.py tests/unit/test_cli_scan.py tests/unit/test_cli_research.py -q` still exits 0 after seed/evidence support lands.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Seeded CLI parity proof passes
    Tool: Bash
    Steps: Run `.venv/bin/python -m poe_trade.qa_contract seed --output poe_trade/evidence/qa/seed.json && .venv/bin/python -m poe_trade.evidence_bundle && .venv/bin/python -m poe_trade.cli scan plan --league Mirage --limit 20 && .venv/bin/python -m poe_trade.cli research backtest --strategy bulk_essence --league Mirage --days 14`
    Expected: Commands succeed; package-local evidence captures matching sorted key arrays and counts for the same seeded snapshot.
    Evidence: `poe_trade/evidence/qa/seed.json`

  Scenario: Journal-gated seeded failure path stays explicit
    Tool: Bash
    Steps: Run `.venv/bin/python -m poe_trade.qa_contract seed --output poe_trade/evidence/qa/seed-journal.json && .venv/bin/python -m poe_trade.cli research backtest --strategy high_dim_jewels --league Mirage --days 14`
    Expected: Command succeeds; package-local evidence shows zero eligible candidates with gate-specific summary text when journal state is absent.
    Evidence: `poe_trade/evidence/qa/seed-journal.json`
  ```

  **Commit**: YES | Message: `test(qa): add deterministic parity verification and edge-case coverage` | Files: [`poe_trade/qa_contract.py`, `poe_trade/evidence_bundle.py`]

- [x] 10. Refresh package-local evidence outputs and parity summaries

  **What to do**: Update `poe_trade/evidence_bundle.py` and package-owned evidence outputs so they describe the canonical candidate/parity workflow using generated package-local artifacts from Task 9. Refresh package-local summary/index files so they no longer rely on dry-run or zero-row placeholder evidence.
  **Must NOT do**: Do not document commands that were not run, and do not preserve dry-run or zero-row placeholders as if they prove parity.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: package-local evidence summary refresh with accuracy-sensitive output descriptions.
  - Skills: [`evidence-bundle`] — Reason: package-owned evidence output must stay indexed and ready to inspect.
  - Omitted: [`protocol-compat`] — No schema change in this task.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: [Final Verification Wave] | Blocked By: [1, 7, 8, 9]

  **References** (executor has NO interview context — be exhaustive):
  - API/Type: `poe_trade/evidence_bundle.py` — Package-owned evidence summary/index generator.
  - API/Type: `poe_trade/qa_contract.py` — Package-owned seeded parity evidence source.
  - Pattern: `poe_trade/evidence/qa/seed.json` — Package-local seed/evidence output from Task 9.

  **Acceptance Criteria** (agent-executable only):
  - [x] Package-local evidence summary/index output describes the canonical candidate/parity workflow and status meanings accurately.
  - [x] Refreshed package-local artifacts/evidence are generated from real non-dry-run parity runs and no longer show empty or placeholder parity proof.
  - [x] `.venv/bin/python -m poe_trade.evidence_bundle` exits 0 after docs/evidence refresh, and referenced files exist.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Docs and evidence bundle refresh pass
    Tool: Bash
    Steps: Run `.venv/bin/python -m poe_trade.evidence_bundle`
    Expected: Exit code 0; refreshed package-local summary/index references existing package-owned evidence files generated by Task 9.
    Evidence: `poe_trade/evidence/summary.md`

  Scenario: Stale artifact regression is removed
    Tool: Bash
    Steps: Run `python3 - <<'PY'
from pathlib import Path
summary = Path('poe_trade/evidence/summary.md').read_text(encoding='utf-8')
assert 'Artifact count: 0' not in summary
assert '--dry-run' not in summary
PY`
    Expected: Exit code 0; refreshed package-local evidence summary is non-dry-run and no longer reports empty placeholder parity proof.
    Evidence: `poe_trade/evidence/summary.md`
  ```

  **Commit**: YES | Message: `docs(strategy): refresh package-local parity evidence summaries` | Files: [`poe_trade/evidence_bundle.py`, `poe_trade/evidence/`]

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: `test(strategy): codify candidate contract and parity fixtures`
- Commit 2: `refactor(strategy): add candidate contract loading and shared policy helpers`
- Commit 3: `refactor(strategy): route scanner through canonical candidate pipeline`
- Commit 4: `refactor(strategy): route backtest through canonical candidate pipeline`
- Commit 5: `test(qa): add deterministic parity verification and edge-case coverage`
- Commit 6: `docs(strategy): refresh package-local parity evidence summaries`
- Keep each commit green on its task-scoped test commands; do not mix docs refresh into logic commits.

## Success Criteria
- For any migrated strategy, scanner and backtest consume the same `candidate.sql` body and the same policy helper outputs.
- For the same strategy/league/window and seeded snapshot, `poe_trade.scanner_recommendations` and `poe_trade.research_backtest_detail` contain the same sorted `item_or_market_key` array after policy application.
- `no_data` appears only when raw candidate source rows are absent; `no_opportunities` appears when source rows exist but policy eliminates all candidates.
- `requires_journal` behavior is identical in both paths for this change.
- New evidence replaces dry-run/zero-row artifacts with deterministic non-zero parity proof.
