ALTER TABLE poe_trade.account_stash_scan_runs
    MODIFY TTL started_at + INTERVAL 90 DAY DELETE;

ALTER TABLE poe_trade.account_stash_active_scans
    MODIFY TTL updated_at + INTERVAL 90 DAY DELETE;

ALTER TABLE poe_trade.account_stash_published_scans
    MODIFY TTL published_at + INTERVAL 90 DAY DELETE;
