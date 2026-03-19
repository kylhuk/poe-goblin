# ML pricing deterministic evidence pack

## Purpose
- Enforce deterministic evidence for ML pricing promotion checks and rollout drills as part of `make ci-deterministic`.

## Required artifacts
- `.sisyphus/evidence/task-1-baseline.json` (baseline/candidate latency evidence source)
- `.sisyphus/evidence/task-10-promotion-gates.json` (MDAPE + protected cohort gate outcome)
- `.sisyphus/evidence/task-11-rollout-cutover.json` (controlled cutover drill proof)
- `.sisyphus/evidence/task-11-rollout-rollback.json` (rollback drill proof)

## Commands
- Happy path (writes deterministic pack log):
  - `make ci-deterministic-ml-evidence`
- Full deterministic gate (includes ML evidence enforcement):
  - `make ci-deterministic`
- Missing-artifact failure drill (expected non-zero exit):
  - `.venv/bin/python scripts/verify_ml_deterministic_pack.py --evidence-root .sisyphus/evidence --output-log .sisyphus/evidence/task-12-deterministic-pack-error.log --required task-1-baseline.json task-10-promotion-gates.json task-11-rollout-cutover.json task-11-rollout-rollback.json task-12-intentionally-missing.json`

## How to interpret results
- `status: "ok"` in `.sisyphus/evidence/task-12-deterministic-pack.log` means every required artifact exists, passes minimal JSON shape checks, and was hashed.
- `status: "missing_or_invalid_artifacts"` means enforcement failed; inspect both `missing` and `invalid` arrays and regenerate/fix those artifacts before rerunning deterministic gates.
