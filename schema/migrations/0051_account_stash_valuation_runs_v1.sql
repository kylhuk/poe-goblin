CREATE TABLE IF NOT EXISTS poe_trade.account_stash_valuation_runs (
    scan_id String,
    account_name String,
    league String,
    realm String,
    status LowCardinality(String),
    started_at DateTime64(3, 'UTC'),
    completed_at Nullable(DateTime64(3, 'UTC')),
    failed_at Nullable(DateTime64(3, 'UTC')),
    tabs_total UInt32,
    tabs_processed UInt32,
    items_total UInt32,
    items_processed UInt32,
    error_message String,
    published_at Nullable(DateTime64(3, 'UTC'))
) ENGINE = ReplacingMergeTree(started_at)
PARTITION BY (league, toYYYYMMDD(started_at))
ORDER BY (account_name, realm, league, scan_id);

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_items (
    scan_id String,
    account_name String,
    league String,
    realm String,
    tab_id String,
    tab_name String,
    tab_type String,
    item_fingerprint String,
    item_id Nullable(String),
    item_name String,
    item_class String,
    rarity LowCardinality(String),
    x UInt16,
    y UInt16,
    w UInt16,
    h UInt16,
    listed_price Nullable(Float64),
    currency LowCardinality(String),
    icon_url String,
    source_observed_at DateTime64(3, 'UTC'),
    payload_json String
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(source_observed_at))
ORDER BY (account_name, realm, league, scan_id, tab_id, item_fingerprint);

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_item_valuations (
    scan_id String,
    account_name String,
    league String,
    realm String,
    tab_id String,
    item_fingerprint String,
    item_id Nullable(String),
    item_name String,
    item_class String,
    rarity LowCardinality(String),
    listed_price Nullable(Float64),
    predicted_price Float64,
    confidence Float64,
    price_p10 Nullable(Float64),
    price_p90 Nullable(Float64),
    comparable_count UInt32,
    fallback_reason String,
    priced_at DateTime64(3, 'UTC'),
    payload_json String
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(priced_at))
ORDER BY (account_name, realm, league, item_fingerprint, priced_at, scan_id);

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_active_scans (
    account_name String,
    league String,
    realm String,
    scan_id String,
    published_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(published_at)
PARTITION BY league
ORDER BY (account_name, realm, league);

GRANT SELECT, INSERT ON poe_trade.account_stash_valuation_runs TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_scan_items TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_item_valuations TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_active_scans TO poe_api_reader;

GRANT INSERT ON poe_trade.account_stash_valuation_runs TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_scan_items TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_item_valuations TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_active_scans TO poe_ingest_writer;
