ALTER TABLE poe_trade.scanner_recommendations
    ADD COLUMN IF NOT EXISTS recommendation_source Nullable(String) AFTER league;

ALTER TABLE poe_trade.scanner_recommendations
    ADD COLUMN IF NOT EXISTS recommendation_contract_version Nullable(UInt32) AFTER recommendation_source;

ALTER TABLE poe_trade.scanner_recommendations
    ADD COLUMN IF NOT EXISTS producer_version Nullable(String) AFTER recommendation_contract_version;

ALTER TABLE poe_trade.scanner_recommendations
    ADD COLUMN IF NOT EXISTS producer_run_id Nullable(String) AFTER producer_version;

ALTER TABLE poe_trade.scanner_alert_log
    ADD COLUMN IF NOT EXISTS recommendation_source Nullable(String) AFTER league;

ALTER TABLE poe_trade.scanner_alert_log
    ADD COLUMN IF NOT EXISTS recommendation_contract_version Nullable(UInt32) AFTER recommendation_source;

ALTER TABLE poe_trade.scanner_alert_log
    ADD COLUMN IF NOT EXISTS producer_version Nullable(String) AFTER recommendation_contract_version;

ALTER TABLE poe_trade.scanner_alert_log
    ADD COLUMN IF NOT EXISTS producer_run_id Nullable(String) AFTER producer_version;
