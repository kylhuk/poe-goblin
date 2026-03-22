# Pricing Research PoC Design

**Goal:** Determine, with offline evidence only, whether the pricing system can be materially improved for the evaluated league population before any serving-path implementation work begins.

**Scope:** Research and proof-of-concept only. No production implementation, no serving cutover, no schema changes, and no API contract changes are in scope for this phase.

## Problem

The current `v3` pricing path is promising but still lightweight:

- `poe_trade/ml/v3/train.py` trains route-local sklearn gradient-boosted regressors for `p10`, `p50`, and `p90`, plus a logistic sale classifier.
- `poe_trade/ml/v3/serve.py` uses heuristic confidence and a route/base-type median fallback when a model bundle is unavailable.
- `poe_trade/ml/v3/eval.py` provides useful promotion metrics, but the current model family and fallback path may be leaving substantial accuracy on the table.

The main risk is spending time implementing a more complex pricing system that does not actually improve real-world accuracy. This phase exists to prevent that.

## Research Findings

### Current-stack weaknesses

- The current `v3` path uses separate route-local models rather than a stronger shared model that can borrow strength across related item families.
- Quantile models are trained independently, which can limit interval consistency and calibration quality.
- Confidence is heuristic rather than learned and calibrated.
- The median fallback in `poe_trade/ml/v3/serve.py` is coarse and is unlikely to be competitive for thin or complex slices.

### Existing code that supports a stronger direction

- Legacy retrieval-style helpers already exist in `poe_trade/ml/workflows.py`, especially `_select_top_comparables` and `_robust_anchor_from_comparables`.
- Existing API behavior already exposes a comparables concept in `poe_trade/api/ops.py`.
- `schema/migrations/0053_ml_v3_training_and_serving_store.sql` already defines `poe_trade.ml_v3_retrieval_candidates`, which is useful context for future work but does not commit this research phase to a retrieval implementation.

### Static PoC insight

A simple weighted-median comparable set behaves as desired for pricing: close comparables dominate the estimate while obvious outliers contribute very little. This supports using robust comp aggregation as a serious candidate, not just a fallback.

## Candidate Approaches

### 1. Stronger global tabular baseline hypothesis

Train a stronger offline tabular model from a modern boosted-tree family, using shared categorical and numeric features across routes.

**Expected upside:**

- Better overall accuracy on common and medium-support items.
- Better use of shared structure across categories, base types, rarity, and market state.
- Lower complexity than a full retrieval-first serving stack.

**Main risk:**

- It may improve broad averages while still underperforming on highly specific rare or mod-driven items.

### 2. Comparables-anchor baseline hypothesis

Build an offline estimator that retrieves close historical items and computes a robust anchor price from top comparables.

**Expected upside:**

- Better behavior on rare, unusual, or strongly mod-dependent items.
- Better resistance to outliers through trimming and weighted aggregation.
- More interpretable failure modes than direct regression.

**Main risk:**

- Retrieval quality may vary by slice, and sparse comparable coverage can still limit performance.

### 3. Hybrid anchor-plus-residual hypothesis

Use comparables to form an anchor price, then train a residual model to predict how far the target item should move away from that anchor.

**Expected upside:**

- Combines local market evidence with model-based generalization.
- Most likely to improve accuracy across all items if the anchor and residual signals complement each other.

**Main risk:**

- Highest complexity of the three options; not worth pursuing unless the first two PoCs show clear signal.

## Recommended PoC Order

1. Measure the current `v3` baseline with a fixed offline evaluation harness.
2. Run a stronger global tabular PoC.
3. Run a comparables-anchor PoC.
4. Run the hybrid residual PoC only if one of the first two approaches clears the explicit progression bar defined below.

This order minimizes wasted work and maximizes decision quality. These are offline hypotheses only; none of them imply a serving-path or schema commitment in this phase.

## Proof Strategy

### Evaluation population

`Across all items` in this phase means all evaluation examples that satisfy the current `v3` training/evaluation data contract for the selected league and time windows, including low-support and fallback-prone cohorts when they are present in that dataset. The default scope is one league at a time, starting with the active research league already used by the current ML flow. If additional leagues are included, they must be evaluated separately before any pooled summary is reported.

Single-league evidence is sufficient for an `implement` recommendation only for that evaluated league. Any broader cross-league recommendation must remain `maybe` until replicated on each target league.

Any cohort excluded for data-quality or contract reasons must be called out explicitly in the evidence output, along with the excluded row count and exclusion reason.

### Offline-only evaluation

All comparisons in this phase must be offline. No production-serving changes should be made before a winner is established.

### Fixed evaluation setup

- Use the same time-based rolling split for all candidates.
- Predict only from information that would have been available at that time.
- Score each candidate under the same slice definitions and metric definitions.

### Baseline definition

The baseline for every comparison is the current shipped `v3` offline behavior, including the existing training logic in `poe_trade/ml/v3/train.py`, the evaluation logic in `poe_trade/ml/v3/eval.py`, and the serve-time fallback behavior in `poe_trade/ml/v3/serve.py` whenever that fallback would apply inside the evaluated window.

Existing offline assets such as `scripts/evaluate_single_item_algorithms.py` and the related README guidance are prior art and should be treated as the default starting harness unless the research notes explicitly justify a different runner.

### Rolling-split protocol

- Use a forward-only rolling evaluation.
- Each window trains on historical data up to a cutoff timestamp and evaluates on the immediately following holdout window.
- The same cutoffs and holdout widths must be reused for every candidate.
- No candidate may use future observations, future aggregates, or labels derived after the prediction timestamp.

The exact cutoff timestamps, holdout widths, and evaluated leagues must be written out as a repo-visible artifact so another reviewer can rerun the same windows.

All candidate-vs-baseline comparisons must be paired on the same holdout examples and windows.

### Required metrics

Keep the current top-line metrics from `poe_trade/ml/v3/eval.py` as the main decision surface:

- fair-value MDAPE
- fast-sale 24h hit rate
- sale-probability calibration error
- worst-slice MDAPE

Every candidate must produce fair-value outputs. Interval, fast-sale, and sale-probability outputs are required only if that candidate is intended to compete as a full replacement for the current pricing contract. If a candidate is price-only, those secondary metrics must be marked `not produced`, and that candidate can receive at most a `maybe` recommendation in this phase.

Add research-only diagnostics to avoid false positives:

- MDAPE by support bucket
- MDAPE by route, rarity, and key item families
- interval coverage for `p10/p90`
- bootstrap confidence intervals for candidate-vs-baseline metric deltas

### Required slices

At minimum, every candidate must be reported on these slices:

- all items
- route
- rarity
- support bucket
- key item families with adequate support

For slice reporting, a slice is eligible only if it has at least 100 evaluation examples in the holdout set. Lower-support slices may be shown descriptively but may not drive the main recommendation. `Key item families` means a fixed, pre-declared family mapping written into the methodology artifact before candidate scoring begins; only mapped families with at least 100 evaluation examples are part of the eligible slice universe.

Low-support and fallback-prone cohorts below the 100-example threshold must still receive a secondary descriptive review. A candidate cannot be recommended as `implement` if those thin cohorts show obvious directional regressions even when they are excluded from the formal worst-slice gate.

### Progression rules for later PoCs

- The hybrid anchor-plus-residual PoC is attempted only if either the stronger tabular baseline or the comparables-anchor baseline improves global fair-value MDAPE by at least 3% relative without violating the regression guardrails.
- If both earlier PoCs qualify, the hybrid may combine the stronger parts of each, but it must still be evaluated as a fresh candidate against the original shipped baseline.
- If neither earlier PoC qualifies, the hybrid PoC is skipped.

### Statistical guardrails

- Compute bootstrap confidence intervals for the delta between each candidate and the baseline on global fair-value MDAPE and worst-slice MDAPE.
- Use a 95% bootstrap confidence interval with fixed seed and a documented resampling count.
- Use fixed seeds for both model training and bootstrap resampling.
- Any hyperparameter search must use the same documented and bounded budget for every candidate family.
- `Null or harmful result` means the interval includes zero improvement or crosses into regression relative to the allowed threshold for that metric.
- `Worst-slice MDAPE` must be computed over the eligible slice universe only: route, rarity, support bucket, and key item family slices with at least 100 evaluation examples.
- `Unstable across windows` means the direction of the candidate-vs-baseline delta changes sign in at least 30% of evaluation windows or the 95% interval width exceeds half of the claimed relative improvement; such a result is inconclusive and should not be used to justify implementation.

The same paired-bootstrap and window-stability rules apply to fast-sale hit rate and sale-probability calibration whenever those outputs are produced by a candidate.

### Allowed research inputs

PoCs may use the current `v3` data contract and may derive new offline-only features from already available repo-accessible historical data, but they may not require new migrations, new production pipelines, or new online-serving dependencies in this phase. Any derived offline-only feature set must be described explicitly in the methodology artifact.

## Decision Rules

A candidate is considered implementation-worthy only if it:

- improves global fair-value MDAPE against the current baseline by at least 5% relative
- does not regress worst-slice MDAPE by more than 2% relative
- does not worsen fast-sale hit rate by more than 0.02 absolute
- does not worsen sale-probability calibration error by more than 0.01 absolute
- shows non-negative MDAPE delta in at least 3 of these 4 required slice groups: route, rarity, support bucket, key item family

The fast-sale and sale-probability gates apply only to candidates that produce those outputs. Price-only candidates cannot clear the full implementation bar and therefore cannot be recommended as `implement` in this phase.

If no candidate clears that bar, the outcome of this phase is `do not pursue`.

`Maybe` is allowed only when a candidate shows promising but inconclusive results: for example, it clears the global improvement bar but confidence intervals remain too wide, or it improves overall accuracy while creating unresolved slice risk. In that case, the recommendation is additional research only, not implementation.

An `implement` recommendation requires both threshold success and statistical-guardrail success. Point-estimate wins alone are insufficient.

If multiple candidates pass, winner selection follows this order:

1. best global fair-value MDAPE improvement
2. better worst-slice MDAPE
3. better fast-sale hit rate
4. lower implementation complexity, scored by a fixed rubric: fewer new moving parts, fewer new data dependencies, and fewer production-surface changes required in a later phase

If top candidates remain effectively tied after those checks, the outcome is `maybe` rather than an implementation recommendation.

## Deliverables

The research PoC phase should produce:

- a ranked comparison of baseline and candidate approaches
- per-slice metric tables
- bootstrap confidence-interval outputs for candidate-vs-baseline deltas
- a short write-up describing what won, what lost, and why
- an implementation recommendation with one of: `implement`, `maybe`, `do not pursue`

Artifacts should be written into repo-visible locations:

- research notes and methodology in `docs/research/`
- run evidence and metric outputs in `docs/evidence/`
- the final recommendation summary in `docs/superpowers/specs/` or a linked follow-up plan, depending on outcome

At minimum, reproducible outputs must include:

- window definitions and evaluated leagues
- candidate configuration summaries
- raw metric tables and summary tables
- bootstrap interval outputs
- exact commands or scripts used to generate the evidence
- repo-visible script or config locations for each run
- candidate manifests and run IDs or equivalent artifact names
- a per-candidate decision record stating `passed`, `failed`, or `skipped`, plus the exact gate or rationale responsible for that outcome
- a repo-visible reusable evaluation entrypoint or harness configuration that reproduces the candidate-vs-baseline comparison

## Out of Scope

- production model training changes
- offline PoC findings may inform a later implementation plan, but they do not authorize production training changes in this phase
- serving path changes in `poe_trade/ml/v3/serve.py`
- API changes in `poe_trade/api/ml.py` or `poe_trade/api/ops.py`
- schema changes or new migrations
- rollout, cutover, or shadow serving

## Next Step

If this design is accepted after review, the next artifact should be an implementation plan for the research-and-PoC phase only, with no production implementation tasks mixed in.
