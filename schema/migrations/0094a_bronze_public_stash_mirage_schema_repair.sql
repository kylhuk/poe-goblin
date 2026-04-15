ALTER TABLE poe_trade.bronze_public_stash_mirage
    ADD COLUMN IF NOT EXISTS realm LowCardinality(String) AFTER ingested_at;

ALTER TABLE poe_trade.bronze_public_stash_mirage
    ADD COLUMN IF NOT EXISTS league LowCardinality(String) AFTER realm;

ALTER TABLE poe_trade.bronze_public_stash_mirage
    ADD COLUMN IF NOT EXISTS stash_json_id Nullable(String) CODEC(ZSTD(3)) AFTER stash_id;

ALTER TABLE poe_trade.bronze_public_stash_mirage
    ADD COLUMN IF NOT EXISTS next_change_id String CODEC(ZSTD(3)) AFTER checkpoint;
