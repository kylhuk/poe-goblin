CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_items_v2 (
    scan_id String,
    account_name String,
    league String,
    realm String,
    tab_id String,
    tab_index UInt16,
    tab_name String,
    tab_type String,
    lineage_key String,
    content_signature String,
    item_position_key String,
    item_id String,
    item_name String,
    base_type String,
    item_class String,
    rarity LowCardinality(String),
    x UInt16,
    y UInt16,
    w UInt16,
    h UInt16,
    listed_price Nullable(Float64),
    listed_currency LowCardinality(String),
    listed_price_chaos Nullable(Float64),
    estimated_price_chaos Nullable(Float64),
    price_p10_chaos Nullable(Float64),
    price_p90_chaos Nullable(Float64),
    price_delta_chaos Nullable(Float64),
    price_delta_pct Nullable(Float64),
    price_band LowCardinality(String),
    price_band_version UInt16,
    confidence Float64,
    estimate_trust LowCardinality(String),
    estimate_warning String,
    fallback_reason String,
    explicit_mods_json String CODEC(ZSTD(3)),
    icon_url String,
    priced_at DateTime64(3, 'UTC'),
    payload_json String CODEC(ZSTD(6))
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(priced_at))
ORDER BY (account_name, realm, league, scan_id, tab_index, y, x, item_id)
TTL priced_at + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_item_history_v2 (
    scan_id String,
    account_name String,
    league String,
    realm String,
    tab_id String,
    tab_index UInt16,
    tab_name String,
    tab_type String,
    lineage_key String,
    content_signature String,
    item_position_key String,
    item_id String,
    item_name String,
    base_type String,
    item_class String,
    rarity LowCardinality(String),
    x UInt16,
    y UInt16,
    w UInt16,
    h UInt16,
    listed_price Nullable(Float64),
    listed_currency LowCardinality(String),
    listed_price_chaos Nullable(Float64),
    estimated_price_chaos Nullable(Float64),
    price_p10_chaos Nullable(Float64),
    price_p90_chaos Nullable(Float64),
    price_delta_chaos Nullable(Float64),
    price_delta_pct Nullable(Float64),
    price_band LowCardinality(String),
    price_band_version UInt16,
    confidence Float64,
    estimate_trust LowCardinality(String),
    estimate_warning String,
    fallback_reason String,
    explicit_mods_json String CODEC(ZSTD(3)),
    icon_url String,
    priced_at DateTime64(3, 'UTC'),
    payload_json String CODEC(ZSTD(6))
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(priced_at))
ORDER BY (account_name, realm, league, lineage_key, priced_at, scan_id)
TTL priced_at + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192;

CREATE VIEW IF NOT EXISTS poe_trade.v_account_stash_latest_scan_items AS
SELECT
    items.*
FROM poe_trade.account_stash_scan_items_v2 AS items
INNER JOIN (
    SELECT
        account_name,
        league,
        realm,
        argMax(scan_id, published_at) AS scan_id
    FROM poe_trade.account_stash_published_scans
    GROUP BY
        account_name,
        league,
        realm
) AS latest
ON latest.account_name = items.account_name
AND latest.league = items.league
AND latest.realm = items.realm
AND latest.scan_id = items.scan_id;

ALTER TABLE poe_trade.account_stash_scan_tabs
    MODIFY TTL captured_at + INTERVAL 90 DAY DELETE;

ALTER TABLE poe_trade.account_stash_item_valuations
    MODIFY TTL priced_at + INTERVAL 90 DAY DELETE;

GRANT INSERT ON poe_trade.account_stash_scan_items_v2 TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_item_history_v2 TO poe_ingest_writer;
GRANT SELECT ON poe_trade.account_stash_scan_items_v2 TO poe_api_reader;
GRANT SELECT ON poe_trade.account_stash_item_history_v2 TO poe_api_reader;
GRANT SELECT ON poe_trade.v_account_stash_latest_scan_items TO poe_api_reader;
