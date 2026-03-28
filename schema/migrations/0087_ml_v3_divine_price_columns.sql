ALTER TABLE poe_trade.ml_v3_listing_episodes
    ADD COLUMN IF NOT EXISTS latest_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS min_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS fx_hour Nullable(DateTime64(0, 'UTC')),
    ADD COLUMN IF NOT EXISTS fx_source LowCardinality(String),
    ADD COLUMN IF NOT EXISTS fx_chaos_per_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_fast_sale_24h_price_divine Nullable(Float64);

ALTER TABLE poe_trade.ml_v3_training_examples
    ADD COLUMN IF NOT EXISTS fx_hour Nullable(DateTime64(0, 'UTC')),
    ADD COLUMN IF NOT EXISTS fx_source LowCardinality(String),
    ADD COLUMN IF NOT EXISTS fx_chaos_per_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_price_divine Nullable(Float64),
    ADD COLUMN IF NOT EXISTS target_fast_sale_24h_price_divine Nullable(Float64);
