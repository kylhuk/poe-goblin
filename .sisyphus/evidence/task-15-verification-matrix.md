# Task 15 Verification Matrix

- Backend full unit matrix: `.venv/bin/pytest tests/unit` -> `239 passed`
- Backend API/strategy/ML matrix: `.venv/bin/pytest tests/unit/test_api_*.py tests/unit/test_strategy_*.py tests/unit/test_ml_*.py` -> `103 passed`
- Frontend unit tests: `cd frontend && npm run test` -> `5 passed`
- Frontend inventory checks: `cd frontend && npm run test:inventory` -> `4 passed`
- Frontend Playwright suites: `cd frontend && npx playwright test` -> `6 passed`
- Full QA gate: `make qa-verify-product` -> pass (`pytest`, `vitest`, `vite build`, `test:inventory`, `playwright`, `poe_trade.evidence_bundle`)

## Deterministic QA workflows

- `make qa-up` completed and services reached healthy/exited expected states.
- `make qa-seed` wrote deterministic fixture proof at `.sisyphus/evidence/product/task-1-qa-environment/qa-seed.json`.
- Fault profile workflow completed:
  - `make qa-fault-scanner`
  - `make qa-fault-stash-empty`
  - `make qa-fault-api-unavailable`
  - `make qa-fault-service-action-failure`
  - `make qa-fault-clear`

## Live API smoke

- Deployed frontend URL: `https://poe.lama-lan.ch`
- Deployed API URL: `https://api.poe.lama-lan.ch`
- `GET /healthz` returned `200` with `{"status":"ok","service":"api","version":"v1"}`.
- `GET /api/v1/ops/scanner/summary` returned `200` with CORS allowed for `https://poe.lama-lan.ch`.
- `GET /api/v1/ops/analytics/report` returned `200` with truthful `status:"empty"` payload.
- `GET /api/v1/stash/status?league=Mirage&realm=pc` returned `200` with `feature_unavailable` payload on the deployed environment.
- Live browser smoke was captured at `.sisyphus/evidence/product/task-15-live-smoke/live-proof.png` after restoring the API CORS origin back to `https://poe.lama-lan.ch`.

## User-facing browser proof

- Playwright suite generated inventory artifacts in `.sisyphus/evidence/product/task-2-scenario-inventory/`.
- MCP Playwright browser screenshots captured at:
  - `.sisyphus/evidence/product/task-15-final-verification/playwright-mcp-dashboard.png`
  - `.sisyphus/evidence/product/task-15-final-verification/playwright-mcp-analytics.png`
  - `.sisyphus/evidence/product/task-13-auth-shell/connect-success.png`
  - `.sisyphus/evidence/product/task-13-auth-shell/connect-failure.png`
  - `.sisyphus/evidence/product/task-15-live-smoke/live-proof.png`
