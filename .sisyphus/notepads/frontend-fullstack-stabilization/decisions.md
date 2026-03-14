# Decisions

- Included `clickhouse`, `schema_migrator`, `market_harvester`, `scanner_worker`, `ml_trainer`, and `api` in the default `make up` command to align with the real product surface.
- Kept `account_stash_harvester` as an optional service that must be started explicitly, as it is credential-gated.
- Documented `ml_trainer` as part of the default background stack but clarified its role in ML automation.
- Updated `README.md` to reflect the new default startup and distinguish between core and optional services.
