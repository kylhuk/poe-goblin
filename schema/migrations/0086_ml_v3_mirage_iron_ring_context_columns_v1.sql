CREATE OR REPLACE VIEW poe_trade.v_ml_v3_mirage_iron_ring_item_features_v1 AS
WITH
    catalog_signatures AS (
        SELECT
            normalized_signature,
            any(mod_generation_type) AS mod_generation_type
        FROM (
            SELECT
                replaceRegexpAll(
                    lowerUTF8(
                        trimBoth(
                            replaceAll(
                                replaceAll(
                                    replaceAll(
                                        replaceAll(mod_text_pattern, '"', ''),
                                        '(',
                                        ' '
                                    ),
                                    ')',
                                    ' '
                                ),
                                '-',
                                ' '
                            )
                        )
                    ),
                    '[0-9]+([.][0-9]+)?',
                    ' '
                ) AS normalized_signature,
                mod_generation_type
            FROM poe_trade.ml_ring_mod_catalog_v1
        )
        GROUP BY normalized_signature
    ),
    affix_rows AS (
        SELECT
            item.observed_at,
            item.realm,
            item.league,
            item.stash_id,
            item.account_name,
            item.stash_name,
            item.checkpoint,
            item.next_change_id,
            item.item_id,
            item.identity_key,
            item.fingerprint_v3,
            item.item_name,
            item.item_type_line,
            item.base_type,
            item.rarity,
            item.category,
            item.ilvl,
            item.stack_size,
            item.corrupted,
            item.fractured,
            item.synthesised,
            item.item_json,
            item.note,
            item.forum_note,
            item.effective_price_note,
            item.parsed_amount,
            item.parsed_currency,
            item.normalized_affix_hash,
            item.affix_payload_json,
            item.inserted_at,
            tupleElement(affix_tuple, 1) AS affix_kind,
            tupleElement(affix_tuple, 2) AS affix_text,
            replaceRegexpAll(
                replaceRegexpAll(
                    lowerUTF8(
                        trimBoth(
                            replaceAll(
                                replaceAll(
                                    replaceAll(
                                        replaceAll(tupleElement(affix_tuple, 2), '"', ''),
                                        '(',
                                        ' '
                                    ),
                                    ')',
                                    ' '
                                ),
                                '-',
                                ' '
                            )
                        )
                    ),
                    '[0-9]+([.][0-9]+)?',
                    ' '
                ),
                '[[:space:]]+',
                ' '
            ) AS affix_signature,
            toUInt8(JSONExtractBool(item.item_json, 'shaperItem'))
            + toUInt8(JSONExtractBool(item.item_json, 'elderItem')) * 2
            + toUInt8(JSONExtractBool(item.item_json, 'crusaderItem')) * 4
            + toUInt8(JSONExtractBool(item.item_json, 'redeemerItem')) * 8
            + toUInt8(JSONExtractBool(item.item_json, 'hunterItem')) * 16
            + toUInt8(JSONExtractBool(item.item_json, 'warlordItem')) * 32 AS influence_mask,
            ifNull(JSONExtractString(item.item_json, 'catalystType'), '') AS catalyst_type,
            toUInt8(JSONExtractUInt(item.item_json, 'catalystQuality')) AS catalyst_quality,
            if(item.synthesised = 1, toUInt32(length(JSONExtractArrayRaw(item.item_json, 'implicitMods'))), 0) AS synth_imp_count,
            if(item.synthesised = 1, ifNull(JSONExtractRaw(item.item_json, 'implicitMods'), '[]'), '[]') AS synth_implicit_mods_json,
            if(item.corrupted = 1, ifNull(JSONExtractRaw(item.item_json, 'implicitMods'), '[]'), '[]') AS corrupted_implicit_mods_json,
            toUInt32(length(JSONExtractArrayRaw(item.item_json, 'veiledMods'))) AS veiled_count,
            toUInt32(length(JSONExtractArrayRaw(item.item_json, 'craftedMods'))) AS crafted_count,
            toUInt32(count() OVER (PARTITION BY item.league, item.realm, item.stash_id, item.identity_key)) AS support_count_recent
        FROM poe_trade.ml_v3_mirage_iron_ring_branch_v1 AS item
        ARRAY JOIN arrayConcat(
            arrayMap(mod_line -> tuple('explicit', mod_line), JSONExtractArrayRaw(item.item_json, 'explicitMods')),
            arrayMap(mod_line -> tuple('implicit', mod_line), JSONExtractArrayRaw(item.item_json, 'implicitMods')),
            arrayMap(mod_line -> tuple('crafted', mod_line), JSONExtractArrayRaw(item.item_json, 'craftedMods')),
            arrayMap(mod_line -> tuple('fractured', mod_line), JSONExtractArrayRaw(item.item_json, 'fracturedMods')),
            arrayMap(mod_line -> tuple('enchant', mod_line), JSONExtractArrayRaw(item.item_json, 'enchantMods'))
        ) AS affix_tuple
    ),
    enriched_affix_rows AS (
        SELECT
            affix_rows.*,
            catalog_signatures.mod_generation_type AS affix_generation_type
        FROM affix_rows
        LEFT JOIN catalog_signatures
            ON catalog_signatures.normalized_signature = affix_rows.affix_signature
    )
SELECT
    as_of_ts,
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
    any(influence_mask) AS influence_mask,
    any(catalyst_type) AS catalyst_type,
    any(catalyst_quality) AS catalyst_quality,
    any(synth_imp_count) AS synth_imp_count,
    any(synth_implicit_mods_json) AS synth_implicit_mods_json,
    any(corrupted_implicit_mods_json) AS corrupted_implicit_mods_json,
    any(veiled_count) AS veiled_count,
    any(crafted_count) AS crafted_count,
    any(support_count_recent) AS support_count_recent,
    toUInt32(countIf(affix_kind = 'explicit' AND affix_generation_type = 'prefix')) AS prefix_count,
    toUInt32(countIf(affix_kind = 'explicit' AND affix_generation_type = 'suffix')) AS suffix_count,
    toUInt32(greatest(0, 3 - countIf(affix_kind = 'explicit' AND affix_generation_type = 'prefix'))) AS open_prefixes,
    toUInt32(greatest(0, 3 - countIf(affix_kind = 'explicit' AND affix_generation_type = 'suffix'))) AS open_suffixes,
    normalized_affix_hash,
    count() AS affix_count,
    groupArray(tuple(affix_kind, affix_text)) AS affixes,
    parsed_amount,
    ifNull(parsed_amount, CAST(NULL, 'Nullable(Float64)')) AS target_price_chaos,
    toFloat64(ifNull(parsed_amount, 0.0) * 0.95) AS target_fast_sale_24h_price,
    toFloat32(1.0) AS target_sale_probability_24h,
    toUInt8(1) AS target_likely_sold,
    toUInt8(1) AS sale_confidence_flag,
    toFloat32(1.0) AS label_weight,
    'branch_mirage_iron_ring_v1' AS label_source,
    toUInt16(0) AS split_bucket,
    toJSONString(mapFromArrays(
        arrayMap(affix -> concat(tupleElement(affix, 1), '::', lowerUTF8(replaceAll(trimBoth(replaceAll(tupleElement(affix, 2), '"', '')), '  ', ' '))), affixes),
        arrayMap(_ -> 1.0, affixes)
    )) AS mod_features_json
FROM enriched_affix_rows
GROUP BY
    as_of_ts,
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
    normalized_affix_hash,
    parsed_amount
ORDER BY as_of_ts ASC, identity_key ASC, item_id ASC;
