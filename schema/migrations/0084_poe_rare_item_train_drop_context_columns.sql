CREATE TABLE poe_trade.poe_rare_item_train_v2
ENGINE = MergeTree()
PARTITION BY tuple()
ORDER BY item_id
AS
SELECT * EXCEPT(league, category, base_type, observed_at)
FROM poe_trade.poe_rare_item_train
LIMIT 0;

INSERT INTO poe_trade.poe_rare_item_train_v2
SELECT * EXCEPT(league, category, base_type, observed_at)
FROM poe_trade.poe_rare_item_train;

RENAME TABLE
    poe_trade.poe_rare_item_train TO poe_trade.poe_rare_item_train_v1_context_legacy,
    poe_trade.poe_rare_item_train_v2 TO poe_trade.poe_rare_item_train;
