CREATE TABLE IF NOT EXISTS poe_trade.qa_parity_contract (
    table_name String,
    contract_group LowCardinality(String),
    matching_mode Enum8('exact_order' = 1, 'set_equivalent' = 2, 'sorted' = 3),
    key_columns Array(String),
    comparison_columns Array(String),
    watermark_columns Array(String),
    duplicate_policy String,
    notes String,
    created_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY table_name;

INSERT INTO poe_trade.qa_parity_contract VALUES
(
    'raw_poeninja_currency_overview',
    'currency',
    'exact_order',
    ['league', 'currency_type_name', 'sample_time_utc'],
    ['line_type', 'chaos_equivalent', 'listing_count', 'payload_json', 'stale'],
    ['sample_time_utc'],
    'append-only ordering preserved by ingestion',
    'No dedup; every row from the parser must survive in order',
    now()
),
(
    'ml_price_labels_v1',
    'labels',
    'exact_order',
    ['league', 'realm', 'item_id', 'as_of_ts'],
    ['normalized_price_chaos', 'stack_size', 'outlier_status', 'label_quality', 'category', 'base_type'],
    ['as_of_ts'],
    'ReplacingMergeTree by updated_at',
    'Every update must keep normalized price + label metadata in lockstep',
    now()
),
(
    'ml_item_mod_features_v1',
    'mod_features',
    'exact_order',
    ['league', 'item_id'],
    ['mod_features_json', 'mod_count', 'as_of_ts'],
    ['as_of_ts'],
    'ReplacingMergeTree by updated_at ensures deterministic dedup',
    'Mod token ordering must stay exactly as derived from ARRAY JOIN',
    now()
),
(
    'ml_price_dataset_v1',
    'dataset',
    'exact_order',
    ['league', 'item_id', 'as_of_ts'],
    ['normalized_price_chaos', 'support_count_recent', 'mod_token_count', 'route_candidate'],
    ['as_of_ts'],
    'ReplacingMergeTree by updated_at',
    'Every column that downstream features rely on must be identical; no silent drifts',
    now()
),
(
    'ml_comps_v1',
    'comps',
    'exact_order',
    ['league', 'as_of_ts', 'target_item_id', 'comp_item_id'],
    ['distance_score', 'comp_price_chaos', 'retrieval_window_hours'],
    ['as_of_ts'],
    'ReplacingMergeTree by updated_at',
    'Join output must match legacy pairings exactly',
    now()
),
(
    'ml_serving_profile_v1',
    'serving_profile',
    'set_equivalent',
    ['league', 'category', 'base_type', 'profile_as_of_ts'],
    ['reference_price_p10', 'reference_price_p50', 'reference_price_p90', 'support_count_recent'],
    ['profile_as_of_ts'],
    'ReplacingMergeTree by updated_at',
    'Serving profile quantiles may reorder, but values must match per (league, category, base_type)',
    now()
);
