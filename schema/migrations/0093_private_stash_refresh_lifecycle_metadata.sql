ALTER TABLE poe_trade.account_stash_scan_runs
    ADD COLUMN IF NOT EXISTS scan_kind LowCardinality(String) DEFAULT 'stash_scan' AFTER realm;

ALTER TABLE poe_trade.account_stash_scan_runs
    ADD COLUMN IF NOT EXISTS source_scan_id String DEFAULT '' AFTER scan_kind;

ALTER TABLE poe_trade.account_stash_active_scans
    ADD COLUMN IF NOT EXISTS scan_kind LowCardinality(String) DEFAULT 'stash_scan' AFTER realm;

ALTER TABLE poe_trade.account_stash_active_scans
    ADD COLUMN IF NOT EXISTS source_scan_id String DEFAULT '' AFTER scan_kind;
