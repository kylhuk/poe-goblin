CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_listing_episodes(
    as_of_ts DateTime64(3, 'UTC'), realm String, league String, stash_id String,
    item_id Nullable(String), identity_key String, listing_episode_id String,
    first_seen DateTime64(3, 'UTC'), last_seen DateTime64(3, 'UTC'),
    snapshot_count UInt32, latest_price Nullable(Float64), min_price Nullable(Float64),
    latest_price_divine Nullable(Float64), min_price_divine Nullable(Float64),
    fx_hour Nullable(DateTime64(0, 'UTC')), fx_source LowCardinality(String),
    fx_chaos_per_divine Nullable(Float64),
    category String, route String, strategy_family String, cohort_key String,
    material_state_signature String, item_name String, item_type_line String,
    base_type String, rarity Nullable(String), ilvl UInt16, stack_size UInt32,
    corrupted UInt8, fractured UInt8, synthesised UInt8, item_state_key String,
    support_count_recent UInt32, feature_vector_json String, mod_features_json String,
    target_price_chaos Nullable(Float64), target_fast_sale_24h_price Nullable(Float64),
    target_price_divine Nullable(Float64), target_fast_sale_24h_price_divine Nullable(Float64),
    target_sale_probability_24h Nullable(Float32), target_likely_sold UInt8,
    sale_confidence_flag UInt8, target_time_to_exit_hours Nullable(Float64),
    target_sale_price_anchor_chaos Nullable(Float64), label_weight Float32,
    label_source String, label_quality String, split_bucket UInt16, inserted_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(inserted_at) PARTITION BY toYYYYMMDD(as_of_ts) ORDER BY (league, realm, stash_id, listing_episode_id, as_of_ts);

ALTER TABLE poe_trade.ml_v3_listing_episodes
    ADD COLUMN IF NOT EXISTS latest_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS min_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS fx_hour Nullable(DateTime64(0, 'UTC')),
    ADD COLUMN IF NOT EXISTS fx_source LowCardinality(String),
    ADD COLUMN IF NOT EXISTS fx_chaos_per_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_fast_sale_24h_price_divine Nullable(Float64);

ALTER TABLE poe_trade.ml_v3_training_examples
    ADD COLUMN IF NOT EXISTS fx_hour Nullable(DateTime64(0, 'UTC')),
    ADD COLUMN IF NOT EXISTS fx_source LowCardinality(String),
    ADD COLUMN IF NOT EXISTS fx_chaos_per_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_fast_sale_24h_price_divine Nullable(Float64);
