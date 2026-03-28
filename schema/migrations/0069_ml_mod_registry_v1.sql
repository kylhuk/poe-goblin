CREATE TABLE IF NOT EXISTS poe_trade.ml_mod_registry_v1 (
    mod_id String,
    mod_name String,
    mod_type LowCardinality(String),
    mod_text String,
    domain LowCardinality(String),
    generation_type LowCardinality(String),
    required_level UInt16,
    is_essence_only UInt8,
    gold_value Nullable(Float64),
    groups Array(String),
    adds_tags Array(String),
    implicit_tags Array(String),
    spawn_weight_tags Array(String),
    spawn_weight_values Array(Int32),
    generation_weight_tags Array(String),
    generation_weight_values Array(Int32),
    grant_effect_ids Array(String),
    grant_effect_levels Array(UInt16),
    stat_ids Array(String),
    stat_mins Array(Int32),
    stat_maxs Array(Int32),
    source_url String,
    source_json String,
    updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (mod_id)
SETTINGS index_granularity = 8192;
