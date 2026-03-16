
- Task 1: defaulted `recommendation_source` to `strategy_pack`, `producer_version` to backend package version, and `producer_run_id` to `scanner_run_id` so existing SQL producers emit stable provenance without adding new strategy-pack requirements yet.
- Task 1: kept new ClickHouse metadata columns nullable instead of backfilling defaults in-place, then filled legacy API fallbacks in Python (`contractVersion=1`, source fallback, producer run fallback) to preserve old-row readability.
- Task 1: introduced migration-safe query/insert fallbacks around scanner metadata reads and writes so code remains runnable during staggered deploy-vs-migrate rollouts.
