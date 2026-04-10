ALTER TABLE poe_trade.account_stash_scan_items_v2
    ADD COLUMN IF NOT EXISTS price_evaluation LowCardinality(String) AFTER price_band;

ALTER TABLE poe_trade.account_stash_item_history_v2
    ADD COLUMN IF NOT EXISTS price_evaluation LowCardinality(String) AFTER price_band;
