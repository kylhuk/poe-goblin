CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_runs (
    scan_id String,
    account_name String,
    league String,
    realm String,
    status LowCardinality(String),
    started_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    completed_at Nullable(DateTime64(3, 'UTC')),
    published_at Nullable(DateTime64(3, 'UTC')),
    failed_at Nullable(DateTime64(3, 'UTC')),
    tabs_total UInt32,
    tabs_processed UInt32,
    items_total UInt32,
    items_processed UInt32,
    error_message String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY (league, toYYYYMMDD(started_at))
ORDER BY (account_name, realm, league, scan_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_tabs (
    scan_id String,
    account_name String,
    league String,
    realm String,
    tab_id String,
    tab_index UInt16,
    tab_name String,
    tab_type String,
    captured_at DateTime64(3, 'UTC'),
    tab_meta_json String,
    payload_json String
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(captured_at))
ORDER BY (account_name, realm, league, scan_id, tab_index, tab_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_item_valuations (
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
    item_class String,
    rarity LowCardinality(String),
    x UInt16,
    y UInt16,
    w UInt16,
    h UInt16,
    listed_price Nullable(Float64),
    currency LowCardinality(String),
    predicted_price Float64,
    confidence Float64,
    price_p10 Nullable(Float64),
    price_p90 Nullable(Float64),
    price_recommendation_eligible UInt8,
    estimate_trust LowCardinality(String),
    estimate_warning String,
    fallback_reason String,
    icon_url String,
    priced_at DateTime64(3, 'UTC'),
    payload_json String
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(priced_at))
ORDER BY (account_name, realm, league, lineage_key, priced_at, scan_id, tab_index)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_active_scans (
    account_name String,
    league String,
    realm String,
    scan_id String,
    is_active UInt8,
    started_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY league
ORDER BY (account_name, realm, league)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_published_scans (
    account_name String,
    league String,
    realm String,
    scan_id String,
    published_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(published_at)
PARTITION BY league
ORDER BY (account_name, realm, league)
SETTINGS index_granularity = 8192;

GRANT SELECT, INSERT ON poe_trade.account_stash_scan_runs TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_scan_tabs TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_item_valuations TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_active_scans TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_published_scans TO poe_api_reader;
GRANT INSERT ON poe_trade.account_stash_scan_runs TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_scan_tabs TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_item_valuations TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_active_scans TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_published_scans TO poe_ingest_writer;
