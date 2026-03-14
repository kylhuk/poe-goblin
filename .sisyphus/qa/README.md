# Disposable QA Contract

This QA profile is disposable and local-only. It is designed for deterministic browser/API evidence runs.

## Commands

- `make qa-up` starts the QA stack using `docker-compose.yml` + `docker-compose.qa.yml`.
- `make qa-seed` resets QA fixture tables and writes deterministic seed evidence to `.sisyphus/evidence/product/task-1-qa-environment/qa-seed.json`.
- `make qa-fault-scanner` enables scanner degraded fault mode and writes evidence.
- `make qa-fault-stash-empty` enables stash-empty fault mode and writes evidence.
- `make qa-fault-api-unavailable` enables API-unavailable fault mode and writes evidence.
- `make qa-fault-service-action-failure` enables service-action-failure fault mode and writes evidence.
- `make qa-fault-clear` resets all fault toggles.
- `make qa-down` stops and removes the disposable stack.
- `make qa-frontend` runs frontend runtime for Playwright at `http://127.0.0.1:4173`.

## State files

- Fault toggles: `.sisyphus/state/qa/faults.json`
- Simulated authenticated account session: `.sisyphus/state/qa/auth-session.json`

## Deterministic seed scope

`qa-seed` writes fixtures for:

- scanner recommendations + scanner alert log
- stash snapshot tabs/items in `raw_account_stash_snapshot`
- ingest status rows for public and account stash pipelines
- ML train + promotion audit rows
- simulated authenticated account session metadata for QA login/session flows

All seed/fault commands are machine-readable and produce JSON artifacts under `.sisyphus/evidence/product/task-1-qa-environment/`.
