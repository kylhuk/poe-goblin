ALTER TABLE poe_trade.raw_account_stash_snapshot
    ADD COLUMN IF NOT EXISTS account_name String DEFAULT ''
    AFTER league;

ALTER TABLE poe_trade.silver_account_stash_items
    ADD COLUMN IF NOT EXISTS account_name String DEFAULT ''
    AFTER league;
