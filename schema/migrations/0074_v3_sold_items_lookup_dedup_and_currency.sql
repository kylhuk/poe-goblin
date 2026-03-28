CREATE TABLE IF NOT EXISTS poe_trade.silver_v3_sold_items_lookup_v2 (
    sold_at DateTime64(3, 'UTC'),
    league LowCardinality(String),
    realm LowCardinality(String),
    stash_id String,
    item_id String,
    price Nullable(Float64),
    currency LowCardinality(String),
    identity_key String,
    inserted_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMMDD(sold_at)
ORDER BY (league, realm, stash_id, sold_at, item_id)
SETTINGS index_granularity = 8192;

INSERT INTO poe_trade.silver_v3_sold_items_lookup_v2
SELECT
    sold_at,
    league,
    realm,
    stash_id,
    item_id,
    price,
    currency,
    identity_key,
    max(inserted_at) AS inserted_at
FROM (
    SELECT
        e.current_observed_at AS sold_at,
        e.league,
        e.realm,
        e.stash_id,
        o.item_id,
        o.parsed_amount AS price,
        coalesce(nullIf(lowerUTF8(trimBoth(o.parsed_currency)), ''), 'chaos') AS currency,
        e.identity_key,
        now64(3) AS inserted_at
    FROM poe_trade.silver_v3_item_events AS e
    INNER JOIN poe_trade.silver_v3_item_observations AS o
        ON o.league = e.league
       AND o.realm = e.realm
       AND o.stash_id = e.stash_id
       AND o.identity_key = e.identity_key
       AND o.observed_at = e.previous_observed_at
    WHERE e.event_type = 'disappeared'
      AND toDate(e.event_ts) = toDate('2026-03-16')
      AND o.parsed_amount IS NOT NULL
      AND o.observed_at >= toDateTime64('2026-03-15 00:00:00', 3, 'UTC')
      AND o.observed_at < toDateTime64('2026-03-17 00:00:00', 3, 'UTC')

    UNION ALL

    SELECT
        e.current_observed_at AS sold_at,
        e.league,
        e.realm,
        e.stash_id,
        o.item_id,
        o.parsed_amount AS price,
        coalesce(nullIf(lowerUTF8(trimBoth(o.parsed_currency)), ''), 'chaos') AS currency,
        e.identity_key,
        now64(3) AS inserted_at
    FROM poe_trade.silver_v3_item_events AS e
    INNER JOIN poe_trade.silver_v3_item_observations AS o
        ON o.league = e.league
       AND o.realm = e.realm
       AND o.stash_id = e.stash_id
       AND o.identity_key = e.identity_key
       AND o.observed_at = e.previous_observed_at
    WHERE e.event_type = 'disappeared'
      AND toDate(e.event_ts) = toDate('2026-03-19')
      AND o.parsed_amount IS NOT NULL
      AND o.observed_at >= toDateTime64('2026-03-18 00:00:00', 3, 'UTC')
      AND o.observed_at < toDateTime64('2026-03-20 00:00:00', 3, 'UTC')

    UNION ALL

    SELECT
        e.current_observed_at AS sold_at,
        e.league,
        e.realm,
        e.stash_id,
        o.item_id,
        o.parsed_amount AS price,
        coalesce(nullIf(lowerUTF8(trimBoth(o.parsed_currency)), ''), 'chaos') AS currency,
        e.identity_key,
        now64(3) AS inserted_at
    FROM poe_trade.silver_v3_item_events AS e
    INNER JOIN poe_trade.silver_v3_item_observations AS o
        ON o.league = e.league
       AND o.realm = e.realm
       AND o.stash_id = e.stash_id
       AND o.identity_key = e.identity_key
       AND o.observed_at = e.previous_observed_at
    WHERE e.event_type = 'disappeared'
      AND toDate(e.event_ts) = toDate('2026-03-22')
      AND o.parsed_amount IS NOT NULL
      AND o.observed_at >= toDateTime64('2026-03-21 00:00:00', 3, 'UTC')
      AND o.observed_at < toDateTime64('2026-03-23 00:00:00', 3, 'UTC')
 ) AS src (sold_at, league, realm, stash_id, item_id, price, currency, identity_key, inserted_at)
GROUP BY
    sold_at,
    league,
    realm,
    stash_id,
    item_id,
    price,
    currency,
    identity_key;

DROP VIEW IF EXISTS poe_trade.v_account_stash_sold_items;

CREATE VIEW poe_trade.v_account_stash_sold_items AS
SELECT
    stash_id,
    item_id,
    sold_at,
    price,
    currency
FROM poe_trade.silver_v3_sold_items_lookup_v2 FINAL;
