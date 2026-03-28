CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_mirage_iron_ring_branch_v1 (
    observed_at DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(1)),
    realm LowCardinality(String),
    league LowCardinality(String),
    stash_id String CODEC(ZSTD(6)),
    account_name Nullable(String),
    stash_name Nullable(String),
    checkpoint String,
    next_change_id String,
    item_id Nullable(String),
    identity_key String,
    fingerprint_v3 String,
    item_name String,
    item_type_line String,
    base_type String,
    rarity LowCardinality(String),
    category LowCardinality(String),
    ilvl UInt16,
    stack_size UInt32,
    corrupted UInt8,
    fractured UInt8,
    synthesised UInt8,
    note Nullable(String),
    forum_note Nullable(String),
    effective_price_note Nullable(String),
    parsed_amount Nullable(Float64),
    parsed_currency Nullable(String),
    normalized_affix_hash String,
    affix_payload_json String CODEC(ZSTD(6)),
    item_json String CODEC(ZSTD(6)),
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(observed_at)
ORDER BY (league, realm, stash_id, identity_key, observed_at)
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_silver_v3_item_observations_to_ml_v3_mirage_iron_ring_branch_v1
TO poe_trade.ml_v3_mirage_iron_ring_branch_v1
AS
SELECT
    observed_at,
    realm,
    league,
    stash_id,
    account_name,
    stash_name,
    checkpoint,
    next_change_id,
    item_id,
    identity_key,
    fingerprint_v3,
    item_name,
    item_type_line,
    base_type,
    rarity,
    category,
    ilvl,
    stack_size,
    corrupted,
    fractured,
    synthesised,
    note,
    forum_note,
    effective_price_note,
    parsed_amount,
    parsed_currency,
    normalized_affix_hash,
    affix_payload_json,
    item_json,
    inserted_at
FROM poe_trade.silver_v3_item_observations
WHERE league = 'Mirage'
    AND category = 'ring'
    AND base_type = 'Iron Ring';

INSERT INTO poe_trade.ml_v3_mirage_iron_ring_branch_v1
SELECT
    observed_at,
    realm,
    league,
    stash_id,
    account_name,
    stash_name,
    checkpoint,
    next_change_id,
    item_id,
    identity_key,
    fingerprint_v3,
    item_name,
    item_type_line,
    base_type,
    rarity,
    category,
    ilvl,
    stack_size,
    corrupted,
    fractured,
    synthesised,
    note,
    forum_note,
    effective_price_note,
    parsed_amount,
    parsed_currency,
    normalized_affix_hash,
    affix_payload_json,
    item_json,
    inserted_at
FROM poe_trade.silver_v3_item_observations
WHERE league = 'Mirage'
    AND category = 'ring'
    AND base_type = 'Iron Ring';
