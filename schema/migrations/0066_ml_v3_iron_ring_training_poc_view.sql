CREATE VIEW IF NOT EXISTS poe_trade.v_ml_v3_iron_ring_training_poc AS
SELECT
    *
FROM poe_trade.v_ml_v3_item_training_poc
WHERE category = 'ring'
    AND base_type = 'Iron Ring'
    AND league = 'Mirage';
