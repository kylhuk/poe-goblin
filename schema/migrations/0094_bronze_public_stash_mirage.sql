CREATE TABLE IF NOT EXISTS poe_trade.bronze_public_stash_mirage (
    ingested_at DateTime64(3, 'UTC') CODEC(Delta(8), ZSTD(3)),
    realm LowCardinality(String),
    league LowCardinality(String),
    stash_id String CODEC(ZSTD(3)),
    stash_json_id Nullable(String) CODEC(ZSTD(3)),
    checkpoint String CODEC(ZSTD(3)),
    next_change_id String CODEC(ZSTD(3)),
    account_name Nullable(String) CODEC(ZSTD(3)),
    stash_name Nullable(String) CODEC(ZSTD(3)),
    stash_type LowCardinality(Nullable(String)),
    public_flag UInt8,
    row_type LowCardinality(String),
    array_group LowCardinality(Nullable(String)),
    root_item_ordinal UInt32,
    root_item_id Nullable(String) CODEC(ZSTD(3)),
    item_id Nullable(String) CODEC(ZSTD(3)),
    parent_item_id Nullable(String) CODEC(ZSTD(3)),
    array_ordinal Nullable(UInt32),
    value_ordinal Nullable(UInt32),
    item_league LowCardinality(Nullable(String)),
    item_name Nullable(String) CODEC(ZSTD(3)),
    item_type_line Nullable(String) CODEC(ZSTD(3)),
    base_type Nullable(String) CODEC(ZSTD(3)),
    rarity LowCardinality(Nullable(String)),
    inventory_id Nullable(String) CODEC(ZSTD(3)),
    note Nullable(String) CODEC(ZSTD(3)),
    forum_note Nullable(String) CODEC(ZSTD(3)),
    icon Nullable(String) CODEC(ZSTD(3)),
    descr_text Nullable(String) CODEC(ZSTD(3)),
    sec_descr_text Nullable(String) CODEC(ZSTD(3)),
    art_filename Nullable(String) CODEC(ZSTD(3)),
    built_in_support Nullable(String) CODEC(ZSTD(3)),
    item_colour LowCardinality(Nullable(String)),
    stack_size_text Nullable(String) CODEC(ZSTD(3)),
    ilvl Nullable(UInt16),
    item_level Nullable(UInt16),
    monster_level Nullable(UInt16),
    stack_size Nullable(UInt32),
    max_stack_size Nullable(UInt32),
    frame_type Nullable(UInt8),
    w Nullable(UInt8),
    h Nullable(UInt8),
    x Nullable(UInt8),
    y Nullable(UInt8),
    socket_index Nullable(UInt8),
    socket_group Nullable(UInt8),
    socket_attr LowCardinality(Nullable(String)),
    socket_colour LowCardinality(Nullable(String)),
    talisman_tier Nullable(UInt8),
    foil_variation Nullable(UInt16),
    verified Nullable(UInt8),
    identified Nullable(UInt8),
    corrupted Nullable(UInt8),
    fractured Nullable(UInt8),
    synthesised Nullable(UInt8),
    duplicated Nullable(UInt8),
    split_flag Nullable(UInt8),
    support_flag Nullable(UInt8),
    abyss_jewel Nullable(UInt8),
    delve Nullable(UInt8),
    elder Nullable(UInt8),
    shaper Nullable(UInt8),
    searing Nullable(UInt8),
    tangled Nullable(UInt8),
    veiled Nullable(UInt8),
    memory_item Nullable(UInt8),
    mutated Nullable(UInt8),
    unmodifiable Nullable(UInt8),
    unmodifiable_except_chaos Nullable(UInt8),
    is_relic Nullable(UInt8),
    replica Nullable(UInt8),
    extended_prefixes Nullable(UInt8),
    extended_suffixes Nullable(UInt8),
    hybrid_base_type_name Nullable(String) CODEC(ZSTD(3)),
    hybrid_is_vaal_gem Nullable(UInt8),
    hybrid_sec_descr_text Nullable(String) CODEC(ZSTD(3)),
    incubated_item_name Nullable(String) CODEC(ZSTD(3)),
    incubated_item_level Nullable(UInt16),
    incubated_item_progress Nullable(UInt32),
    incubated_item_total Nullable(UInt32),
    influence_crusader Nullable(UInt8),
    influence_elder Nullable(UInt8),
    influence_hunter Nullable(UInt8),
    influence_redeemer Nullable(UInt8),
    influence_shaper Nullable(UInt8),
    influence_warlord Nullable(UInt8),
    attribute_name Nullable(String) CODEC(ZSTD(3)),
    attribute_display_mode Nullable(Int32),
    attribute_type Nullable(Int32),
    attribute_suffix Nullable(String) CODEC(ZSTD(3)),
    attribute_progress Nullable(Float64),
    attribute_value_text Nullable(String) CODEC(ZSTD(3)),
    attribute_value_style Nullable(Int32),
    mod_text Nullable(String) CODEC(ZSTD(3)),
    logbook_name Nullable(String) CODEC(ZSTD(3)),
    logbook_faction_id Nullable(String) CODEC(ZSTD(3)),
    logbook_faction_name Nullable(String) CODEC(ZSTD(3)),
    ultimatum_type Nullable(String) CODEC(ZSTD(3)),
    ultimatum_tier Nullable(UInt8)
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(ingested_at))
ORDER BY (
    league,
    realm,
    stash_id,
    ingested_at,
    ifNull(root_item_id, ''),
    row_type,
    ifNull(array_group, ''),
    ifNull(array_ordinal, 0),
    ifNull(value_ordinal, 0),
    ifNull(item_id, '')
)
TTL ingested_at + INTERVAL 14 DAY
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_raw_public_stash_to_bronze_public_stash_mirage
TO poe_trade.bronze_public_stash_mirage AS
WITH
item_base AS (
    SELECT
        base.ingested_at,
        base.realm,
        'Mirage' AS league,
        base.stash_id,
        nullIf(JSONExtractString(base.payload_json, 'id'), '') AS stash_json_id,
        base.checkpoint,
        base.next_change_id,
        nullIf(JSONExtractString(base.payload_json, 'accountName'), '') AS account_name,
        nullIf(JSONExtractString(base.payload_json, 'stash'), '') AS stash_name,
        nullIf(JSONExtractString(base.payload_json, 'stashType'), '') AS stash_type,
        toUInt8(ifNull(JSONExtractBool(base.payload_json, 'public'), 1)) AS public_flag,
        toUInt32(item_index) AS root_item_ordinal,
        nullIf(JSONExtractString(item_json, 'id'), '') AS root_item_id,
        nullIf(JSONExtractString(item_json, 'id'), '') AS item_id,
        nullIf(JSONExtractString(item_json, 'league'), '') AS item_league,
        nullIf(JSONExtractString(item_json, 'name'), '') AS item_name,
        nullIf(JSONExtractString(item_json, 'typeLine'), '') AS item_type_line,
        nullIf(JSONExtractString(item_json, 'baseType'), '') AS base_type,
        nullIf(JSONExtractString(item_json, 'rarity'), '') AS rarity,
        nullIf(JSONExtractString(item_json, 'inventoryId'), '') AS inventory_id,
        nullIf(JSONExtractString(item_json, 'note'), '') AS note,
        nullIf(JSONExtractString(item_json, 'forum_note'), '') AS forum_note,
        nullIf(JSONExtractString(item_json, 'icon'), '') AS icon,
        nullIf(JSONExtractString(item_json, 'descrText'), '') AS descr_text,
        nullIf(JSONExtractString(item_json, 'secDescrText'), '') AS sec_descr_text,
        nullIf(JSONExtractString(item_json, 'artFilename'), '') AS art_filename,
        nullIf(JSONExtractString(item_json, 'builtInSupport'), '') AS built_in_support,
        nullIf(JSONExtractString(item_json, 'colour'), '') AS item_colour,
        nullIf(JSONExtractString(item_json, 'stackSizeText'), '') AS stack_size_text,
        if(JSONHas(item_json, 'ilvl'), toUInt16(greatest(0, JSONExtractInt(item_json, 'ilvl'))), NULL) AS ilvl,
        if(JSONHas(item_json, 'itemLevel'), toUInt16(greatest(0, JSONExtractInt(item_json, 'itemLevel'))), NULL) AS item_level,
        if(JSONHas(item_json, 'monsterLevel'), toUInt16(greatest(0, JSONExtractInt(item_json, 'monsterLevel'))), NULL) AS monster_level,
        if(JSONHas(item_json, 'stackSize'), toUInt32(greatest(0, JSONExtractInt(item_json, 'stackSize'))), NULL) AS stack_size,
        if(JSONHas(item_json, 'maxStackSize'), toUInt32(greatest(0, JSONExtractInt(item_json, 'maxStackSize'))), NULL) AS max_stack_size,
        if(JSONHas(item_json, 'frameType'), toUInt8(greatest(0, JSONExtractInt(item_json, 'frameType'))), NULL) AS frame_type,
        if(JSONHas(item_json, 'w'), toUInt8(greatest(0, JSONExtractInt(item_json, 'w'))), NULL) AS w,
        if(JSONHas(item_json, 'h'), toUInt8(greatest(0, JSONExtractInt(item_json, 'h'))), NULL) AS h,
        if(JSONHas(item_json, 'x'), toUInt8(greatest(0, JSONExtractInt(item_json, 'x'))), NULL) AS x,
        if(JSONHas(item_json, 'y'), toUInt8(greatest(0, JSONExtractInt(item_json, 'y'))), NULL) AS y,
        if(JSONHas(item_json, 'socket'), toUInt8(greatest(0, JSONExtractInt(item_json, 'socket'))), NULL) AS socket_index,
        if(JSONHas(item_json, 'talismanTier'), toUInt8(greatest(0, JSONExtractInt(item_json, 'talismanTier'))), NULL) AS talisman_tier,
        if(JSONHas(item_json, 'foilVariation'), toUInt16(greatest(0, JSONExtractInt(item_json, 'foilVariation'))), NULL) AS foil_variation,
        if(JSONHas(item_json, 'verified'), toUInt8(JSONExtractBool(item_json, 'verified')), NULL) AS verified,
        if(JSONHas(item_json, 'identified'), toUInt8(JSONExtractBool(item_json, 'identified')), NULL) AS identified,
        if(JSONHas(item_json, 'corrupted'), toUInt8(JSONExtractBool(item_json, 'corrupted')), NULL) AS corrupted,
        if(JSONHas(item_json, 'fractured'), toUInt8(JSONExtractBool(item_json, 'fractured')), NULL) AS fractured,
        if(JSONHas(item_json, 'synthesised'), toUInt8(JSONExtractBool(item_json, 'synthesised')), NULL) AS synthesised,
        if(JSONHas(item_json, 'duplicated'), toUInt8(JSONExtractBool(item_json, 'duplicated')), NULL) AS duplicated,
        if(JSONHas(item_json, 'split'), toUInt8(JSONExtractBool(item_json, 'split')), NULL) AS split_flag,
        if(JSONHas(item_json, 'support'), toUInt8(JSONExtractBool(item_json, 'support')), NULL) AS support_flag,
        if(JSONHas(item_json, 'abyssJewel'), toUInt8(JSONExtractBool(item_json, 'abyssJewel')), NULL) AS abyss_jewel,
        if(JSONHas(item_json, 'delve'), toUInt8(JSONExtractBool(item_json, 'delve')), NULL) AS delve,
        if(JSONHas(item_json, 'elder'), toUInt8(JSONExtractBool(item_json, 'elder')), NULL) AS elder,
        if(JSONHas(item_json, 'shaper'), toUInt8(JSONExtractBool(item_json, 'shaper')), NULL) AS shaper,
        if(JSONHas(item_json, 'searing'), toUInt8(JSONExtractBool(item_json, 'searing')), NULL) AS searing,
        if(JSONHas(item_json, 'tangled'), toUInt8(JSONExtractBool(item_json, 'tangled')), NULL) AS tangled,
        if(JSONHas(item_json, 'veiled'), toUInt8(JSONExtractBool(item_json, 'veiled')), NULL) AS veiled,
        if(JSONHas(item_json, 'memoryItem'), toUInt8(JSONExtractBool(item_json, 'memoryItem')), NULL) AS memory_item,
        if(JSONHas(item_json, 'mutated'), toUInt8(JSONExtractBool(item_json, 'mutated')), NULL) AS mutated,
        if(JSONHas(item_json, 'unmodifiable'), toUInt8(JSONExtractBool(item_json, 'unmodifiable')), NULL) AS unmodifiable,
        if(JSONHas(item_json, 'unmodifiableExceptChaos'), toUInt8(JSONExtractBool(item_json, 'unmodifiableExceptChaos')), NULL) AS unmodifiable_except_chaos,
        if(JSONHas(item_json, 'isRelic'), toUInt8(JSONExtractBool(item_json, 'isRelic')), NULL) AS is_relic,
        if(JSONHas(item_json, 'replica'), toUInt8(JSONExtractBool(item_json, 'replica')), NULL) AS replica,
        if(JSONHas(JSONExtractRaw(item_json, 'extended'), 'prefixes'), toUInt8(greatest(0, JSONExtractInt(JSONExtractRaw(item_json, 'extended'), 'prefixes'))), NULL) AS extended_prefixes,
        if(JSONHas(JSONExtractRaw(item_json, 'extended'), 'suffixes'), toUInt8(greatest(0, JSONExtractInt(JSONExtractRaw(item_json, 'extended'), 'suffixes'))), NULL) AS extended_suffixes,
        nullIf(JSONExtractString(JSONExtractRaw(item_json, 'hybrid'), 'baseTypeName'), '') AS hybrid_base_type_name,
        if(JSONHas(JSONExtractRaw(item_json, 'hybrid'), 'isVaalGem'), toUInt8(JSONExtractBool(JSONExtractRaw(item_json, 'hybrid'), 'isVaalGem')), NULL) AS hybrid_is_vaal_gem,
        nullIf(JSONExtractString(JSONExtractRaw(item_json, 'hybrid'), 'secDescrText'), '') AS hybrid_sec_descr_text,
        nullIf(JSONExtractString(JSONExtractRaw(item_json, 'incubatedItem'), 'name'), '') AS incubated_item_name,
        if(JSONHas(JSONExtractRaw(item_json, 'incubatedItem'), 'level'), toUInt16(greatest(0, JSONExtractInt(JSONExtractRaw(item_json, 'incubatedItem'), 'level'))), NULL) AS incubated_item_level,
        if(JSONHas(JSONExtractRaw(item_json, 'incubatedItem'), 'progress'), toUInt32(greatest(0, JSONExtractInt(JSONExtractRaw(item_json, 'incubatedItem'), 'progress'))), NULL) AS incubated_item_progress,
        if(JSONHas(JSONExtractRaw(item_json, 'incubatedItem'), 'total'), toUInt32(greatest(0, JSONExtractInt(JSONExtractRaw(item_json, 'incubatedItem'), 'total'))), NULL) AS incubated_item_total,
        if(JSONHas(JSONExtractRaw(item_json, 'influences'), 'crusader'), toUInt8(JSONExtractBool(JSONExtractRaw(item_json, 'influences'), 'crusader')), NULL) AS influence_crusader,
        if(JSONHas(JSONExtractRaw(item_json, 'influences'), 'elder'), toUInt8(JSONExtractBool(JSONExtractRaw(item_json, 'influences'), 'elder')), NULL) AS influence_elder,
        if(JSONHas(JSONExtractRaw(item_json, 'influences'), 'hunter'), toUInt8(JSONExtractBool(JSONExtractRaw(item_json, 'influences'), 'hunter')), NULL) AS influence_hunter,
        if(JSONHas(JSONExtractRaw(item_json, 'influences'), 'redeemer'), toUInt8(JSONExtractBool(JSONExtractRaw(item_json, 'influences'), 'redeemer')), NULL) AS influence_redeemer,
        if(JSONHas(JSONExtractRaw(item_json, 'influences'), 'shaper'), toUInt8(JSONExtractBool(JSONExtractRaw(item_json, 'influences'), 'shaper')), NULL) AS influence_shaper,
        if(JSONHas(JSONExtractRaw(item_json, 'influences'), 'warlord'), toUInt8(JSONExtractBool(JSONExtractRaw(item_json, 'influences'), 'warlord')), NULL) AS influence_warlord,
        item_json
    FROM poe_trade.raw_public_stash_pages AS base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(base.payload_json, 'items')) AS item_index,
        JSONExtractArrayRaw(base.payload_json, 'items') AS item_json
    WHERE base.league = 'Mirage'
),
socketed_item_base AS (
    SELECT
        item_base.ingested_at,
        item_base.realm,
        item_base.league,
        item_base.stash_id,
        item_base.stash_json_id,
        item_base.checkpoint,
        item_base.next_change_id,
        item_base.account_name,
        item_base.stash_name,
        item_base.stash_type,
        item_base.public_flag,
        item_base.root_item_ordinal,
        item_base.root_item_id,
        item_base.item_id AS parent_item_id,
        nullIf(JSONExtractString(socketed_item_json, 'id'), '') AS item_id,
        nullIf(JSONExtractString(socketed_item_json, 'league'), '') AS item_league,
        nullIf(JSONExtractString(socketed_item_json, 'name'), '') AS item_name,
        nullIf(JSONExtractString(socketed_item_json, 'typeLine'), '') AS item_type_line,
        nullIf(JSONExtractString(socketed_item_json, 'baseType'), '') AS base_type,
        nullIf(JSONExtractString(socketed_item_json, 'rarity'), '') AS rarity,
        nullIf(JSONExtractString(socketed_item_json, 'inventoryId'), '') AS inventory_id,
        nullIf(JSONExtractString(socketed_item_json, 'note'), '') AS note,
        nullIf(JSONExtractString(socketed_item_json, 'forum_note'), '') AS forum_note,
        nullIf(JSONExtractString(socketed_item_json, 'icon'), '') AS icon,
        nullIf(JSONExtractString(socketed_item_json, 'descrText'), '') AS descr_text,
        nullIf(JSONExtractString(socketed_item_json, 'secDescrText'), '') AS sec_descr_text,
        nullIf(JSONExtractString(socketed_item_json, 'artFilename'), '') AS art_filename,
        nullIf(JSONExtractString(socketed_item_json, 'builtInSupport'), '') AS built_in_support,
        nullIf(JSONExtractString(socketed_item_json, 'colour'), '') AS item_colour,
        nullIf(JSONExtractString(socketed_item_json, 'stackSizeText'), '') AS stack_size_text,
        if(JSONHas(socketed_item_json, 'ilvl'), toUInt16(greatest(0, JSONExtractInt(socketed_item_json, 'ilvl'))), NULL) AS ilvl,
        if(JSONHas(socketed_item_json, 'itemLevel'), toUInt16(greatest(0, JSONExtractInt(socketed_item_json, 'itemLevel'))), NULL) AS item_level,
        if(JSONHas(socketed_item_json, 'monsterLevel'), toUInt16(greatest(0, JSONExtractInt(socketed_item_json, 'monsterLevel'))), NULL) AS monster_level,
        if(JSONHas(socketed_item_json, 'stackSize'), toUInt32(greatest(0, JSONExtractInt(socketed_item_json, 'stackSize'))), NULL) AS stack_size,
        if(JSONHas(socketed_item_json, 'maxStackSize'), toUInt32(greatest(0, JSONExtractInt(socketed_item_json, 'maxStackSize'))), NULL) AS max_stack_size,
        if(JSONHas(socketed_item_json, 'frameType'), toUInt8(greatest(0, JSONExtractInt(socketed_item_json, 'frameType'))), NULL) AS frame_type,
        if(JSONHas(socketed_item_json, 'w'), toUInt8(greatest(0, JSONExtractInt(socketed_item_json, 'w'))), NULL) AS w,
        if(JSONHas(socketed_item_json, 'h'), toUInt8(greatest(0, JSONExtractInt(socketed_item_json, 'h'))), NULL) AS h,
        if(JSONHas(socketed_item_json, 'x'), toUInt8(greatest(0, JSONExtractInt(socketed_item_json, 'x'))), NULL) AS x,
        if(JSONHas(socketed_item_json, 'y'), toUInt8(greatest(0, JSONExtractInt(socketed_item_json, 'y'))), NULL) AS y,
        if(JSONHas(socketed_item_json, 'socket'), toUInt8(greatest(0, JSONExtractInt(socketed_item_json, 'socket'))), NULL) AS socket_index,
        if(JSONHas(socketed_item_json, 'talismanTier'), toUInt8(greatest(0, JSONExtractInt(socketed_item_json, 'talismanTier'))), NULL) AS talisman_tier,
        if(JSONHas(socketed_item_json, 'foilVariation'), toUInt16(greatest(0, JSONExtractInt(socketed_item_json, 'foilVariation'))), NULL) AS foil_variation,
        if(JSONHas(socketed_item_json, 'verified'), toUInt8(JSONExtractBool(socketed_item_json, 'verified')), NULL) AS verified,
        if(JSONHas(socketed_item_json, 'identified'), toUInt8(JSONExtractBool(socketed_item_json, 'identified')), NULL) AS identified,
        if(JSONHas(socketed_item_json, 'corrupted'), toUInt8(JSONExtractBool(socketed_item_json, 'corrupted')), NULL) AS corrupted,
        if(JSONHas(socketed_item_json, 'fractured'), toUInt8(JSONExtractBool(socketed_item_json, 'fractured')), NULL) AS fractured,
        if(JSONHas(socketed_item_json, 'synthesised'), toUInt8(JSONExtractBool(socketed_item_json, 'synthesised')), NULL) AS synthesised,
        if(JSONHas(socketed_item_json, 'duplicated'), toUInt8(JSONExtractBool(socketed_item_json, 'duplicated')), NULL) AS duplicated,
        if(JSONHas(socketed_item_json, 'split'), toUInt8(JSONExtractBool(socketed_item_json, 'split')), NULL) AS split_flag,
        if(JSONHas(socketed_item_json, 'support'), toUInt8(JSONExtractBool(socketed_item_json, 'support')), NULL) AS support_flag,
        if(JSONHas(socketed_item_json, 'abyssJewel'), toUInt8(JSONExtractBool(socketed_item_json, 'abyssJewel')), NULL) AS abyss_jewel,
        if(JSONHas(socketed_item_json, 'delve'), toUInt8(JSONExtractBool(socketed_item_json, 'delve')), NULL) AS delve,
        if(JSONHas(socketed_item_json, 'elder'), toUInt8(JSONExtractBool(socketed_item_json, 'elder')), NULL) AS elder,
        if(JSONHas(socketed_item_json, 'shaper'), toUInt8(JSONExtractBool(socketed_item_json, 'shaper')), NULL) AS shaper,
        if(JSONHas(socketed_item_json, 'searing'), toUInt8(JSONExtractBool(socketed_item_json, 'searing')), NULL) AS searing,
        if(JSONHas(socketed_item_json, 'tangled'), toUInt8(JSONExtractBool(socketed_item_json, 'tangled')), NULL) AS tangled,
        if(JSONHas(socketed_item_json, 'veiled'), toUInt8(JSONExtractBool(socketed_item_json, 'veiled')), NULL) AS veiled,
        if(JSONHas(socketed_item_json, 'memoryItem'), toUInt8(JSONExtractBool(socketed_item_json, 'memoryItem')), NULL) AS memory_item,
        if(JSONHas(socketed_item_json, 'mutated'), toUInt8(JSONExtractBool(socketed_item_json, 'mutated')), NULL) AS mutated,
        if(JSONHas(socketed_item_json, 'unmodifiable'), toUInt8(JSONExtractBool(socketed_item_json, 'unmodifiable')), NULL) AS unmodifiable,
        if(JSONHas(socketed_item_json, 'unmodifiableExceptChaos'), toUInt8(JSONExtractBool(socketed_item_json, 'unmodifiableExceptChaos')), NULL) AS unmodifiable_except_chaos,
        if(JSONHas(socketed_item_json, 'isRelic'), toUInt8(JSONExtractBool(socketed_item_json, 'isRelic')), NULL) AS is_relic,
        if(JSONHas(socketed_item_json, 'replica'), toUInt8(JSONExtractBool(socketed_item_json, 'replica')), NULL) AS replica,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'extended'), 'prefixes'), toUInt8(greatest(0, JSONExtractInt(JSONExtractRaw(socketed_item_json, 'extended'), 'prefixes'))), NULL) AS extended_prefixes,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'extended'), 'suffixes'), toUInt8(greatest(0, JSONExtractInt(JSONExtractRaw(socketed_item_json, 'extended'), 'suffixes'))), NULL) AS extended_suffixes,
        nullIf(JSONExtractString(JSONExtractRaw(socketed_item_json, 'hybrid'), 'baseTypeName'), '') AS hybrid_base_type_name,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'hybrid'), 'isVaalGem'), toUInt8(JSONExtractBool(JSONExtractRaw(socketed_item_json, 'hybrid'), 'isVaalGem')), NULL) AS hybrid_is_vaal_gem,
        nullIf(JSONExtractString(JSONExtractRaw(socketed_item_json, 'hybrid'), 'secDescrText'), '') AS hybrid_sec_descr_text,
        nullIf(JSONExtractString(JSONExtractRaw(socketed_item_json, 'incubatedItem'), 'name'), '') AS incubated_item_name,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'incubatedItem'), 'level'), toUInt16(greatest(0, JSONExtractInt(JSONExtractRaw(socketed_item_json, 'incubatedItem'), 'level'))), NULL) AS incubated_item_level,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'incubatedItem'), 'progress'), toUInt32(greatest(0, JSONExtractInt(JSONExtractRaw(socketed_item_json, 'incubatedItem'), 'progress'))), NULL) AS incubated_item_progress,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'incubatedItem'), 'total'), toUInt32(greatest(0, JSONExtractInt(JSONExtractRaw(socketed_item_json, 'incubatedItem'), 'total'))), NULL) AS incubated_item_total,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'influences'), 'crusader'), toUInt8(JSONExtractBool(JSONExtractRaw(socketed_item_json, 'influences'), 'crusader')), NULL) AS influence_crusader,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'influences'), 'elder'), toUInt8(JSONExtractBool(JSONExtractRaw(socketed_item_json, 'influences'), 'elder')), NULL) AS influence_elder,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'influences'), 'hunter'), toUInt8(JSONExtractBool(JSONExtractRaw(socketed_item_json, 'influences'), 'hunter')), NULL) AS influence_hunter,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'influences'), 'redeemer'), toUInt8(JSONExtractBool(JSONExtractRaw(socketed_item_json, 'influences'), 'redeemer')), NULL) AS influence_redeemer,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'influences'), 'shaper'), toUInt8(JSONExtractBool(JSONExtractRaw(socketed_item_json, 'influences'), 'shaper')), NULL) AS influence_shaper,
        if(JSONHas(JSONExtractRaw(socketed_item_json, 'influences'), 'warlord'), toUInt8(JSONExtractBool(JSONExtractRaw(socketed_item_json, 'influences'), 'warlord')), NULL) AS influence_warlord,
        toUInt32(socketed_item_index) AS socketed_item_ordinal,
        socketed_item_json
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_base.item_json, 'socketedItems')) AS socketed_item_index,
        JSONExtractArrayRaw(item_base.item_json, 'socketedItems') AS socketed_item_json
)
SELECT * FROM (
    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item' AS row_type,
        CAST(NULL AS Nullable(String)) AS array_group,
        root_item_ordinal, root_item_id, item_id,
        CAST(NULL AS Nullable(String)) AS parent_item_id,
        CAST(NULL AS Nullable(UInt32)) AS array_ordinal,
        CAST(NULL AS Nullable(UInt32)) AS value_ordinal,
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)) AS socket_group,
        CAST(NULL AS Nullable(String)) AS socket_attr,
        CAST(NULL AS Nullable(String)) AS socket_colour,
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)) AS attribute_name,
        CAST(NULL AS Nullable(Int32)) AS attribute_display_mode,
        CAST(NULL AS Nullable(Int32)) AS attribute_type,
        CAST(NULL AS Nullable(String)) AS attribute_suffix,
        CAST(NULL AS Nullable(Float64)) AS attribute_progress,
        CAST(NULL AS Nullable(String)) AS attribute_value_text,
        CAST(NULL AS Nullable(Int32)) AS attribute_value_style,
        CAST(NULL AS Nullable(String)) AS mod_text,
        CAST(NULL AS Nullable(String)) AS logbook_name,
        CAST(NULL AS Nullable(String)) AS logbook_faction_id,
        CAST(NULL AS Nullable(String)) AS logbook_faction_name,
        CAST(NULL AS Nullable(String)) AS ultimatum_type,
        CAST(NULL AS Nullable(UInt8)) AS ultimatum_tier
    FROM item_base

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_attribute' AS row_type,
        'properties' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal) AS array_ordinal,
        toUInt32(value_ordinal) AS value_ordinal,
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), '') AS attribute_name,
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL) AS attribute_display_mode,
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL) AS attribute_type,
        nullIf(JSONExtractString(attribute_json, 'suffix'), '') AS attribute_suffix,
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL) AS attribute_progress,
        nullIf(JSONExtractString(attribute_value_json, 1), '') AS attribute_value_text,
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL) AS attribute_value_style,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, 'properties')) AS array_ordinal,
        JSONExtractArrayRaw(item_json, 'properties') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_attribute' AS row_type,
        'requirements' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, 'requirements')) AS array_ordinal,
        JSONExtractArrayRaw(item_json, 'requirements') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_attribute' AS row_type,
        'additionalProperties' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, 'additionalProperties')) AS array_ordinal,
        JSONExtractArrayRaw(item_json, 'additionalProperties') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_attribute' AS row_type,
        'nextLevelRequirements' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, 'nextLevelRequirements')) AS array_ordinal,
        JSONExtractArrayRaw(item_json, 'nextLevelRequirements') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_attribute' AS row_type,
        'hybrid.properties' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(JSONExtractRaw(item_json, 'hybrid'), 'properties')) AS array_ordinal,
        JSONExtractArrayRaw(JSONExtractRaw(item_json, 'hybrid'), 'properties') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_mod' AS row_type,
        mod_group AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), CAST(NULL AS Nullable(UInt32)),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        JSONExtractString(mod_json),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN ['explicitMods', 'implicitMods', 'enchantMods', 'fracturedMods', 'craftedMods', 'utilityMods', 'veiledMods', 'flavourText', 'mutatedMods'] AS mod_group
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, mod_group)) AS array_ordinal,
        JSONExtractArrayRaw(item_json, mod_group) AS mod_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_mod' AS row_type,
        'hybrid.explicitMods' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), CAST(NULL AS Nullable(UInt32)),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        JSONExtractString(mod_json),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(JSONExtractRaw(item_json, 'hybrid'), 'explicitMods')) AS array_ordinal,
        JSONExtractArrayRaw(JSONExtractRaw(item_json, 'hybrid'), 'explicitMods') AS mod_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_socket' AS row_type,
        'sockets' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), CAST(NULL AS Nullable(UInt32)),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        if(JSONHas(socket_json, 'group'), toUInt8(greatest(0, JSONExtractInt(socket_json, 'group'))), NULL),
        nullIf(JSONExtractString(socket_json, 'attr'), ''),
        nullIf(JSONExtractString(socket_json, 'sColour'), ''),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        CAST(NULL AS Nullable(String)),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, 'sockets')) AS array_ordinal,
        JSONExtractArrayRaw(item_json, 'sockets') AS socket_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_ultimatum_mod' AS row_type,
        'ultimatumMods' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), CAST(NULL AS Nullable(UInt32)),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        CAST(NULL AS Nullable(String)),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        nullIf(JSONExtractString(ultimatum_json, 'type'), ''),
        if(JSONHas(ultimatum_json, 'tier'), toUInt8(greatest(0, JSONExtractInt(ultimatum_json, 'tier'))), NULL)
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, 'ultimatumMods')) AS array_ordinal,
        JSONExtractArrayRaw(item_json, 'ultimatumMods') AS ultimatum_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'item_logbook_mod' AS row_type,
        'logbookMods' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        JSONExtractString(mod_json),
        nullIf(JSONExtractString(logbook_json, 'name'), ''),
        nullIf(JSONExtractString(JSONExtractRaw(logbook_json, 'faction'), 'id'), ''),
        nullIf(JSONExtractString(JSONExtractRaw(logbook_json, 'faction'), 'name'), ''),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(item_json, 'logbookMods')) AS array_ordinal,
        JSONExtractArrayRaw(item_json, 'logbookMods') AS logbook_json
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(logbook_json, 'mods')) AS value_ordinal,
        JSONExtractArrayRaw(logbook_json, 'mods') AS mod_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item' AS row_type,
        CAST(NULL AS Nullable(String)) AS array_group,
        root_item_ordinal, root_item_id, item_id, parent_item_id,
        socketed_item_ordinal AS array_ordinal,
        CAST(NULL AS Nullable(UInt32)) AS value_ordinal,
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item_attribute' AS row_type,
        'properties' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(socketed_item_json, 'properties')) AS array_ordinal,
        JSONExtractArrayRaw(socketed_item_json, 'properties') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item_attribute' AS row_type,
        'requirements' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(socketed_item_json, 'requirements')) AS array_ordinal,
        JSONExtractArrayRaw(socketed_item_json, 'requirements') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item_attribute' AS row_type,
        'additionalProperties' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(socketed_item_json, 'additionalProperties')) AS array_ordinal,
        JSONExtractArrayRaw(socketed_item_json, 'additionalProperties') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item_attribute' AS row_type,
        'nextLevelRequirements' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(socketed_item_json, 'nextLevelRequirements')) AS array_ordinal,
        JSONExtractArrayRaw(socketed_item_json, 'nextLevelRequirements') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item_attribute' AS row_type,
        'hybrid.properties' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), toUInt32(value_ordinal),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        nullIf(JSONExtractString(attribute_json, 'name'), ''),
        if(JSONHas(attribute_json, 'displayMode'), toInt32(JSONExtractInt(attribute_json, 'displayMode')), NULL),
        if(JSONHas(attribute_json, 'type'), toInt32(JSONExtractInt(attribute_json, 'type')), NULL),
        nullIf(JSONExtractString(attribute_json, 'suffix'), ''),
        if(JSONHas(attribute_json, 'progress'), toFloat64(JSONExtractFloat(attribute_json, 'progress')), NULL),
        nullIf(JSONExtractString(attribute_value_json, 1), ''),
        if(JSONHas(attribute_value_json, 2), toInt32(JSONExtractInt(attribute_value_json, 2)), NULL),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(JSONExtractRaw(socketed_item_json, 'hybrid'), 'properties')) AS array_ordinal,
        JSONExtractArrayRaw(JSONExtractRaw(socketed_item_json, 'hybrid'), 'properties') AS attribute_json
    ARRAY JOIN
        arrayEnumerate(emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values'))) AS value_ordinal,
        emptyArrayToSingle(JSONExtractArrayRaw(attribute_json, 'values')) AS attribute_value_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item_mod' AS row_type,
        mod_group AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), CAST(NULL AS Nullable(UInt32)),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        JSONExtractString(mod_json),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base
    ARRAY JOIN ['explicitMods', 'fracturedMods'] AS mod_group
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(socketed_item_json, mod_group)) AS array_ordinal,
        JSONExtractArrayRaw(socketed_item_json, mod_group) AS mod_json

    UNION ALL

    SELECT
        ingested_at, realm, league, stash_id, stash_json_id, checkpoint, next_change_id,
        account_name, stash_name, stash_type, public_flag,
        'socketed_item_mod' AS row_type,
        'hybrid.explicitMods' AS array_group,
        root_item_ordinal, root_item_id, item_id, item_id AS parent_item_id,
        toUInt32(array_ordinal), CAST(NULL AS Nullable(UInt32)),
        item_league, item_name, item_type_line, base_type, rarity, inventory_id, note,
        forum_note, icon, descr_text, sec_descr_text, art_filename, built_in_support,
        item_colour, stack_size_text, ilvl, item_level, monster_level, stack_size,
        max_stack_size, frame_type, w, h, x, y, socket_index,
        CAST(NULL AS Nullable(UInt8)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)),
        talisman_tier, foil_variation, verified, identified, corrupted, fractured,
        synthesised, duplicated, split_flag, support_flag, abyss_jewel, delve, elder,
        shaper, searing, tangled, veiled, memory_item, mutated, unmodifiable,
        unmodifiable_except_chaos, is_relic, replica, extended_prefixes,
        extended_suffixes, hybrid_base_type_name, hybrid_is_vaal_gem,
        hybrid_sec_descr_text, incubated_item_name, incubated_item_level,
        incubated_item_progress, incubated_item_total, influence_crusader,
        influence_elder, influence_hunter, influence_redeemer, influence_shaper,
        influence_warlord,
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(Int32)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Float64)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(Int32)),
        JSONExtractString(mod_json),
        CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(String)), CAST(NULL AS Nullable(UInt8))
    FROM socketed_item_base
    ARRAY JOIN
        arrayEnumerate(JSONExtractArrayRaw(JSONExtractRaw(socketed_item_json, 'hybrid'), 'explicitMods')) AS array_ordinal,
        JSONExtractArrayRaw(JSONExtractRaw(socketed_item_json, 'hybrid'), 'explicitMods') AS mod_json
);
