# ML Pricing Performance Optimization (Mirage-First)

## TL;DR
> **Summary**: Improve pricing accuracy and predict latency by hardening data/eval integrity, eliminating train-serve skew, and reducing online ClickHouse dependency in the `predict-one` path.
> **Deliverables**:
> - Frozen-slice training/evaluation with leakage and freshness hard-fail gates
> - Train/serve feature parity and schema-checked model artifacts
> - Cached serving profile path with reduced per-request query load
> - Cohort-protected promotion contract with deterministic evidence
> **Effort**: XL
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 -> 3 -> 4 -> 10 -> 11

## Context
### Original Request
Improve the performance of the ML pricing algorithm and achieve accurate price prediction for any given item.

### Interview Summary
- Optimization priority: accuracy-first, then latency/cost.
- Primary quality gate: MDAPE plus protected cohort floors.
- Scope: end-to-end (data rebuild, features, training/eval, inference serving).
- Rollout: Mirage first, then generalization hardening.
- Test strategy: tests-after implementation with agent-executed QA scenarios on every task.
- Threshold profile: aggressive (`>=20%` MDAPE improvement, zero protected-cohort degradation, `>=50%` p95 latency improvement).

### Metis Review (gaps addressed)
- Split execution into explicit offline and online tracks.
- Add protected-cohort minimum-support and data-freshness validity gates.
- Require deterministic, command-driven evidence for every acceptance gate.
- Prevent benchmark gaming by enforcing same-slice candidate vs incumbent comparison.

## Work Objectives
### Core Objective
Deliver a Mirage-first pricing pipeline that improves model quality and API latency with strict anti-leakage, anti-drift, and cohort-protection gates enforced by deterministic CI evidence.

### Deliverables
- Run-manifested dataset/eval pipeline with frozen slices and reproducible lineage.
- Promotion contract that blocks leakage, stale data, and protected-cohort regressions.
- Predict-one serving cache path that minimizes per-request ClickHouse and artifact reload overhead.
- Shadow comparison workflow for candidate vs incumbent prior to cutover.
- Rollout and rollback controls with evidence-backed operational playbook.

### Definition of Done (verifiable conditions with commands)
- `make ci-deterministic` exits `0` with ML + API + frontend deterministic checks passing.
- `.venv/bin/poe-ml train-loop --league Mirage --dataset-table poe_trade.ml_price_dataset_v1 --model-dir artifacts/ml/mirage_v1 --max-iterations 2 --max-wall-clock-seconds 1800 --no-improvement-patience 2 --min-mdape-improvement 0.005` records a candidate eval run with frozen-slice metadata.
- `.venv/bin/poe-ml status --league Mirage --run latest` reports promotion decision including protected-cohort and freshness checks.
- API predict benchmark harness shows candidate p95 latency at or below 50% of incumbent baseline on identical corpus and concurrency profile.

### Must Have
- Same-slice candidate/incumbent evaluation contract.
- Hard-fail leakage and freshness gates.
- Protected-cohort non-regression gate with minimum support threshold.
- Train/serve feature parity checks embedded in model bundle contract.
- Predict-one hot path cache with deterministic fallback behavior.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No metric-only claims without command output evidence.
- No manual-only QA acceptance steps.
- No threshold relaxation to force promotion.
- No unrelated ingestion/UI refactors outside pricing quality/latency objective.
- No schema-destructive changes (`DROP`, mass deletes outside controlled rebuild semantics).

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after + existing `pytest`/CLI/deterministic Make targets.
- QA policy: every task includes happy-path and failure/edge QA scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: High-independence foundations (Tasks 1, 2, 5, 7)
Wave 2: Gate + parity + performance integration (Tasks 3, 4, 6, 8, 9)
Wave 3: Promotion and rollout completion (Tasks 10, 11, 12)

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 3, 6, 10.
- Task 2 blocks Tasks 3, 10, 11.
- Task 3 blocks Tasks 4, 10.
- Task 4 blocks Tasks 8, 10.
- Task 5 blocks Tasks 6, 11.
- Task 6 blocks Task 10.
- Task 7 blocks Tasks 8, 9.
- Task 8 blocks Task 11.
- Task 9 blocks Task 11.
- Task 10 blocks Task 11.
- Task 11 blocks Task 12.
- Task 12 must complete before Final Verification Wave.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 4 tasks -> `deep`, `ultrabrain`, `unspecified-high`
- Wave 2 -> 5 tasks -> `deep`, `ultrabrain`, `unspecified-high`, `quick`
- Wave 3 -> 3 tasks -> `deep`, `unspecified-high`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.


- [ ] 9. Add artifact warmup and registry lookup minimization on serving startup

  **What to do**: Implement model artifact preloading/warmup and registry lookup minimization so first-request latency spikes are reduced after deploy/promotion.
  **Must NOT do**: Do not bypass model registry correctness checks.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: focused startup optimization around existing load path.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 11 | Blocked By: 7

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — artifact resolution/load functions and caches.
  - Pattern: `poe_trade/services/ml_trainer.py` — lifecycle hooks for newly promoted artifacts.
  - API/Type: `poe_trade/api/ml.py` — serving layer integration points.
  - Test: `tests/unit/test_ml_observability.py` — run-status fields to expose warmup state.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Cold-start benchmark shows reduced first-request latency relative to Task-1 baseline.
  - [ ] Registry lookup frequency drops on steady-state requests without stale artifact usage.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path startup warmup
    Tool: Bash
    Steps: Restart API process, execute first request benchmark sequence.
    Expected: First-hit latency is improved and warmup markers appear in logs/status.
    Evidence: .sisyphus/evidence/task-9-artifact-warmup.json

  Scenario: Promotion during warm cache
    Tool: Bash
    Steps: Promote new artifact while service is warm and issue immediate predictions.
    Expected: New artifact is loaded correctly with no stale predictions or 5xx.
    Evidence: .sisyphus/evidence/task-9-artifact-warmup-promotion.json
  ```

  **Commit**: YES | Message: `perf(ml-serving): add artifact warmup and registry cache` | Files: `poe_trade/ml/workflows.py`, `poe_trade/api/ml.py`, `poe_trade/services/ml_trainer.py`

- [ ] 10. Implement candidate-vs-incumbent shadow evaluation and promotion gate enforcement

  **What to do**: Add shadow comparison flow that runs candidate and incumbent on identical frozen slices and enforces aggressive gates (>=20% MDAPE improvement, zero protected-cohort degradation with support threshold, freshness/leakage pass) before promotion.
  **Must NOT do**: Do not compare candidate/incumbent on different slices or mixed freshness windows.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: core safety-critical decision logic for promotion.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 11 | Blocked By: 1, 2, 3, 4, 6

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — `evaluate_stack`, promotion audit writes, model registry updates.
  - Pattern: `poe_trade/api/ml.py` — automation history/status contract.
  - Test: `tests/unit/test_ml_observability.py` — route metrics and verdict reporting.
  - Test: `tests/unit/test_ml_cli.py` — train/status/report command behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Candidate is promoted only when all gate checks pass on identical slice ids.
  - [ ] Any gate failure (mdape shortfall/cohort regression/leakage/staleness) returns `hold` with explicit machine-readable reason.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path all gates pass
    Tool: Bash
    Steps: Run candidate and incumbent evaluation on same frozen slice fixture.
    Expected: Candidate promoted with gate pass evidence for each criterion.
    Evidence: .sisyphus/evidence/task-10-promotion-gates.json

  Scenario: Gate failure matrix
    Tool: Bash
    Steps: Run four failure fixtures (mdape miss, cohort regression, leakage, stale snapshot).
    Expected: All produce hold verdicts with correct reason codes.
    Evidence: .sisyphus/evidence/task-10-promotion-gates-failures.json
  ```

  **Commit**: YES | Message: `feat(ml-promotion): enforce strict shadow gate contract` | Files: `poe_trade/ml/workflows.py`, `poe_trade/api/ml.py`, `tests/unit/test_ml_observability.py`, `tests/unit/test_ml_cli.py`

- [ ] 11. Execute Mirage-first rollout with controlled cutover and rollback toggles

  **What to do**: Implement league-scoped rollout toggles for candidate serving path, support shadow-only mode before cutover, and codify deterministic rollback behavior to incumbent model/profile.
  **Must NOT do**: Do not enable multi-league rollout in this task; do not remove rollback path.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: production-safety control path across service and API components.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 12 | Blocked By: 2, 5, 8, 9, 10

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/api/ml.py` — league allowlist and prediction route handling.
  - Pattern: `poe_trade/api/app.py` — endpoint/router wiring and auth guard.
  - Pattern: `poe_trade/services/ml_trainer.py` — automation lifecycle and active model updates.
  - Test: `tests/unit/test_api_ml_routes.py` — API contract and league route behaviors.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Mirage shadow mode emits side-by-side candidate/incumbent comparisons without user-visible cutover.
  - [ ] Rollback toggle reverts serving to incumbent deterministically within one refresh cycle.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path controlled cutover
    Tool: Bash
    Steps: Enable Mirage shadow mode, verify comparisons, then enable cutover flag.
    Expected: Serving switches to candidate only after gate pass; API contract unchanged.
    Evidence: .sisyphus/evidence/task-11-rollout-cutover.json

  Scenario: Rollback execution
    Tool: Bash
    Steps: Trigger rollback flag after cutover and send prediction traffic.
    Expected: Incumbent resumes serving, candidate path disabled, no downtime.
    Evidence: .sisyphus/evidence/task-11-rollout-rollback.json
  ```

  **Commit**: YES | Message: `feat(ml-rollout): add mirage cutover and rollback controls` | Files: `poe_trade/api/ml.py`, `poe_trade/api/app.py`, `poe_trade/services/ml_trainer.py`, `tests/unit/test_api_ml_routes.py`

- [ ] 12. Lock deterministic evidence and operational verification artifacts

  **What to do**: Add deterministic benchmark/test orchestration and ops evidence capture for baseline vs candidate deltas, gate outcomes, and rollout/rollback drill results.
  **Must NOT do**: Do not mark success without generated evidence files.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: final integration and evidence enforcement across CLI/CI workflow.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: Final Verification Wave | Blocked By: 11

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `Makefile` — `ci-deterministic` and related deterministic targets.
  - Pattern: `.github/workflows/python-ci.yml` — CI execution surface.
  - API/Type: `README.md` — documented ML commands and verdict terminology.
  - Test: `tests/unit/test_ml_cli.py` and `tests/unit/test_ml_observability.py` — reporting/contract coverage expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `make ci-deterministic` passes after changes and output is stored in evidence artifact.
  - [ ] Evidence pack includes baseline/candidate latency deltas, MDAPE/cohort gate results, and rollback drill proof.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path deterministic gate
    Tool: Bash
    Steps: Run full deterministic target and collect outputs to evidence directory.
    Expected: Exit code 0 and evidence pack contains all required artifacts.
    Evidence: .sisyphus/evidence/task-12-deterministic-pack.log

  Scenario: Missing evidence enforcement
    Tool: Bash
    Steps: Run verification script with one intentionally missing artifact.
    Expected: Verification fails with explicit missing-artifact message.
    Evidence: .sisyphus/evidence/task-12-deterministic-pack-error.log
  ```

  **Commit**: YES | Message: `chore(ml-evidence): enforce deterministic verification artifacts` | Files: `Makefile`, `.github/workflows/python-ci.yml`, `README.md`, `tests/unit/test_ml_cli.py`, `tests/unit/test_ml_observability.py`

- [ ] 5. Optimize dataset rebuild from full refresh toward incremental-safe execution

  **What to do**: Refactor `poeninja_snapshot` + workflow rebuild steps to avoid unnecessary full-table rewrites for unchanged windows; use deterministic partition/window strategy and retain correctness of labels/comps outputs.
  **Must NOT do**: Do not introduce destructive schema changes or bypass rebuild correctness checks.

  **Recommended Agent Profile**:
  - Category: `ultrabrain` — Reason: high-risk data-pipeline optimization with correctness constraints.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 11 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/services/poeninja_snapshot.py` — rebuild orchestration order and cadence.
  - Pattern: `poe_trade/ml/workflows.py` — table rebuild statements for labels/dataset/comps.
  - API/Type: `README.md` — service defaults and rebuild interval behavior.
  - Test: `tests/unit/test_ml_cli.py` — command/report expectations relevant to rebuild observability.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Two consecutive rebuild runs on unchanged snapshot show reduced write volume/runtime while producing identical row-hash checksums for target tables.
  - [ ] Rebuild on changed snapshot updates only intended partitions/windows and keeps downstream training inputs consistent.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path unchanged snapshot
    Tool: Bash
    Steps: Execute rebuild twice against identical snapshot fixture; compare row counts/checksums and runtime.
    Expected: Outputs are identical, second run has lower write pressure/runtime.
    Evidence: .sisyphus/evidence/task-5-rebuild-opt.json

  Scenario: Changed snapshot incremental update
    Tool: Bash
    Steps: Apply delta fixture and rerun rebuild.
    Expected: Only affected partitions/windows are refreshed; no global rewrite needed.
    Evidence: .sisyphus/evidence/task-5-rebuild-opt-delta.json
  ```

  **Commit**: YES | Message: `feat(ml-data): optimize snapshot rebuild execution` | Files: `poe_trade/services/poeninja_snapshot.py`, `poe_trade/ml/workflows.py`

- [ ] 6. Reduce training/evaluation scan cost without weakening metric fidelity

  **What to do**: Optimize route training/eval data access patterns (pre-aggregation, bounded windows, reusable intermediates) to lower ClickHouse IO/CPU while preserving exact MDAPE/cohort semantics.
  **Must NOT do**: Do not change the metric definitions or hide poor-performing slices.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: performance optimization with strict correctness invariants.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 1, 5

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — route training loops and eval aggregation.
  - Pattern: `poe_trade/services/ml_trainer.py` — training iteration lifecycle and stop policy.
  - Test: `tests/unit/test_ml_training_run_state.py` — training run state invariants.
  - Test: `tests/unit/test_ml_observability.py` — expected metric payload integrity.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Controlled benchmark shows reduced train/eval wall-clock and/or query cost compared with Task-1 baseline.
  - [ ] Metric outputs (MDAPE/cohort/support fields) are unchanged for identical input slices.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path faster train/eval
    Tool: Bash
    Steps: Run bounded train-loop with old baseline fixture and optimized path.
    Expected: Runtime/query-cost improves while metrics remain equivalent.
    Evidence: .sisyphus/evidence/task-6-train-scan-opt.json

  Scenario: Fidelity regression guard
    Tool: Bash
    Steps: Compare route-level metric outputs before/after optimization on same snapshot id.
    Expected: Any metric drift beyond tolerance fails task.
    Evidence: .sisyphus/evidence/task-6-train-scan-opt-error.json
  ```

  **Commit**: YES | Message: `perf(ml-training): optimize route scan and eval access` | Files: `poe_trade/ml/workflows.py`, `poe_trade/services/ml_trainer.py`, `tests/unit/test_ml_training_run_state.py`

- [ ] 7. Precompute serving profile aggregates for predict-one hot path

  **What to do**: Build/update precomputed serving profile data for support counts and reference price statistics used by `predict_one`, reducing live query complexity in request path.
  **Must NOT do**: Do not remove raw fallback path until cache reliability is verified.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: targeted serving-path data design with low algorithmic risk.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8, 9 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — `_support_count_recent`, `_reference_price` query patterns.
  - Pattern: `poe_trade/services/poeninja_snapshot.py` — periodic job hook suitable for profile refresh.
  - API/Type: `poe_trade/api/ml.py` — predict-one response fields consuming support/reference features.
  - Test: `tests/test_price_check_comparables.py` — comparable/reference data path assertions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Predict-one can resolve support/reference values from precomputed profile for warm path requests.
  - [ ] Profile refresh job keeps values aligned with latest eligible dataset snapshot.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path profile hit
    Tool: Bash
    Steps: Build serving profile then call predict-one for items covered by profile.
    Expected: Request path uses profile lookup and returns expected values.
    Evidence: .sisyphus/evidence/task-7-serving-profile.json

  Scenario: Profile miss fallback
    Tool: Bash
    Steps: Query an item intentionally missing in profile cache.
    Expected: Deterministic fallback executes without 5xx and logs fallback reason.
    Evidence: .sisyphus/evidence/task-7-serving-profile-fallback.json
  ```

  **Commit**: YES | Message: `feat(ml-serving): add precomputed profile aggregates` | Files: `poe_trade/ml/workflows.py`, `poe_trade/services/poeninja_snapshot.py`, `tests/test_price_check_comparables.py`

- [ ] 8. Add in-process serving cache and refresh policy for model and profile data

  **What to do**: Extend inference path to keep active model metadata and serving profile in memory with deterministic refresh/invalidation policy tied to promotion/snapshot updates.
  **Must NOT do**: Do not cache indefinitely without version checks or stale guards.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: latency-focused runtime optimization in API + workflow layers.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 11 | Blocked By: 4, 7

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — `_MODEL_BUNDLE_CACHE` and artifact loading.
  - Pattern: `poe_trade/api/ml.py` — request handling for predict-one/status.
  - API/Type: `poe_trade/api/app.py` — routing and endpoint contract boundaries.
  - Test: `tests/unit/test_api_ml_routes.py` — API route/contract expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Warm-path benchmark demonstrates significant drop in per-request query count and latency.
  - [ ] Cache invalidation updates active model/profile after promotion or snapshot refresh without restart.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path warm cache
    Tool: Bash
    Steps: Prime cache with repeated predict-one calls on fixed set.
    Expected: Subsequent calls show lower p95 and fewer backend queries.
    Evidence: .sisyphus/evidence/task-8-serving-cache.json

  Scenario: Stale cache invalidation
    Tool: Bash
    Steps: Promote a new model/profile version then issue predict-one requests.
    Expected: Cache refreshes to new version automatically; no stale-version predictions persist.
    Evidence: .sisyphus/evidence/task-8-serving-cache-invalidation.json
  ```

  **Commit**: YES | Message: `perf(ml-api): add predict path cache and invalidation` | Files: `poe_trade/ml/workflows.py`, `poe_trade/api/ml.py`, `tests/unit/test_api_ml_routes.py`


- [ ] 1. Establish Mirage baseline and run manifest contract

  **What to do**: Add a baseline benchmarking flow that records incumbent MDAPE/cohort metrics and predict-one latency using a fixed Mirage corpus/concurrency profile; persist run manifest fields (dataset snapshot id, source watermarks, eval slice id) into training/eval records for reproducible comparisons.
  **Must NOT do**: Do not alter promotion thresholds in this task; do not change model behavior yet.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: introduces cross-cutting measurement contract used by all later gates.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 3, 6, 10 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — train/eval metadata writes and run bookkeeping.
  - Pattern: `poe_trade/services/ml_trainer.py` — loop orchestration and run lifecycle.
  - API/Type: `poe_trade/api/ml.py` — status/report surfaces used for baseline visibility.
  - Test: `tests/unit/test_ml_observability.py` — expected automation history payload pattern.
  - Test: `tests/unit/test_ml_cli.py` — CLI result/reporting assertions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Running `poe-ml train-loop` and `poe-ml status` emits run metadata including snapshot/watermark identifiers in persisted output tables.
  - [ ] Benchmark script logs incumbent p50/p95 and request corpus hash to `.sisyphus/evidence/task-1-baseline.json`.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path baseline capture
    Tool: Bash
    Steps: Run train-loop/status commands for Mirage with bounded iterations; run benchmark harness against predict-one with fixed payload set.
    Expected: Run metadata includes snapshot fields and evidence JSON contains latency percentiles + corpus hash.
    Evidence: .sisyphus/evidence/task-1-baseline.json

  Scenario: Missing manifest field rejection
    Tool: Bash
    Steps: Execute a run with intentionally omitted manifest metadata via test fixture path.
    Expected: Pipeline returns deterministic failure/hold signal and no promotion-ready record is created.
    Evidence: .sisyphus/evidence/task-1-baseline-error.log
  ```

  **Commit**: YES | Message: `test(ml): add baseline and run-manifest contract` | Files: `poe_trade/ml/workflows.py`, `tests/unit/test_ml_observability.py`, `tests/unit/test_ml_cli.py`

- [ ] 2. Define protected cohorts and minimum-support policy contract

  **What to do**: Encode canonical protected cohorts (route/family/support-bucket) and minimum-support thresholds for Mirage promotion decisions; ensure policy is loaded consistently in eval/promotion paths and surfaced in status output.
  **Must NOT do**: Do not relax zero-degradation requirement; do not mix multi-league generalization logic yet.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: policy contract affects promotion logic and API observability.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 3, 10, 11 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — promotion verdict generation and route-level metrics.
  - API/Type: `poe_trade/api/ml.py` — status payload fields for promotion rationale.
  - Test: `tests/unit/test_ml_observability.py` — expected status/history schema checks.
  - External: `README.md` — current ML verdict vocabulary and operator-facing expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Status/report output includes protected cohort policy and minimum-support thresholds used in latest decision.
  - [ ] Promotion decision is blocked (`hold`) when any protected cohort with support >= threshold regresses.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path with non-regressing protected cohorts
    Tool: Bash
    Steps: Run evaluation using fixture data where protected cohorts improve or hold.
    Expected: Verdict can be promote/eligible and response includes policy fields.
    Evidence: .sisyphus/evidence/task-2-cohort-policy.json

  Scenario: Regression on supported protected cohort
    Tool: Bash
    Steps: Run evaluation fixture with one protected cohort regressing above threshold support.
    Expected: Verdict is hold with explicit protected-cohort regression reason.
    Evidence: .sisyphus/evidence/task-2-cohort-policy-error.json
  ```

  **Commit**: YES | Message: `feat(ml): add protected cohort support policy` | Files: `poe_trade/ml/workflows.py`, `poe_trade/api/ml.py`, `tests/unit/test_ml_observability.py`

- [ ] 3. Enforce hard-fail leakage and freshness gates for promotion validity

  **What to do**: Add deterministic gates that fail/hold promotion when train/eval slice overlap or stale source watermarks are detected; persist explicit stop/hold reasons into audit tables and CLI/API status.
  **Must NOT do**: Do not downgrade hard-fail conditions to warnings.

  **Recommended Agent Profile**:
  - Category: `ultrabrain` — Reason: requires precise integrity logic across run/eval/promotion contracts.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 4, 10 | Blocked By: 1, 2

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — existing eval aggregation, promotion audit writes.
  - Pattern: `poe_trade/services/poeninja_snapshot.py` — dataset freshness/rebuild cadence.
  - API/Type: `poe_trade/api/ml.py` — automation status/reporting paths.
  - Test: `tests/unit/test_ml_cli.py` — league validation and command error behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Overlap fixture run produces `hold` with leakage-specific reason in promotion audit outputs.
  - [ ] Stale watermark fixture run produces `hold` with freshness-specific reason and no active-model switch.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path integrity passes
    Tool: Bash
    Steps: Execute evaluation on non-overlapping, fresh-snapshot fixtures.
    Expected: Integrity gates pass and promotion remains eligible subject to metrics.
    Evidence: .sisyphus/evidence/task-3-integrity-pass.log

  Scenario: Leakage or stale-data guard trigger
    Tool: Bash
    Steps: Execute dedicated leakage fixture and stale-source fixture runs.
    Expected: Both runs resolve to hold with distinct machine-readable reasons.
    Evidence: .sisyphus/evidence/task-3-integrity-fail.log
  ```

  **Commit**: YES | Message: `feat(ml): enforce leakage and freshness promotion gates` | Files: `poe_trade/ml/workflows.py`, `poe_trade/api/ml.py`, `tests/unit/test_ml_cli.py`

- [ ] 4. Remove train-serve feature skew with schema-checked artifact contract

  **What to do**: Ensure online `predict_one` feature extraction uses the same mod-token/feature schema contract as training; persist feature schema/version in artifacts and validate at inference time before scoring.
  **Must NOT do**: Do not add unrelated new feature families in this task.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: ties together dataset feature engineering and serving-time inference correctness.
  - Skills: `[]` — no extra skill dependency required.
  - Omitted: `[]` — none.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8, 10 | Blocked By: 3

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/workflows.py` — `discover_mod_features`, dataset build, `predict_one`.
  - Pattern: `poe_trade/ml/workflows.py` — model bundle load/cache behavior (`_MODEL_BUNDLE_CACHE`).
  - Test: `tests/test_price_check_comparables.py` — inference route behavior expectations.
  - Test: `tests/test_pricing_outliers.py` — feature/output stability checks for pricing analytics.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Schema mismatch between model artifact and runtime feature payload deterministically fails with explicit error reason.
  - [ ] Matched schema path yields successful prediction and unchanged response contract shape.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Happy path schema parity
    Tool: Bash
    Steps: Train artifact with recorded feature schema, then call predict-one with valid item payload.
    Expected: Prediction succeeds and logs schema-version match.
    Evidence: .sisyphus/evidence/task-4-feature-parity.json

  Scenario: Feature schema mismatch
    Tool: Bash
    Steps: Attempt inference with an artifact/schema mismatch fixture.
    Expected: Request fails gracefully with deterministic mismatch reason (no silent fallback drift).
    Evidence: .sisyphus/evidence/task-4-feature-parity-error.json
  ```

  **Commit**: YES | Message: `feat(ml): enforce train-serve feature schema parity` | Files: `poe_trade/ml/workflows.py`, `poe_trade/api/ml.py`, `tests/test_price_check_comparables.py`


## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: `test(ml): codify baseline and gating expectations`
- Commit 2: `feat(ml-offline): enforce frozen-slice eval and integrity guards`
- Commit 3: `feat(ml-online): add predict serving cache and hot-path optimizations`
- Commit 4: `feat(ml-promotion): enforce cohort and freshness promotion contract`
- Commit 5: `chore(ml-rollout): add mirage rollout toggles and rollback flow`
- Commit 6: `docs(ops): capture performance evidence and operating procedure`

## Success Criteria
- Candidate run shows `>=20%` MDAPE improvement versus incumbent on identical frozen slices.
- No protected cohort with sufficient support shows degradation.
- Predict-one p95 latency is `>=50%` better than incumbent baseline on identical load profile.
- Promotion verdict remains `hold` when leakage, stale data, or cohort regressions are induced.
- Deterministic CI and targeted ML commands pass with evidence artifacts committed under `.sisyphus/evidence/`.
