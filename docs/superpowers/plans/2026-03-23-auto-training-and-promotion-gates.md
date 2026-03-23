# Automatic Hybrid Training and Promotion Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hybrid ML v3 training run automatically on Docker startup when artifacts are missing or stale, and promote only when balanced quality gates pass.

**Architecture:** Keep the existing v3 serving path, but add a startup-triggered training orchestrator that checks artifact freshness, launches training asynchronously, and records the outcome in the existing ML status surfaces. Promotion should stay deterministic and conservative: require fair-value improvement, cap fast-sale regression, and enforce minimum support/confidence thresholds before swapping the active bundle.

**Tech Stack:** Python 3.11, ClickHouse, existing `poe_trade.ml.v3` modules, pytest, Docker Compose, current ML status/reporting surfaces.

---

### Task 1: Define freshness and startup training trigger

**Files:**
- Modify: `poe_trade/services/ml_trainer.py`
- Modify: `poe_trade/ml/workflows.py`
- Test: `tests/unit/test_service_ml_trainer.py`

- [ ] **Step 1: Write failing tests for stale/missing artifact detection and startup trigger**

```python
def test_trainer_triggers_auto_run_when_bundle_missing() -> None:
    ...

def test_trainer_skips_auto_run_when_bundle_is_fresh() -> None:
    ...
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/unit/test_service_ml_trainer.py -k "auto_run or fresh" -v`
Expected: FAIL because no startup freshness gate exists yet.

- [ ] **Step 3: Implement a minimal freshness check and startup trigger flag**

```python
def should_auto_train(bundle_state: Mapping[str, Any], *, now: datetime) -> bool:
    ...
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/unit/test_service_ml_trainer.py -k "auto_run or fresh" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/services/ml_trainer.py poe_trade/ml/workflows.py tests/unit/test_service_ml_trainer.py
git commit -m "feat: add hybrid training startup gate"
```

### Task 2: Add balanced promotion gates

**Files:**
- Modify: `poe_trade/ml/v3/train.py`
- Modify: `poe_trade/ml/v3/eval.py`
- Test: `tests/unit/test_ml_v3_train.py`
- Test: `tests/unit/test_ml_v3_eval.py`

- [ ] **Step 1: Write failing tests for promotion decision thresholds**

```python
def test_promote_requires_fair_value_improvement() -> None:
    ...

def test_promote_rejects_large_fast_sale_regression() -> None:
    ...
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_train.py tests/unit/test_ml_v3_eval.py -k promotion -v`
Expected: FAIL because no balanced gate exists yet.

- [ ] **Step 3: Implement promotion gate calculation**

```python
def should_promote_hybrid(candidate: Mapping[str, Any], incumbent: Mapping[str, Any]) -> bool:
    ...
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/unit/test_ml_v3_train.py tests/unit/test_ml_v3_eval.py -k promotion -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/ml/v3/train.py poe_trade/ml/v3/eval.py tests/unit/test_ml_v3_train.py tests/unit/test_ml_v3_eval.py
git commit -m "feat: add balanced hybrid promotion gates"
```

### Task 3: Wire automatic startup training into service startup

**Files:**
- Modify: `poe_trade/services/ml_trainer.py`
- Modify: `poe_trade/cli.py` or the service entrypoint used by Docker startup
- Modify: `poe_trade/ml/workflows.py`
- Test: `tests/unit/test_service_ml_trainer.py`

- [ ] **Step 1: Write failing tests for non-blocking startup training**

```python
def test_startup_launches_training_in_background_when_stale() -> None:
    ...

def test_startup_does_not_block_service_boot() -> None:
    ...
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/unit/test_service_ml_trainer.py -k startup -v`
Expected: FAIL because startup orchestration is not implemented yet.

- [ ] **Step 3: Implement the background training launch and cooldown handling**

```python
def maybe_start_auto_training(...):
    ...
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/unit/test_service_ml_trainer.py -k startup -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/services/ml_trainer.py poe_trade/cli.py poe_trade/ml/workflows.py tests/unit/test_service_ml_trainer.py
git commit -m "feat: auto-start hybrid training on boot"
```

### Task 4: Preserve status/reporting for training failures and promotion decisions

**Files:**
- Modify: `poe_trade/api/ml.py`
- Modify: `poe_trade/services/ml_trainer.py`
- Test: `tests/unit/test_api_ml_routes.py`
- Test: `tests/unit/test_service_ml_trainer.py`

- [ ] **Step 1: Write failing tests for surfaced auto-training state**

```python
def test_ml_status_reports_auto_training_and_promotion_state() -> None:
    ...
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/bin/pytest tests/unit/test_api_ml_routes.py tests/unit/test_service_ml_trainer.py -k auto_training -v`
Expected: FAIL because the status payload does not yet expose the new state.

- [ ] **Step 3: Add status fields for auto-training and promotion gates**

```python
payload["autoTraining"] = ...
payload["promotionGates"] = ...
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `.venv/bin/pytest tests/unit/test_api_ml_routes.py tests/unit/test_service_ml_trainer.py -k auto_training -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/api/ml.py poe_trade/services/ml_trainer.py tests/unit/test_api_ml_routes.py tests/unit/test_service_ml_trainer.py
git commit -m "feat: expose hybrid training status"
```

### Task 5: Verify Docker startup and frontend/backend regressions

**Files:**
- Test: `tests/unit/test_service_ml_trainer.py`
- Test: `tests/unit/test_api_ml_routes.py`
- Test: `tests/unit/test_ml_v3_train.py`
- Test: `tests/unit/test_ml_v3_eval.py`

- [ ] **Step 1: Run the focused backend suite**

Run: `.venv/bin/pytest tests/unit/test_service_ml_trainer.py tests/unit/test_api_ml_routes.py tests/unit/test_ml_v3_train.py tests/unit/test_ml_v3_eval.py -v`
Expected: PASS.

- [ ] **Step 2: Run the frontend contract tests if exposed status fields affect UI**

Run: `npm --prefix frontend exec vitest run src/services/api.test.ts src/components/tabs/PriceCheckTab.test.tsx`
Expected: PASS.

- [ ] **Step 3: Validate Docker startup wiring**

Run: `docker compose config`
Expected: PASS and show the service still starts with the trainer hook wired in.

- [ ] **Step 4: Commit any last verification fixes**

```bash
git add .
git commit -m "test: verify automatic hybrid training startup"
```
