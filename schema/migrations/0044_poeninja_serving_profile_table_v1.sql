CREATE TABLE IF NOT EXISTS poe_trade.ml_serving_profile_v1 (
    profile_as_of_ts DateTime64(3, 'UTC'),
    snapshot_window_id String,
    league String,
    category String,
    base_type String,
    support_count_recent UInt64,
    reference_price_p10 Float64,
    reference_price_p50 Float64,
    reference_price_p90 Float64,
    updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMMDD(profile_as_of_ts)
ORDER BY (league, category, base_type, profile_as_of_ts, updated_at);
