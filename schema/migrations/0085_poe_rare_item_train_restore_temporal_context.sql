CREATE TABLE poe_trade.poe_rare_item_train_v3
ENGINE = MergeTree()
PARTITION BY toYYYYMM(observed_at)
ORDER BY (league, category, base_type, observed_at, item_fingerprint, item_id)
AS
SELECT
    *,
    toString(
        cityHash64(
            concat(
                ifNull(league, ''),
                '|', ifNull(category, ''),
                '|', ifNull(base_type, ''),
                '|', ifNull(toString(ilvl), ''),
                '|', ifNull(toString(corrupted), ''),
                '|', ifNull(toString(fractured), ''),
                '|', ifNull(toString(synthesised), ''),
                '|', ifNull(toString(prefix_count), ''),
                '|', ifNull(toString(suffix_count), ''),
                '|', ifNull(toString(explicit_count), ''),
                '|', ifNull(toString(implicit_count), '')
            )
        )
    ) AS item_fingerprint
FROM poe_trade.poe_rare_item_train_v1_context_legacy
LIMIT 0;

INSERT INTO poe_trade.poe_rare_item_train_v3
SELECT
    *,
    toString(
        cityHash64(
            concat(
                ifNull(league, ''),
                '|', ifNull(category, ''),
                '|', ifNull(base_type, ''),
                '|', ifNull(toString(ilvl), ''),
                '|', ifNull(toString(corrupted), ''),
                '|', ifNull(toString(fractured), ''),
                '|', ifNull(toString(synthesised), ''),
                '|', ifNull(toString(prefix_count), ''),
                '|', ifNull(toString(suffix_count), ''),
                '|', ifNull(toString(explicit_count), ''),
                '|', ifNull(toString(implicit_count), '')
            )
        )
    ) AS item_fingerprint
FROM poe_trade.poe_rare_item_train_v1_context_legacy;

RENAME TABLE
    poe_trade.poe_rare_item_train TO poe_trade.poe_rare_item_train_v2_lean,
    poe_trade.poe_rare_item_train_v3 TO poe_trade.poe_rare_item_train;
