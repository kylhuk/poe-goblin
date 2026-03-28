# poe_trade

## Docker workflow

- `make up` = fast dev start for the core stack, no `--build`
- `make build` = explicit image refresh for app services
- `make rebuild` = refresh images, then restart the stack if needed
- repo-root edits under the mounted source tree no longer force Docker rebuilds

## Services

- ClickHouse, schema_migrator, market_harvester, scanner_worker, ml_trainer, poeninja_snapshot, and api
- account_stash_harvester
