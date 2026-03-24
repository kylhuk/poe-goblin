CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_reference_snapshots (
    snapshot_as_of_ts DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(1)),
    league LowCardinality(String),
    route LowCardinality(String),
    category LowCardinality(String),
    base_type String,
    window_kind LowCardinality(String),
    window_hours UInt16,
    min_support UInt32,
    support_count_recent UInt64,
    reference_price_p10 Nullable(Float64),
    reference_price_p50 Nullable(Float64),
    reference_price_p90 Nullable(Float64),
    source_max_as_of_ts Nullable(DateTime64(3, 'UTC')) CODEC(Delta(8), ZSTD(1)),
    is_sufficient_support UInt8,
    updated_at DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(1))
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMMDD(snapshot_as_of_ts)
ORDER BY (league, route, category, base_type, window_kind, snapshot_as_of_ts)
SETTINGS index_granularity = 8192;

ALTER TABLE poe_trade.ml_v3_reference_snapshots
    ADD COLUMN IF NOT EXISTS snapshot_as_of_ts DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(1)),
    ADD COLUMN IF NOT EXISTS league LowCardinality(String),
    ADD COLUMN IF NOT EXISTS route LowCardinality(String),
    ADD COLUMN IF NOT EXISTS category LowCardinality(String),
    ADD COLUMN IF NOT EXISTS base_type String,
    ADD COLUMN IF NOT EXISTS window_kind LowCardinality(String),
    ADD COLUMN IF NOT EXISTS window_hours UInt16,
    ADD COLUMN IF NOT EXISTS min_support UInt32,
    ADD COLUMN IF NOT EXISTS support_count_recent UInt64,
    ADD COLUMN IF NOT EXISTS reference_price_p10 Nullable(Float64),
    ADD COLUMN IF NOT EXISTS reference_price_p50 Nullable(Float64),
    ADD COLUMN IF NOT EXISTS reference_price_p90 Nullable(Float64),
    ADD COLUMN IF NOT EXISTS source_max_as_of_ts Nullable(DateTime64(3, 'UTC')) CODEC(Delta(8), ZSTD(1)),
    ADD COLUMN IF NOT EXISTS is_sufficient_support UInt8,
    ADD COLUMN IF NOT EXISTS updated_at DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(1));
