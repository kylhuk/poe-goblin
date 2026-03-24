ALTER TABLE poe_trade.ml_v3_training_examples
    ADD COLUMN IF NOT EXISTS strategy_family LowCardinality(String) DEFAULT '__legacy_missing_strategy_family__' AFTER route,
    ADD COLUMN IF NOT EXISTS cohort_key String DEFAULT '__legacy_missing_cohort_key__' AFTER strategy_family,
    ADD COLUMN IF NOT EXISTS material_state_signature String DEFAULT '__legacy_missing_material_state_signature__' AFTER cohort_key,
    ADD COLUMN IF NOT EXISTS item_state_key String DEFAULT '__legacy_missing_item_state_key__' AFTER synthesised,
    ADD COLUMN IF NOT EXISTS target_likely_sold Nullable(UInt8) AFTER target_sale_probability_24h,
    ADD COLUMN IF NOT EXISTS target_time_to_exit_hours Nullable(Float32) AFTER target_likely_sold,
    ADD COLUMN IF NOT EXISTS target_sale_price_anchor_chaos Nullable(Float64) AFTER target_time_to_exit_hours;
