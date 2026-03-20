CREATE TABLE IF NOT EXISTS poe_trade.ml_fx_hour_v2 (
    hour_ts DateTime64(0, 'UTC'),
    league String,
    currency String,
    chaos_equivalent Float64,
    fx_source LowCardinality(String),
    sample_time_utc DateTime64(3, 'UTC'),
    stale UInt8,
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(hour_ts)
ORDER BY (league, currency, hour_ts, sample_time_utc);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_raw_poeninja_to_ml_fx_hour_v2
TO poe_trade.ml_fx_hour_v2 AS
SELECT
    toStartOfHour(sample_time_utc) AS hour_ts,
    league,
    lowerUTF8(trimBoth(currency_type_name)) AS currency,
    chaos_equivalent,
    'poeninja' AS fx_source,
    sample_time_utc,
    stale,
    now64(3) AS inserted_at
FROM poe_trade.raw_poeninja_currency_overview;

CREATE TABLE IF NOT EXISTS poe_trade.ml_fx_hour_latest_states_v2 (
    league String,
    currency String,
    hour_ts DateTime64(0, 'UTC'),
    chaos_equivalent_state AggregateFunction(argMax, Float64, DateTime64(3, 'UTC')),
    sample_time_utc_state AggregateFunction(max, DateTime64(3, 'UTC')),
    stale_state AggregateFunction(argMax, UInt8, DateTime64(3, 'UTC')),
    fx_source_state AggregateFunction(argMax, String, DateTime64(3, 'UTC')),
    inserted_at SimpleAggregateFunction(max, DateTime64(3, 'UTC'))
) ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMMDD(hour_ts)
ORDER BY (league, currency, hour_ts);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_ml_fx_hour_latest_states_v2
TO poe_trade.ml_fx_hour_latest_states_v2 AS
SELECT
    league,
    currency,
    hour_ts,
    argMaxState(chaos_equivalent, sample_time_utc) AS chaos_equivalent_state,
    maxState(sample_time_utc) AS sample_time_utc_state,
    argMaxState(stale, sample_time_utc) AS stale_state,
    argMaxState(fx_source, sample_time_utc) AS fx_source_state,
    max(inserted_at) AS inserted_at
FROM poe_trade.ml_fx_hour_v2
GROUP BY league, currency, hour_ts;

CREATE VIEW IF NOT EXISTS poe_trade.ml_fx_hour_latest_v2 AS
SELECT
    league,
    currency,
    hour_ts,
    argMaxMerge(chaos_equivalent_state) AS chaos_equivalent,
    maxMerge(sample_time_utc_state) AS sample_time_utc,
    argMaxMerge(stale_state) AS stale,
    argMaxMerge(fx_source_state) AS fx_source,
    max(inserted_at) AS inserted_at
FROM poe_trade.ml_fx_hour_latest_states_v2
GROUP BY league, currency, hour_ts;

CREATE TABLE IF NOT EXISTS poe_trade.ml_listing_events_v2 (
    as_of_ts DateTime64(3, 'UTC'),
    realm String,
    league String,
    stash_id String,
    item_id Nullable(String),
    item_key String,
    listing_chain_id String,
    note_value Nullable(String),
    note_edited UInt8,
    relist_event UInt8,
    has_trade_metadata UInt8,
    evidence_source LowCardinality(String),
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(as_of_ts)
ORDER BY (league, realm, listing_chain_id, as_of_ts, item_key);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_silver_ps_items_to_listing_events_v2
TO poe_trade.ml_listing_events_v2 AS
SELECT
    items.observed_at AS as_of_ts,
    items.realm,
    ifNull(items.league, '') AS league,
    items.stash_id,
    items.item_id,
    ifNull(items.item_id, concat(items.stash_id, '|', items.base_type, '|', toString(items.observed_at))) AS item_key,
    concat(items.realm, '|', ifNull(items.league, ''), '|', items.stash_id, '|', ifNull(items.item_id, items.base_type)) AS listing_chain_id,
    coalesce(items.note, items.forum_note, if(match(ifNull(items.stash_name, ''), '^~'), items.stash_name, NULL)) AS note_value,
    toUInt8(0) AS note_edited,
    toUInt8(0) AS relist_event,
    toUInt8(meta.item_id IS NOT NULL) AS has_trade_metadata,
    multiIf(meta.item_id IS NOT NULL, 'trade_metadata', 'heuristic') AS evidence_source,
    now64(3) AS inserted_at
FROM poe_trade.silver_ps_items_raw AS items
LEFT JOIN (
    SELECT realm, league, item_id
    FROM poe_trade.bronze_trade_metadata
    WHERE item_id != ''
    GROUP BY realm, league, item_id
) AS meta
ON meta.item_id = ifNull(items.item_id, '')
AND meta.realm = items.realm
AND meta.league = ifNull(items.league, '');

CREATE TABLE IF NOT EXISTS poe_trade.ml_execution_labels_v2 (
    as_of_ts DateTime64(3, 'UTC'),
    realm String,
    league String,
    listing_chain_id String,
    sale_probability_label Nullable(Float64),
    time_to_exit_label Nullable(Float64),
    label_source LowCardinality(String),
    label_quality LowCardinality(String),
    is_censored UInt8,
    eligibility_reason String,
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(as_of_ts)
ORDER BY (league, realm, listing_chain_id, as_of_ts);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_listing_events_to_execution_labels_v2
TO poe_trade.ml_execution_labels_v2 AS
SELECT
    as_of_ts,
    realm,
    league,
    listing_chain_id,
    multiIf(evidence_source = 'trade_metadata', 0.65, 0.4) AS sale_probability_label,
    multiIf(evidence_source = 'trade_metadata', 6.0, 24.0) AS time_to_exit_label,
    evidence_source AS label_source,
    multiIf(evidence_source = 'trade_metadata', 'high', 'low') AS label_quality,
    multiIf(evidence_source = 'trade_metadata', 0, 1) AS is_censored,
    multiIf(evidence_source = 'trade_metadata', 'metadata_backed', 'heuristic_only') AS eligibility_reason,
    now64(3) AS inserted_at
FROM poe_trade.ml_listing_events_v2;

CREATE TABLE IF NOT EXISTS poe_trade.ml_price_labels_v2 (
    as_of_ts DateTime64(3, 'UTC'),
    realm String,
    league String,
    stash_id String,
    item_id Nullable(String),
    item_key String,
    listing_chain_id String,
    category LowCardinality(String),
    base_type String,
    stack_size UInt32,
    parsed_amount Nullable(Float64),
    parsed_currency Nullable(String),
    price_parse_status LowCardinality(String),
    normalized_price_chaos Nullable(Float64),
    unit_price_chaos Nullable(Float64),
    normalization_source LowCardinality(String),
    fx_hour Nullable(DateTime64(0, 'UTC')),
    fx_source LowCardinality(String),
    outlier_status LowCardinality(String),
    label_source LowCardinality(String),
    label_quality LowCardinality(String),
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(as_of_ts)
ORDER BY (league, realm, as_of_ts, stash_id, item_key);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_silver_ps_items_to_price_labels_v2
TO poe_trade.ml_price_labels_v2 AS
SELECT
    items.as_of_ts,
    items.realm,
    items.league,
    items.stash_id,
    items.item_id,
    items.item_key,
    concat(items.realm, '|', items.league, '|', items.stash_id, '|', ifNull(items.item_id, items.base_type)) AS listing_chain_id,
    items.category,
    items.base_type,
    items.stack_size,
    items.parsed_amount,
    lowerUTF8(trimBoth(items.parsed_currency)) AS parsed_currency,
    multiIf(items.parsed_amount IS NULL, 'parse_failure', items.parsed_amount <= 0, 'parse_failure', 'success') AS price_parse_status,
    multiIf(items.parsed_amount IS NULL, NULL, lowerUTF8(trimBoth(items.parsed_currency)) IN ('chaos', 'chaos orb', 'chaos orbs', ''), items.parsed_amount, fx.chaos_equivalent > 0, items.parsed_amount * fx.chaos_equivalent, NULL) AS normalized_price_chaos,
    multiIf(items.stack_size > 0 AND normalized_price_chaos IS NOT NULL, normalized_price_chaos / toFloat64(items.stack_size), normalized_price_chaos) AS unit_price_chaos,
    multiIf(items.parsed_amount IS NULL, 'none', lowerUTF8(trimBoth(items.parsed_currency)) IN ('chaos', 'chaos orb', 'chaos orbs', ''), 'chaos_direct', fx.chaos_equivalent > 0, 'poeninja_fx', 'missing_fx') AS normalization_source,
    fx.hour_ts AS fx_hour,
    ifNull(fx.fx_source, 'missing') AS fx_source,
    'trainable' AS outlier_status,
    'note_parse' AS label_source,
    'medium' AS label_quality,
    now64(3) AS inserted_at
FROM (
    SELECT
        observed_at AS as_of_ts,
        realm,
        ifNull(league, '') AS league,
        stash_id,
        item_id,
        ifNull(item_id, concat(stash_id, '|', base_type, '|', toString(observed_at))) AS item_key,
        base_type,
        greatest(1, stack_size) AS stack_size,
        coalesce(note, forum_note, if(match(ifNull(stash_name, ''), '^~'), stash_name, NULL)) AS effective_price_note,
        toFloat64OrNull(extract(coalesce(note, forum_note, if(match(ifNull(stash_name, ''), '^~'), stash_name, '')), '^~(?:b/o|price)\\s+([0-9]+(?:\\.[0-9]+)?)')) AS parsed_amount,
        nullIf(extract(coalesce(note, forum_note, if(match(ifNull(stash_name, ''), '^~'), stash_name, '')), '^~(?:b/o|price)\\s+[0-9]+(?:\\.[0-9]+)?\\s+(.+)$'), '') AS parsed_currency,
        multiIf(
            match(base_type, 'Essence'), 'essence',
            match(base_type, 'Fossil'), 'fossil',
            match(base_type, 'Scarab'), 'scarab',
            match(base_type, 'Cluster Jewel'), 'cluster_jewel',
            match(item_type_line, ' Map$'), 'map',
            match(base_type, 'Logbook'), 'logbook',
            match(base_type, 'Flask'), 'flask',
            'other'
        ) AS category
    FROM poe_trade.silver_ps_items_raw
) AS items
LEFT JOIN poe_trade.ml_fx_hour_latest_v2 AS fx
ON fx.league = items.league
AND fx.currency = lowerUTF8(trimBoth(items.parsed_currency))
AND fx.hour_ts = toStartOfHour(items.as_of_ts)
WHERE items.effective_price_note IS NOT NULL;

CREATE TABLE IF NOT EXISTS poe_trade.ml_item_mod_tokens_v2 (
    as_of_ts DateTime64(3, 'UTC'),
    realm String,
    league String,
    stash_id String,
    item_id Nullable(String),
    item_key String,
    mod_token String,
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(as_of_ts)
ORDER BY (league, realm, as_of_ts, item_key, mod_token);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_silver_ps_items_to_mod_tokens_v2
TO poe_trade.ml_item_mod_tokens_v2 AS
SELECT
    items.observed_at AS as_of_ts,
    items.realm,
    ifNull(items.league, '') AS league,
    items.stash_id,
    items.item_id,
    ifNull(items.item_id, concat(items.stash_id, '|', items.base_type, '|', toString(items.observed_at))) AS item_key,
    lowerUTF8(trimBoth(mod_line)) AS mod_token,
    now64(3) AS inserted_at
FROM poe_trade.silver_ps_items_raw AS items
ARRAY JOIN arrayConcat(
    JSONExtractArrayRaw(item_json, 'implicitMods'),
    JSONExtractArrayRaw(item_json, 'explicitMods'),
    JSONExtractArrayRaw(item_json, 'enchantMods'),
    JSONExtractArrayRaw(item_json, 'craftedMods'),
    JSONExtractArrayRaw(item_json, 'fracturedMods')
) AS mod_line;

CREATE TABLE IF NOT EXISTS poe_trade.ml_item_mod_features_v2 (
    as_of_ts DateTime64(3, 'UTC'),
    realm String,
    league String,
    stash_id String,
    item_id Nullable(String),
    item_key String,
    mod_token_count UInt16,
    mod_features_json String,
    feature_source LowCardinality(String),
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(as_of_ts)
ORDER BY (league, realm, as_of_ts, stash_id, item_key);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_mod_tokens_to_features_v2
TO poe_trade.ml_item_mod_features_v2 AS
SELECT
    raw.as_of_ts,
    raw.realm,
    raw.league,
    raw.stash_id,
    raw.item_id,
    raw.item_key,
    toUInt16(least(count(), 65535)) AS mod_token_count,
    toJSONString(
        mapFromArrays(
            ['Strength', 'Dexterity', 'Intelligence', 'MaximumLife', 'MaximumMana', 'MaximumEnergyShield', 'AttackSpeed', 'CastSpeed', 'PhysicalDamage', 'FireDamage', 'ColdDamage', 'LightningDamage', 'ChaosDamage', 'ElementalDamage', 'SpellDamage', 'FireResistance', 'ColdResistance', 'LightningResistance', 'ChaosResistance', 'AllElementalResistances'],
            [
                maxIf(primary_numeric, position(token, 'to strength') > 0 OR position(token, 'all attributes') > 0),
                maxIf(primary_numeric, position(token, 'to dexterity') > 0 OR position(token, 'all attributes') > 0),
                maxIf(primary_numeric, position(token, 'to intelligence') > 0 OR position(token, 'all attributes') > 0),
                maxIf(primary_numeric, position(token, 'maximum life') > 0 OR position(token, 'to life') > 0),
                maxIf(primary_numeric, position(token, 'maximum mana') > 0 OR position(token, 'to mana') > 0),
                maxIf(primary_numeric, position(token, 'maximum energy shield') > 0 OR position(token, 'energy shield') > 0),
                maxIf(primary_numeric, position(token, 'attack speed') > 0 OR position(token, 'attack and cast speed') > 0),
                maxIf(primary_numeric, position(token, 'cast speed') > 0 OR position(token, 'attack and cast speed') > 0),
                maxIf(if(physical_added_value > 0., physical_added_value, primary_numeric), position(token, 'physical damage') > 0),
                maxIf(if(fire_added_value > 0., fire_added_value, primary_numeric), position(token, 'fire damage') > 0),
                maxIf(if(cold_added_value > 0., cold_added_value, primary_numeric), position(token, 'cold damage') > 0),
                maxIf(if(lightning_added_value > 0., lightning_added_value, primary_numeric), position(token, 'lightning damage') > 0),
                maxIf(if(chaos_added_value > 0., chaos_added_value, primary_numeric), position(token, 'chaos damage') > 0),
                maxIf(primary_numeric, position(token, 'elemental damage') > 0),
                maxIf(primary_numeric, position(token, 'spell damage') > 0),
                maxIf(primary_numeric, position(token, 'fire resistance') > 0),
                maxIf(primary_numeric, position(token, 'cold resistance') > 0),
                maxIf(primary_numeric, position(token, 'lightning resistance') > 0),
                maxIf(primary_numeric, position(token, 'chaos resistance') > 0),
                maxIf(primary_numeric, position(token, 'all elemental resistances') > 0 OR position(token, 'to all elemental resistances') > 0)
            ]
        )
    ) AS mod_features_json,
    'token_sql_v2' AS feature_source,
    now64(3) AS inserted_at
FROM (
    SELECT
        as_of_ts,
        realm,
        league,
        stash_id,
        item_id,
        item_key,
        replaceRegexpAll(
            replaceRegexpAll(
                replaceAll(lowerUTF8(trimBoth(mod_token)), '\\"', '"'),
                '^"|"$',
                ''
            ),
            '\\s+',
            ' '
        ) AS token,
        if(
            toFloat64OrZero(extract(token, '(?:^|\\s)[+-]?(\\d+(?:\\.\\d+)?)\\s*%?')) > 0.,
            toFloat64OrZero(extract(token, '(?:^|\\s)[+-]?(\\d+(?:\\.\\d+)?)\\s*%?')),
            if(
                empty(extractAll(token, '\\d+(?:\\.\\d+)?')),
                0.,
                arrayReduce('max', arrayMap(x -> toFloat64OrZero(x), extractAll(token, '\\d+(?:\\.\\d+)?')))
            )
        ) AS primary_numeric,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+physical\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+physical\\s+damage'))
        ) AS physical_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+fire\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+fire\\s+damage'))
        ) AS fire_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+cold\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+cold\\s+damage'))
        ) AS cold_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+lightning\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+lightning\\s+damage'))
        ) AS lightning_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+chaos\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+chaos\\s+damage'))
        ) AS chaos_added_value
    FROM poe_trade.ml_item_mod_tokens_v2
) AS raw
WHERE
    position(token, 'to strength') > 0
    OR position(token, 'all attributes') > 0
    OR position(token, 'to dexterity') > 0
    OR position(token, 'to intelligence') > 0
    OR position(token, 'maximum life') > 0
    OR position(token, 'to life') > 0
    OR position(token, 'maximum mana') > 0
    OR position(token, 'to mana') > 0
    OR position(token, 'maximum energy shield') > 0
    OR position(token, 'energy shield') > 0
    OR position(token, 'attack speed') > 0
    OR position(token, 'attack and cast speed') > 0
    OR position(token, 'cast speed') > 0
    OR position(token, 'physical damage') > 0
    OR position(token, 'fire damage') > 0
    OR position(token, 'cold damage') > 0
    OR position(token, 'lightning damage') > 0
    OR position(token, 'chaos damage') > 0
    OR position(token, 'elemental damage') > 0
    OR position(token, 'spell damage') > 0
    OR position(token, 'fire resistance') > 0
    OR position(token, 'cold resistance') > 0
    OR position(token, 'lightning resistance') > 0
    OR position(token, 'chaos resistance') > 0
    OR position(token, 'all elemental resistances') > 0
    OR position(token, 'to all elemental resistances') > 0
GROUP BY as_of_ts, realm, league, stash_id, item_id, item_key;

CREATE TABLE IF NOT EXISTS poe_trade.ml_price_dataset_v2 (
    as_of_ts DateTime64(3, 'UTC'),
    realm String,
    league String,
    stash_id String,
    item_id Nullable(String),
    item_key String,
    item_name String,
    item_type_line String,
    base_type String,
    rarity Nullable(String),
    ilvl UInt16,
    stack_size UInt32,
    corrupted UInt8,
    fractured UInt8,
    synthesised UInt8,
    category LowCardinality(String),
    normalized_price_chaos Nullable(Float64),
    sale_probability_label Nullable(Float64),
    label_source LowCardinality(String),
    label_quality LowCardinality(String),
    outlier_status LowCardinality(String),
    route_candidate LowCardinality(String),
    support_count_recent UInt64,
    support_bucket LowCardinality(String),
    route_reason String,
    fallback_parent_route LowCardinality(String),
    fx_freshness_minutes Nullable(Float64),
    mod_token_count UInt16,
    confidence_hint Nullable(Float64),
    mod_features_json String,
    inserted_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(as_of_ts)
ORDER BY (league, category, base_type, as_of_ts, item_key);

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_price_labels_to_dataset_v2
TO poe_trade.ml_price_dataset_v2 AS
SELECT
    labels.as_of_ts AS as_of_ts,
    labels.realm AS realm,
    labels.league AS league,
    labels.stash_id AS stash_id,
    labels.item_id AS item_id,
    labels.item_key AS item_key,
    items.item_name AS item_name,
    items.item_type_line AS item_type_line,
    items.base_type AS base_type,
    items.rarity AS rarity,
    items.ilvl AS ilvl,
    items.stack_size AS stack_size,
    items.corrupted AS corrupted,
    items.fractured AS fractured,
    items.synthesised AS synthesised,
    labels.category AS category,
    labels.normalized_price_chaos AS normalized_price_chaos,
    exec_labels.sale_probability_label AS sale_probability_label,
    ifNull(exec_labels.label_source, labels.label_source) AS label_source,
    ifNull(exec_labels.label_quality, labels.label_quality) AS label_quality,
    labels.outlier_status AS outlier_status,
    'fallback_abstain' AS route_candidate,
    toUInt64(0) AS support_count_recent,
    'low' AS support_bucket,
    'incremental_dataset_v2' AS route_reason,
    'fallback_abstain' AS fallback_parent_route,
    if(
        labels.fx_hour IS NULL,
        CAST(NULL, 'Nullable(Float64)'),
        toFloat64(greatest(dateDiff('minute', labels.fx_hour, labels.as_of_ts), 0))
    ) AS fx_freshness_minutes,
    toUInt16(ifNull(features.mod_token_count, 0)) AS mod_token_count,
    multiIf(labels.normalized_price_chaos IS NULL, 0.25, 0.6) AS confidence_hint,
    ifNull(features.mod_features_json, '{}') AS mod_features_json,
    now64(3) AS inserted_at
FROM poe_trade.ml_price_labels_v2 AS labels
INNER JOIN poe_trade.silver_ps_items_raw AS items
ON items.observed_at = labels.as_of_ts
AND items.realm = labels.realm
AND ifNull(items.league, '') = labels.league
AND items.stash_id = labels.stash_id
AND ifNull(items.item_id, concat(items.stash_id, '|', items.base_type, '|', toString(items.observed_at))) = labels.item_key
LEFT JOIN poe_trade.ml_execution_labels_v2 AS exec_labels
ON exec_labels.as_of_ts = labels.as_of_ts
AND exec_labels.realm = labels.realm
AND exec_labels.league = labels.league
AND exec_labels.listing_chain_id = labels.listing_chain_id
LEFT JOIN poe_trade.ml_item_mod_features_v2 AS features
ON features.as_of_ts = labels.as_of_ts
AND features.realm = labels.realm
AND features.league = labels.league
AND features.stash_id = labels.stash_id
AND features.item_key = labels.item_key
WHERE labels.outlier_status = 'trainable'
AND labels.normalized_price_chaos IS NOT NULL;
