DROP TABLE IF EXISTS poe_trade.mv_silver_ps_items_to_price_labels_v2;

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
        toFloat64OrNull(extract(coalesce(note, forum_note, if(match(ifNull(stash_name, ''), '^~'), stash_name, '')), '^~(?:b/o|price)\s+([0-9]+(?:\.[0-9]+)?)')) AS parsed_amount,
        nullIf(extract(coalesce(note, forum_note, if(match(ifNull(stash_name, ''), '^~'), stash_name, '')), '^~(?:b/o|price)\s+[0-9]+(?:\.[0-9]+)?\s+(.+)$'), '') AS parsed_currency,
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
AND replaceRegexpAll(lowerUTF8(trimBoth(fx.currency)), '\s+orbs?$', '') = multiIf(
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('div', 'divine', 'divines'), 'divine',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('exa', 'exalt', 'exalted', 'exalts'), 'exalted',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('alch', 'alchemy'), 'orb of alchemy',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('gcp', 'gemcutter', 'gemcutters', 'gemcutter''s prism'), 'gemcutter''s prism',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('alt', 'alteration'), 'orb of alteration',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('scour', 'scouring'), 'orb of scouring',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('wisdom', 'wisdom scroll'), 'scroll of wisdom',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('annul', 'annulment'), 'orb of annulment',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('chrome', 'chromatic'), 'chromatic',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('fusing',), 'orb of fusing',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('portal',), 'portal scroll',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('bauble',), 'glassblower''s bauble',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('aug', 'augmentation'), 'orb of augmentation',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('transmute', 'transmutation'), 'orb of transmutation',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '') IN ('mirror',), 'mirror of kalandra',
    replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), '\s+', ' '), '\s+orbs?$', '')
)
AND fx.hour_ts = toStartOfHour(items.as_of_ts)
WHERE items.effective_price_note IS NOT NULL;
