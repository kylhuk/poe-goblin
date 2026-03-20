CREATE TABLE IF NOT EXISTS poe_trade.ml_item_mod_feature_states_v1 (
    league LowCardinality(String),
    item_id String,
    mod_tokens_state AggregateFunction(groupArray, String),
    max_as_of_ts_state AggregateFunction(max, DateTime64(3, 'UTC')),
    updated_at SimpleAggregateFunction(max, DateTime64(3, 'UTC'))
) ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(updated_at)
ORDER BY (league, item_id)
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_ml_item_mod_feature_states_v1
TO poe_trade.ml_item_mod_feature_states_v1 AS
SELECT
    league,
    item_id,
    groupArrayState(mod_token) AS mod_tokens_state,
    maxState(as_of_ts) AS max_as_of_ts_state,
    now64(3) AS updated_at
FROM poe_trade.ml_item_mod_tokens_v1
GROUP BY league, item_id;

INSERT INTO poe_trade.ml_item_mod_feature_states_v1
SELECT
    league,
    item_id,
    groupArrayState(mod_token) AS mod_tokens_state,
    maxState(as_of_ts) AS max_as_of_ts_state,
    now64(3) AS updated_at
FROM poe_trade.ml_item_mod_tokens_v1
GROUP BY league, item_id;
