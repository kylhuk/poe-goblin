CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_cohort_eval (
    run_id String,
    league LowCardinality(String),
    route LowCardinality(String),
    strategy_family LowCardinality(String),
    cohort_key String,
    family LowCardinality(String),
    support_bucket LowCardinality(String),
    split_kind LowCardinality(String),
    sample_count UInt64,
    fair_value_mdape Nullable(Float64),
    fair_value_wape Nullable(Float64),
    fast_sale_24h_hit_rate Nullable(Float64),
    fast_sale_24h_mdape Nullable(Float64),
    sale_probability_calibration_error Nullable(Float64),
    confidence_calibration_error Nullable(Float64),
    abstain_rate Nullable(Float64),
    recorded_at DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(1))
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(recorded_at)
ORDER BY (league, run_id, strategy_family, cohort_key, recorded_at)
SETTINGS index_granularity = 8192;

ALTER TABLE poe_trade.ml_v3_cohort_eval
    ADD COLUMN IF NOT EXISTS run_id String,
    ADD COLUMN IF NOT EXISTS league LowCardinality(String),
    ADD COLUMN IF NOT EXISTS route LowCardinality(String),
    ADD COLUMN IF NOT EXISTS strategy_family LowCardinality(String),
    ADD COLUMN IF NOT EXISTS cohort_key String,
    ADD COLUMN IF NOT EXISTS family LowCardinality(String),
    ADD COLUMN IF NOT EXISTS support_bucket LowCardinality(String),
    ADD COLUMN IF NOT EXISTS split_kind LowCardinality(String),
    ADD COLUMN IF NOT EXISTS sample_count UInt64,
    ADD COLUMN IF NOT EXISTS fair_value_mdape Nullable(Float64),
    ADD COLUMN IF NOT EXISTS fair_value_wape Nullable(Float64),
    ADD COLUMN IF NOT EXISTS fast_sale_24h_hit_rate Nullable(Float64),
    ADD COLUMN IF NOT EXISTS fast_sale_24h_mdape Nullable(Float64),
    ADD COLUMN IF NOT EXISTS sale_probability_calibration_error Nullable(Float64),
    ADD COLUMN IF NOT EXISTS confidence_calibration_error Nullable(Float64),
    ADD COLUMN IF NOT EXISTS abstain_rate Nullable(Float64),
    ADD COLUMN IF NOT EXISTS recorded_at DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(1));
