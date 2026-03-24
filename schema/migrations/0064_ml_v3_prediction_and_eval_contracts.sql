ALTER TABLE poe_trade.ml_v3_price_predictions
    ADD COLUMN IF NOT EXISTS strategy_family LowCardinality(String) DEFAULT '__legacy_missing_strategy_family__' AFTER route,
    ADD COLUMN IF NOT EXISTS cohort_key String DEFAULT '__legacy_missing_cohort_key__' AFTER strategy_family,
    ADD COLUMN IF NOT EXISTS parent_cohort_key String DEFAULT '__legacy_missing_parent_cohort_key__' AFTER cohort_key,
    ADD COLUMN IF NOT EXISTS engine_version LowCardinality(String) DEFAULT 'ml_v3_unknown_engine' AFTER prediction_source,
    ADD COLUMN IF NOT EXISTS fallback_depth UInt8 DEFAULT 0 AFTER fallback_reason,
    ADD COLUMN IF NOT EXISTS incumbent_flag UInt8 DEFAULT 0 AFTER fallback_depth;
