-- Backfill ml_item_mod_features_v1 for Mirage league
-- Simple approach: populate with mod_count from tokens, empty mod_features for now
-- Real feature extraction can be done via Python with better token matching

INSERT INTO poe_trade.ml_item_mod_features_v1 (league, item_id, mod_features_json, mod_count, as_of_ts, updated_at)
SELECT 
    t.league,
    t.item_id,
    '{}' AS mod_features_json,
    t.cnt AS mod_count,
    now64(3) AS as_of_ts,
    now64(3) AS updated_at
FROM (
    SELECT league, item_id, count() as cnt
    FROM poe_trade.ml_item_mod_tokens_v1
    WHERE league = 'Mirage'
    GROUP BY league, item_id
    LIMIT 500000
);
