INSERT INTO poe_trade.account_stash_item_history_v2
(
    scan_id,
    account_name,
    league,
    realm,
    tab_id,
    tab_index,
    tab_name,
    tab_type,
    lineage_key,
    content_signature,
    item_position_key,
    item_id,
    item_name,
    base_type,
    item_class,
    rarity,
    x,
    y,
    w,
    h,
    listed_price,
    listed_currency,
    listed_price_chaos,
    estimated_price_chaos,
    price_p10_chaos,
    price_p90_chaos,
    price_delta_chaos,
    price_delta_pct,
    price_band,
    price_band_version,
    confidence,
    estimate_trust,
    estimate_warning,
    fallback_reason,
    explicit_mods_json,
    icon_url,
    priced_at,
    payload_json
)
WITH
    200.0 AS divine_to_chaos_rate
SELECT
    source.scan_id,
    source.account_name,
    source.league,
    source.realm,
    source.tab_id,
    source.tab_index,
    source.tab_name,
    source.tab_type,
    source.lineage_key,
    source.content_signature,
    source.item_position_key,
    source.item_id,
    source.item_name,
    source.base_type,
    source.item_class,
    source.rarity,
    source.x,
    source.y,
    source.w,
    source.h,
    source.listed_price,
    source.listed_currency,
    if(
        source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.listed_price,
        if(
            source.listed_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.listed_price * divine_to_chaos_rate,
            NULL
        )
    ) AS listed_price_chaos,
    if(
        source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.predicted_price,
        if(
            source.predicted_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.predicted_price * divine_to_chaos_rate,
            NULL
        )
    ) AS estimated_price_chaos,
    if(
        source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.price_p10,
        if(
            source.predicted_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.price_p10 * divine_to_chaos_rate,
            NULL
        )
    ) AS price_p10_chaos,
    if(
        source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.price_p90,
        if(
            source.predicted_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.price_p90 * divine_to_chaos_rate,
            NULL
        )
    ) AS price_p90_chaos,
    if(
        isNull(
            if(
                source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.listed_price,
                if(
                    source.listed_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.listed_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        OR isNull(
            if(
                source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.predicted_price,
                if(
                    source.predicted_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.predicted_price * divine_to_chaos_rate,
                    NULL
                )
            )
        ),
        NULL,
        if(
            source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.listed_price,
            if(
                source.listed_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.listed_price * divine_to_chaos_rate,
                NULL
            )
        )
        - if(
            source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.predicted_price,
            if(
                source.predicted_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.predicted_price * divine_to_chaos_rate,
                NULL
            )
        )
    ) AS price_delta_chaos,
    if(
        isNull(
            if(
                source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.listed_price,
                if(
                    source.listed_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.listed_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        OR isNull(
            if(
                source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.predicted_price,
                if(
                    source.predicted_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.predicted_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        OR if(
            source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.predicted_price,
            if(
                source.predicted_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.predicted_price * divine_to_chaos_rate,
                NULL
            )
        ) = 0,
        NULL,
        (
            if(
                source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.listed_price,
                if(
                    source.listed_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.listed_price * divine_to_chaos_rate,
                    NULL
                )
            )
            - if(
                source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.predicted_price,
                if(
                    source.predicted_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.predicted_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        / if(
            source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.predicted_price,
            if(
                source.predicted_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.predicted_price * divine_to_chaos_rate,
                NULL
            )
        ) * 100.0
    ) AS price_delta_pct,
    if(
        isNull(price_delta_pct),
        'bad',
        if(
            abs(price_delta_pct) <= 10.0,
            'good',
            if(abs(price_delta_pct) <= 25.0, 'mediocre', 'bad')
        )
    ) AS price_band,
    toUInt16(1) AS price_band_version,
    source.confidence,
    source.estimate_trust,
    source.estimate_warning,
    source.fallback_reason,
    source.explicit_mods_json,
    source.icon_url,
    source.priced_at,
    source.payload_json
FROM
(
    SELECT
        v.scan_id,
        v.account_name,
        v.league,
        v.realm,
        v.tab_id,
        v.tab_index,
        v.tab_name,
        v.tab_type,
        v.lineage_key,
        v.content_signature,
        v.item_position_key,
        v.item_id,
        v.item_name,
        coalesce(
            nullIf(JSONExtractString(v.payload_json, 'baseType'), ''),
            nullIf(JSONExtractString(v.payload_json, 'typeLine'), ''),
            v.item_name
        ) AS base_type,
        v.item_class,
        v.rarity,
        v.x,
        v.y,
        v.w,
        v.h,
        v.listed_price,
        if(
            match(
                JSONExtractString(v.payload_json, 'note'),
                '^~(?:b/o|price)\\s+[0-9]+(?:\\.[0-9]+)?\\s+(.+)$'
            ),
            lowerUTF8(
                replaceRegexpOne(
                    JSONExtractString(v.payload_json, 'note'),
                    '^~(?:b/o|price)\\s+[0-9]+(?:\\.[0-9]+)?\\s+',
                    ''
                )
            ),
            ''
        ) AS note_currency,
        if(
            note_currency != '',
            note_currency,
            lowerUTF8(coalesce(nullIf(v.currency, ''), 'chaos'))
        ) AS listed_currency,
        lowerUTF8(coalesce(nullIf(v.currency, ''), note_currency, 'chaos')) AS predicted_currency,
        v.predicted_price,
        v.price_p10,
        v.price_p90,
        v.confidence,
        v.estimate_trust,
        v.estimate_warning,
        v.fallback_reason,
        if(
            empty(JSONExtractRaw(v.payload_json, 'explicitMods')),
            '[]',
            JSONExtractRaw(v.payload_json, 'explicitMods')
        ) AS explicit_mods_json,
        v.icon_url,
        v.priced_at,
        v.payload_json
    FROM poe_trade.account_stash_item_valuations AS v
    WHERE v.priced_at >= now() - INTERVAL 90 DAY
) AS source
LEFT ANTI JOIN poe_trade.account_stash_item_history_v2 AS existing
    ON existing.account_name = source.account_name
   AND existing.realm = source.realm
   AND existing.league = source.league
   AND existing.lineage_key = source.lineage_key
   AND existing.priced_at = source.priced_at
   AND existing.scan_id = source.scan_id
;

INSERT INTO poe_trade.account_stash_scan_items_v2
(
    scan_id,
    account_name,
    league,
    realm,
    tab_id,
    tab_index,
    tab_name,
    tab_type,
    lineage_key,
    content_signature,
    item_position_key,
    item_id,
    item_name,
    base_type,
    item_class,
    rarity,
    x,
    y,
    w,
    h,
    listed_price,
    listed_currency,
    listed_price_chaos,
    estimated_price_chaos,
    price_p10_chaos,
    price_p90_chaos,
    price_delta_chaos,
    price_delta_pct,
    price_band,
    price_band_version,
    confidence,
    estimate_trust,
    estimate_warning,
    fallback_reason,
    explicit_mods_json,
    icon_url,
    priced_at,
    payload_json
)
WITH
    200.0 AS divine_to_chaos_rate
SELECT
    source.scan_id,
    source.account_name,
    source.league,
    source.realm,
    source.tab_id,
    source.tab_index,
    source.tab_name,
    source.tab_type,
    source.lineage_key,
    source.content_signature,
    source.item_position_key,
    source.item_id,
    source.item_name,
    source.base_type,
    source.item_class,
    source.rarity,
    source.x,
    source.y,
    source.w,
    source.h,
    source.listed_price,
    source.listed_currency,
    if(
        source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.listed_price,
        if(
            source.listed_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.listed_price * divine_to_chaos_rate,
            NULL
        )
    ) AS listed_price_chaos,
    if(
        source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.predicted_price,
        if(
            source.predicted_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.predicted_price * divine_to_chaos_rate,
            NULL
        )
    ) AS estimated_price_chaos,
    if(
        source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.price_p10,
        if(
            source.predicted_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.price_p10 * divine_to_chaos_rate,
            NULL
        )
    ) AS price_p10_chaos,
    if(
        source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
        source.price_p90,
        if(
            source.predicted_currency IN (
                'div',
                'divine',
                'divines',
                'divine orb',
                'divine orbs'
            ),
            source.price_p90 * divine_to_chaos_rate,
            NULL
        )
    ) AS price_p90_chaos,
    if(
        isNull(
            if(
                source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.listed_price,
                if(
                    source.listed_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.listed_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        OR isNull(
            if(
                source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.predicted_price,
                if(
                    source.predicted_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.predicted_price * divine_to_chaos_rate,
                    NULL
                )
            )
        ),
        NULL,
        if(
            source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.listed_price,
            if(
                source.listed_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.listed_price * divine_to_chaos_rate,
                NULL
            )
        )
        - if(
            source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.predicted_price,
            if(
                source.predicted_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.predicted_price * divine_to_chaos_rate,
                NULL
            )
        )
    ) AS price_delta_chaos,
    if(
        isNull(
            if(
                source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.listed_price,
                if(
                    source.listed_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.listed_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        OR isNull(
            if(
                source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.predicted_price,
                if(
                    source.predicted_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.predicted_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        OR if(
            source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.predicted_price,
            if(
                source.predicted_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.predicted_price * divine_to_chaos_rate,
                NULL
            )
        ) = 0,
        NULL,
        (
            if(
                source.listed_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.listed_price,
                if(
                    source.listed_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.listed_price * divine_to_chaos_rate,
                    NULL
                )
            )
            - if(
                source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
                source.predicted_price,
                if(
                    source.predicted_currency IN (
                        'div',
                        'divine',
                        'divines',
                        'divine orb',
                        'divine orbs'
                    ),
                    source.predicted_price * divine_to_chaos_rate,
                    NULL
                )
            )
        )
        / if(
            source.predicted_currency IN ('chaos', 'chaos orb', 'chaos orbs', 'c'),
            source.predicted_price,
            if(
                source.predicted_currency IN (
                    'div',
                    'divine',
                    'divines',
                    'divine orb',
                    'divine orbs'
                ),
                source.predicted_price * divine_to_chaos_rate,
                NULL
            )
        ) * 100.0
    ) AS price_delta_pct,
    if(
        isNull(price_delta_pct),
        'bad',
        if(
            abs(price_delta_pct) <= 10.0,
            'good',
            if(abs(price_delta_pct) <= 25.0, 'mediocre', 'bad')
        )
    ) AS price_band,
    toUInt16(1) AS price_band_version,
    source.confidence,
    source.estimate_trust,
    source.estimate_warning,
    source.fallback_reason,
    source.explicit_mods_json,
    source.icon_url,
    source.priced_at,
    source.payload_json
FROM
(
    SELECT
        v.scan_id,
        v.account_name,
        v.league,
        v.realm,
        v.tab_id,
        v.tab_index,
        v.tab_name,
        v.tab_type,
        v.lineage_key,
        v.content_signature,
        v.item_position_key,
        v.item_id,
        v.item_name,
        coalesce(
            nullIf(JSONExtractString(v.payload_json, 'baseType'), ''),
            nullIf(JSONExtractString(v.payload_json, 'typeLine'), ''),
            v.item_name
        ) AS base_type,
        v.item_class,
        v.rarity,
        v.x,
        v.y,
        v.w,
        v.h,
        v.listed_price,
        if(
            note_currency != '',
            note_currency,
            lowerUTF8(coalesce(nullIf(v.currency, ''), 'chaos'))
        ) AS listed_currency,
        lowerUTF8(coalesce(nullIf(v.currency, ''), listed_currency, 'chaos')) AS predicted_currency,
        v.predicted_price,
        v.price_p10,
        v.price_p90,
        v.confidence,
        v.estimate_trust,
        v.estimate_warning,
        v.fallback_reason,
        if(
            empty(JSONExtractRaw(v.payload_json, 'explicitMods')),
            '[]',
            JSONExtractRaw(v.payload_json, 'explicitMods')
        ) AS explicit_mods_json,
        v.icon_url,
        v.priced_at,
        v.payload_json,
        if(
            match(
                JSONExtractString(v.payload_json, 'note'),
                '^~(?:b/o|price)\\s+[0-9]+(?:\\.[0-9]+)?\\s+(.+)$'
            ),
            lowerUTF8(
                replaceRegexpOne(
                    JSONExtractString(v.payload_json, 'note'),
                    '^~(?:b/o|price)\\s+[0-9]+(?:\\.[0-9]+)?\\s+',
                    ''
                )
            ),
            ''
        ) AS note_currency
    FROM poe_trade.account_stash_item_valuations AS v
    WHERE v.priced_at >= now() - INTERVAL 90 DAY
) AS source
LEFT ANTI JOIN poe_trade.account_stash_scan_items_v2 AS existing
    ON existing.account_name = source.account_name
   AND existing.realm = source.realm
   AND existing.league = source.league
   AND existing.scan_id = source.scan_id
   AND existing.tab_index = source.tab_index
   AND existing.y = source.y
   AND existing.x = source.x
   AND existing.item_id = source.item_id
;
