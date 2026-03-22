# Pricing Research PoC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce offline evidence showing whether any pricing-research candidate beats the current shipped `v3` baseline for the evaluated league population, without changing production serving behavior.

**Architecture:** Keep the current single-item evaluation harness as the baseline truth source, then add a small research package under `scripts/` with focused modules for config loading, candidate dispatch, statistics, recommendation rules, and artifact writing. The CLI entrypoint orchestrates those modules, writes repo-visible evidence, and never changes production serving behavior.

**Tech Stack:** Python 3.11, existing `poe_trade.ml.workflows` and `poe_trade.ml.v3` modules, ClickHouse-backed offline evaluation, pytest, JSON evidence artifacts, repo docs under `docs/research/`, `docs/evidence/`, and `docs/superpowers/specs/`.

---

## File Structure

- Create: `docs/research/pricing-research-poc-methodology.md` — fixed research rules: scope, windows, seeds, bootstrap count, family mapping, search budget, and recommendation rules.
- Create: `docs/evidence/pricing-research-poc/README.md` — evidence index with exact commands, output inventory, and run status.
- Create: `docs/evidence/pricing-research-poc/window-definitions.json` — fixed evaluated leagues and rolling windows.
- Create: `docs/evidence/pricing-research-poc/candidate-manifest.json` — candidate IDs and offline-eligibility metadata.
- Create: `docs/evidence/pricing-research-poc/decision-record.json` — per-candidate `passed` / `failed` / `skipped` outcomes with gate rationale.
- Create: `docs/superpowers/specs/2026-03-21-pricing-research-poc-results.md` — ranked comparison and final recommendation summary after the PoC run.
- Modify: `scripts/evaluate_single_item_algorithms.py` — expose baseline harness as an importable helper without changing semantics.
- Create: `scripts/pricing_research_poc/config.py` — load and validate methodology-adjacent config files.
- Create: `scripts/pricing_research_poc/candidates.py` — offline candidate adapter registry and guards.
- Create: `scripts/pricing_research_poc/metrics.py` — paired deltas and secondary metric helpers.
- Create: `scripts/pricing_research_poc/stability.py` — paired bootstrap intervals and instability checks.
- Create: `scripts/pricing_research_poc/slices.py` — eligible-slice filtering, family mapping application, thin-cohort warnings, and excluded-cohort reporting.
- Create: `scripts/pricing_research_poc/recommendation.py` — eligibility rules, hybrid progression rule, tie-breaks, and recommendation labels.
- Create: `scripts/pricing_research_poc/artifacts.py` — write raw tables, summaries, decision record, and results summary inputs.
- Create: `scripts/run_pricing_research_poc.py` — CLI entrypoint that wires the focused modules together.
- Create: `tests/unit/test_pricing_research_poc_config.py`
- Create: `tests/unit/test_pricing_research_poc_candidates.py`
- Create: `tests/unit/test_pricing_research_poc_metrics.py`
- Create: `tests/unit/test_pricing_research_poc_stability.py`
- Create: `tests/unit/test_pricing_research_poc_slices.py`
- Create: `tests/unit/test_pricing_research_poc_recommendation.py`
- Create: `tests/unit/test_pricing_research_poc_artifacts.py`
- Create: `tests/unit/test_pricing_research_poc_cli.py`
- Modify: `tests/unit/test_ml_serving_path_eval.py`
- Modify: `README.md`

## Task 1: Methodology Document Contract

**Files:**
- Create: `docs/research/pricing-research-poc-methodology.md`
- Create: `tests/unit/test_pricing_research_poc_config.py`

- [ ] Write a failing test that expects the methodology document to mention fixed seeds, bootstrap confidence level, documented resampling count, bounded hyperparameter budget, allowed offline-only derived features, and the winner-selection order.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k methodology -v` (expect FAIL).
- [ ] Write `docs/research/pricing-research-poc-methodology.md` with the exact rules from the approved spec.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k methodology -v` (expect PASS).

## Task 2: Window Definition Contract

**Files:**
- Create: `docs/evidence/pricing-research-poc/window-definitions.json`
- Create: `tests/unit/test_pricing_research_poc_config.py`

- [ ] Write a failing test that expects ordered window IDs plus train-cutoff, holdout-start, and holdout-end timestamps.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k windows -v` (expect FAIL).
- [ ] Write `docs/evidence/pricing-research-poc/window-definitions.json` in that exact structure.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k windows -v` (expect PASS).

## Task 3: Candidate Manifest Contract

**Files:**
- Create: `docs/evidence/pricing-research-poc/candidate-manifest.json`
- Create: `tests/unit/test_pricing_research_poc_config.py`

- [ ] Write a failing test that expects baseline, stronger-tabular, comparables-anchor, and optional hybrid candidate IDs.
- [ ] Write a failing test that expects each candidate to declare `full_contract` or `price_only`, bounded-search metadata, and offline-only eligibility.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k manifest -v` (expect FAIL).
- [ ] Write `docs/evidence/pricing-research-poc/candidate-manifest.json` to satisfy that contract.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k manifest -v` (expect PASS).

## Task 4: Config Loader Module

**Files:**
- Create: `scripts/pricing_research_poc/config.py`
- Create: `tests/unit/test_pricing_research_poc_config.py`

- [ ] Write a failing test that expects `config.py` to load and validate the window-definition and candidate-manifest files into one typed config payload.
- [ ] Write a failing test that rejects inconsistent league IDs, duplicate window IDs, and unknown candidate kinds.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k loader -v` (expect FAIL).
- [ ] Implement minimal config loading and validation in `scripts/pricing_research_poc/config.py`.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py -k loader -v` (expect PASS).

## Task 5: Baseline Harness Import Path

**Files:**
- Modify: `scripts/evaluate_single_item_algorithms.py`
- Modify: `tests/unit/test_ml_serving_path_eval.py`

- [ ] Write a failing test that expects the current baseline harness to be importable and reusable without changing its CLI behavior.
- [ ] Run: `.venv/bin/pytest tests/unit/test_ml_serving_path_eval.py -k importable -v` (expect FAIL).
- [ ] Refactor `scripts/evaluate_single_item_algorithms.py` minimally to expose an importable helper while preserving baseline semantics.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_ml_serving_path_eval.py -k importable -v` (expect PASS).

## Task 6: Baseline Semantics Proof

**Files:**
- Create: `scripts/pricing_research_poc/candidates.py`
- Modify: `tests/unit/test_ml_serving_path_eval.py`
- Create: `tests/unit/test_pricing_research_poc_candidates.py`

- [ ] Write a failing test that expects the reusable baseline path to preserve shipped `v3` offline behavior tied to `poe_trade/ml/v3/train.py`, `poe_trade/ml/v3/eval.py`, and serve-time fallback behavior whenever fallback would apply.
- [ ] Run: `.venv/bin/pytest tests/unit/test_ml_serving_path_eval.py tests/unit/test_pricing_research_poc_candidates.py -k shipped_baseline -v` (expect FAIL).
- [ ] Implement only the minimum baseline-proof wiring needed to make that contract explicit in tests.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_ml_serving_path_eval.py tests/unit/test_pricing_research_poc_candidates.py -k shipped_baseline -v` (expect PASS).

## Task 7: Candidate Adapter Registry

**Files:**
- Create: `scripts/pricing_research_poc/candidates.py`
- Create: `tests/unit/test_pricing_research_poc_candidates.py`

- [ ] Write a failing test that expects adapter lookup for `baseline`, `stronger_tabular`, `comparables_anchor`, and `hybrid`.
- [ ] Write a failing test that rejects any candidate requesting migrations, production writes, or new online dependencies.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_candidates.py -v` (expect FAIL).
- [ ] Implement the minimal offline-only adapter registry.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_candidates.py -v` (expect PASS).

## Task 8: Paired Execution Contract

**Files:**
- Create: `scripts/pricing_research_poc/candidates.py`
- Create: `tests/unit/test_pricing_research_poc_candidates.py`

- [ ] Write a failing test that expects every candidate-vs-baseline comparison to use the same window IDs and same holdout population metadata.
- [ ] Write a failing test that marks single-league runs as league-specific recommendations only.
- [ ] Write a failing test that requires multi-league evaluations to stay separate by league unless a later artifact explicitly reports pooled summaries as secondary output.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_candidates.py -k paired -v` (expect FAIL).
- [ ] Implement minimal paired-execution bookkeeping.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_candidates.py -k paired -v` (expect PASS).

## Task 9: Core Delta Metrics

**Files:**
- Create: `scripts/pricing_research_poc/metrics.py`
- Create: `tests/unit/test_pricing_research_poc_metrics.py`

- [ ] Write a failing test for paired delta calculation on global fair-value MDAPE.
- [ ] Write a failing test for paired delta calculation on worst-slice MDAPE.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_metrics.py -k delta -v` (expect FAIL).
- [ ] Implement minimal paired-delta helpers in `scripts/pricing_research_poc/metrics.py`.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_metrics.py -k delta -v` (expect PASS).

## Task 10: Full-Contract Secondary Metrics

**Files:**
- Create: `scripts/pricing_research_poc/metrics.py`
- Create: `tests/unit/test_pricing_research_poc_metrics.py`

- [ ] Write a failing test for fast-sale hit-rate comparison when a candidate is `full_contract`.
- [ ] Write a failing test for sale-probability calibration comparison when a candidate is `full_contract`.
- [ ] Write a failing test for `p10/p90` interval-coverage diagnostics.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_metrics.py -k secondary -v` (expect FAIL).
- [ ] Implement only the minimum full-contract secondary-metric helpers needed by the spec.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_metrics.py -k secondary -v` (expect PASS).

## Task 11: Bootstrap and Instability Rules

**Files:**
- Create: `scripts/pricing_research_poc/stability.py`
- Create: `tests/unit/test_pricing_research_poc_stability.py`

- [ ] Write a failing test for 95% paired bootstrap confidence intervals with fixed seeds on fair-value and worst-slice MDAPE.
- [ ] Write a failing test for the same paired-bootstrap requirement on fast-sale hit rate and sale-probability calibration when a candidate is full-contract.
- [ ] Write a failing test for the instability rule based on sign changes across windows.
- [ ] Write a failing test for the interval-width rule that marks results inconclusive.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_stability.py -v` (expect FAIL).
- [ ] Implement the minimum bootstrap and instability logic needed by the spec.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_stability.py -v` (expect PASS).

## Task 12: Slice Eligibility and Thin-Cohort Flags

**Files:**
- Create: `scripts/pricing_research_poc/slices.py`
- Create: `tests/unit/test_pricing_research_poc_slices.py`

- [ ] Write a failing test for required slice groups: route, rarity, support bucket, and fixed family mapping.
- [ ] Write a failing test that excludes slices under the 100-example threshold from the formal worst-slice gate.
- [ ] Write a failing test that still records descriptive warnings for low-support and fallback-prone cohorts below that threshold.
- [ ] Write a failing test that excluded cohorts must report both excluded row count and exclusion reason.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_slices.py -v` (expect FAIL).
- [ ] Implement the minimum slice, thin-cohort, and excluded-cohort helpers needed by the spec.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_slices.py -v` (expect PASS).

## Task 13: Recommendation Rules

**Files:**
- Create: `scripts/pricing_research_poc/recommendation.py`
- Create: `tests/unit/test_pricing_research_poc_recommendation.py`

- [ ] Write a failing test that price-only candidates can never receive `implement`.
- [ ] Write a failing test that `implement` requires both threshold success and statistical-guardrail success.
- [ ] Write a failing test for the exact threshold gates: at least `5%` relative global fair-value MDAPE improvement, no more than `2%` relative worst-slice regression, no more than `0.02` absolute fast-sale hit-rate regression, no more than `0.01` absolute calibration regression, and non-negative MDAPE delta in `3 of 4` required slice groups.
- [ ] Write a failing test that hybrid is skipped unless an earlier candidate clears the 3% progression rule without guardrail violations.
- [ ] Write a failing test for the fixed implementation-complexity rubric used as the final tie-breaker.
- [ ] Write a failing test for the winner tie-break order and `maybe` handling when candidates remain effectively tied.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_recommendation.py -v` (expect FAIL).
- [ ] Implement only the recommendation logic needed by the spec.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_recommendation.py -v` (expect PASS).

## Task 14: Artifact Writer Module

**Files:**
- Create: `scripts/pricing_research_poc/artifacts.py`
- Create: `tests/unit/test_pricing_research_poc_artifacts.py`
- Create: `docs/evidence/pricing-research-poc/decision-record.json`

- [ ] Write a failing test that expects raw metric tables, summary tables, bootstrap outputs, and per-candidate decision records.
- [ ] Write a failing test that expects a stable repo-visible output layout keyed by run ID or artifact name.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_artifacts.py -v` (expect FAIL).
- [ ] Implement the minimal artifact-writer functions in `scripts/pricing_research_poc/artifacts.py` and add `docs/evidence/pricing-research-poc/decision-record.json`.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_artifacts.py -v` (expect PASS).

## Task 15: CLI Runner Entry Point

**Files:**
- Create: `scripts/run_pricing_research_poc.py`
- Create: `tests/unit/test_pricing_research_poc_cli.py`

- [ ] Write a failing test that expects one reproducible entrypoint command to load config, execute paired comparisons, and write the full artifact set.
- [ ] Write a failing test that expects the CLI runner to skip hybrid automatically when the progression rule is not met.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_cli.py -v` (expect FAIL).
- [ ] Implement the CLI entrypoint by composing the focused modules.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_cli.py -v` (expect PASS).

## Task 16: Evidence README Template

**Files:**
- Create: `docs/evidence/pricing-research-poc/README.md`
- Create: `tests/unit/test_pricing_research_poc_artifacts.py`

- [ ] Write a failing test that expects the evidence README template to list exact commands, output locations, run-status wording, excluded-cohort reporting, and `not run` language until a real run is executed.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_artifacts.py -k evidence_readme -v` (expect FAIL).
- [ ] Write the evidence README template.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_artifacts.py -k evidence_readme -v` (expect PASS).

## Task 17: Results Summary Artifact

**Files:**
- Create: `docs/superpowers/specs/2026-03-21-pricing-research-poc-results.md`
- Create: `tests/unit/test_pricing_research_poc_artifacts.py`

- [ ] Write a failing test that expects a results-summary artifact path for ranked comparison, short write-up, and final recommendation label.
- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_artifacts.py -k results_summary -v` (expect FAIL).
- [ ] Create the results-summary template with placeholders for ranked comparison, winning candidate, losing candidates, and rationale.
- [ ] Re-run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_artifacts.py -k results_summary -v` (expect PASS).

## Task 18: README Workflow Docs

**Files:**
- Modify: `README.md`

- [ ] Run a failing verification snippet that expects `README.md` to reference the research runner, methodology doc, evidence directory, and results-summary artifact path.
- [ ] Run: `python3 - <<'PY'
from pathlib import Path
text = Path('README.md').read_text(encoding='utf-8')
needles = [
    'run_pricing_research_poc.py',
    'pricing-research-poc-methodology',
    'docs/evidence/pricing-research-poc',
    'pricing-research-poc-results',
]
missing = [n for n in needles if n not in text]
raise SystemExit(1 if missing else 0)
PY` (expect FAIL).
- [ ] Update `README.md` to mention the research workflow and artifact locations.
- [ ] Re-run the same command (expect PASS).

## Task 19: Verification and Evidence Hygiene

**Files:**
- Test: `tests/unit/test_pricing_research_poc_config.py`
- Test: `tests/unit/test_pricing_research_poc_candidates.py`
- Test: `tests/unit/test_pricing_research_poc_metrics.py`
- Test: `tests/unit/test_pricing_research_poc_stability.py`
- Test: `tests/unit/test_pricing_research_poc_slices.py`
- Test: `tests/unit/test_pricing_research_poc_recommendation.py`
- Test: `tests/unit/test_pricing_research_poc_artifacts.py`
- Test: `tests/unit/test_pricing_research_poc_cli.py`
- Test: `tests/unit/test_ml_serving_path_eval.py`

- [ ] Run: `.venv/bin/pytest tests/unit/test_pricing_research_poc_config.py tests/unit/test_pricing_research_poc_candidates.py tests/unit/test_pricing_research_poc_metrics.py tests/unit/test_pricing_research_poc_stability.py tests/unit/test_pricing_research_poc_slices.py tests/unit/test_pricing_research_poc_recommendation.py tests/unit/test_pricing_research_poc_artifacts.py tests/unit/test_pricing_research_poc_cli.py tests/unit/test_ml_serving_path_eval.py -v` (expect PASS).
- [ ] Run: `.venv/bin/pytest tests/unit -k "pricing_research_poc or serving_path_eval" -v` (expect PASS).
- [ ] Run: `python3 -m compileall scripts/run_pricing_research_poc.py scripts/pricing_research_poc scripts/evaluate_single_item_algorithms.py` (expect PASS).
- [ ] Run one reproducible entrypoint command against fixture-backed or deterministic local inputs if available; otherwise record `not run` explicitly in `docs/evidence/pricing-research-poc/README.md`.
- [ ] Verify that the final artifact set includes methodology, windows, manifest, raw tables, bootstrap outputs, decision record, results summary, and exact command history.
- [ ] Verify that the final artifact set also includes per-slice metric tables, `not produced` handling for price-only secondary metrics, separate per-league outputs when more than one league is evaluated, and excluded-cohort rows with both count and reason.

## Hard Constraints

- Keep this phase offline-only; do not change production serving, API behavior, migrations, or rollout state.
- Reuse `scripts/evaluate_single_item_algorithms.py` as the default baseline harness unless `docs/research/pricing-research-poc-methodology.md` explicitly justifies a different baseline runner.
- Use paired comparisons on the same windows and holdout examples for every candidate-vs-baseline claim.
- Document fixed seeds, bootstrap resampling count, and bounded search budget before comparing candidates.
- Price-only candidates may be researched, but they cannot receive an `implement` recommendation in this phase.
- Skip the hybrid candidate unless the progression rule is satisfied.
- Write all reproducibility artifacts into repo-visible docs/evidence/spec paths before claiming any result.
