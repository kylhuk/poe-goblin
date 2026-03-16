CREATE VIEW IF NOT EXISTS poe_trade.v_gold_mart_diagnostics AS
SELECT
    mart_name,
    source_name,
    source_row_count,
    source_latest_at,
    source_distinct_league_count,
    source_blank_or_null_league_rows,
    gold_row_count,
    gold_latest_at,
    gold_distinct_league_count,
    gold_blank_or_null_league_rows,
    if(
        gold_latest_at IS NULL,
        NULL,
        greatest(0, dateDiff('minute', gold_latest_at, now()))
    ) AS gold_freshness_minutes,
    if(
        source_latest_at IS NULL OR gold_latest_at IS NULL,
        NULL,
        greatest(0, dateDiff('minute', gold_latest_at, source_latest_at))
    ) AS source_to_gold_lag_minutes,
    multiIf(
        source_row_count = 0,
        'source_empty',
        gold_row_count = 0,
        'gold_empty',
        source_latest_at IS NOT NULL
            AND gold_latest_at IS NOT NULL
            AND dateDiff('minute', gold_latest_at, source_latest_at) > 120,
        'gold_stale_vs_source',
        source_distinct_league_count > 0 AND gold_distinct_league_count = 0,
        'gold_league_visibility_gap',
        gold_blank_or_null_league_rows > 0,
        'gold_blank_league_rows',
        'ok'
    ) AS diagnostic_state
FROM (
    SELECT
        'gold_currency_ref_hour' AS mart_name,
        'v_cx_markets_enriched' AS source_name,
        source_stats.source_row_count,
        source_stats.source_latest_at,
        source_stats.source_distinct_league_count,
        source_stats.source_blank_or_null_league_rows,
        gold_stats.gold_row_count,
        gold_stats.gold_latest_at,
        gold_stats.gold_distinct_league_count,
        gold_stats.gold_blank_or_null_league_rows
    FROM (
        SELECT
            count() AS source_row_count,
            maxOrNull(toDateTime(hour_ts, 'UTC')) AS source_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS source_distinct_league_count,
            countIf(ifNull(league, '') = '') AS source_blank_or_null_league_rows
        FROM poe_trade.v_cx_markets_enriched
    ) AS source_stats
    CROSS JOIN (
        SELECT
            count() AS gold_row_count,
            maxOrNull(toDateTime(time_bucket, 'UTC')) AS gold_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS gold_distinct_league_count,
            countIf(ifNull(league, '') = '') AS gold_blank_or_null_league_rows
        FROM poe_trade.gold_currency_ref_hour
    ) AS gold_stats

    UNION ALL

    SELECT
        'gold_listing_ref_hour' AS mart_name,
        'v_ps_items_enriched' AS source_name,
        source_stats.source_row_count,
        source_stats.source_latest_at,
        source_stats.source_distinct_league_count,
        source_stats.source_blank_or_null_league_rows,
        gold_stats.gold_row_count,
        gold_stats.gold_latest_at,
        gold_stats.gold_distinct_league_count,
        gold_stats.gold_blank_or_null_league_rows
    FROM (
        SELECT
            count() AS source_row_count,
            maxOrNull(toDateTime(observed_at, 'UTC')) AS source_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS source_distinct_league_count,
            countIf(ifNull(league, '') = '') AS source_blank_or_null_league_rows
        FROM poe_trade.v_ps_items_enriched
    ) AS source_stats
    CROSS JOIN (
        SELECT
            count() AS gold_row_count,
            maxOrNull(toDateTime(time_bucket, 'UTC')) AS gold_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS gold_distinct_league_count,
            countIf(ifNull(league, '') = '') AS gold_blank_or_null_league_rows
        FROM poe_trade.gold_listing_ref_hour
    ) AS gold_stats

    UNION ALL

    SELECT
        'gold_liquidity_ref_hour' AS mart_name,
        'v_ps_items_enriched' AS source_name,
        source_stats.source_row_count,
        source_stats.source_latest_at,
        source_stats.source_distinct_league_count,
        source_stats.source_blank_or_null_league_rows,
        gold_stats.gold_row_count,
        gold_stats.gold_latest_at,
        gold_stats.gold_distinct_league_count,
        gold_stats.gold_blank_or_null_league_rows
    FROM (
        SELECT
            count() AS source_row_count,
            maxOrNull(toDateTime(observed_at, 'UTC')) AS source_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS source_distinct_league_count,
            countIf(ifNull(league, '') = '') AS source_blank_or_null_league_rows
        FROM poe_trade.v_ps_items_enriched
    ) AS source_stats
    CROSS JOIN (
        SELECT
            count() AS gold_row_count,
            maxOrNull(toDateTime(time_bucket, 'UTC')) AS gold_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS gold_distinct_league_count,
            countIf(ifNull(league, '') = '') AS gold_blank_or_null_league_rows
        FROM poe_trade.gold_liquidity_ref_hour
    ) AS gold_stats

    UNION ALL

    SELECT
        'gold_bulk_premium_hour' AS mart_name,
        'v_ps_items_enriched' AS source_name,
        source_stats.source_row_count,
        source_stats.source_latest_at,
        source_stats.source_distinct_league_count,
        source_stats.source_blank_or_null_league_rows,
        gold_stats.gold_row_count,
        gold_stats.gold_latest_at,
        gold_stats.gold_distinct_league_count,
        gold_stats.gold_blank_or_null_league_rows
    FROM (
        SELECT
            count() AS source_row_count,
            maxOrNull(toDateTime(observed_at, 'UTC')) AS source_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS source_distinct_league_count,
            countIf(ifNull(league, '') = '') AS source_blank_or_null_league_rows
        FROM poe_trade.v_ps_items_enriched
    ) AS source_stats
    CROSS JOIN (
        SELECT
            count() AS gold_row_count,
            maxOrNull(toDateTime(time_bucket, 'UTC')) AS gold_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS gold_distinct_league_count,
            countIf(ifNull(league, '') = '') AS gold_blank_or_null_league_rows
        FROM poe_trade.gold_bulk_premium_hour
    ) AS gold_stats

    UNION ALL

    SELECT
        'gold_set_ref_hour' AS mart_name,
        'v_ps_items_enriched' AS source_name,
        source_stats.source_row_count,
        source_stats.source_latest_at,
        source_stats.source_distinct_league_count,
        source_stats.source_blank_or_null_league_rows,
        gold_stats.gold_row_count,
        gold_stats.gold_latest_at,
        gold_stats.gold_distinct_league_count,
        gold_stats.gold_blank_or_null_league_rows
    FROM (
        SELECT
            count() AS source_row_count,
            maxOrNull(toDateTime(observed_at, 'UTC')) AS source_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS source_distinct_league_count,
            countIf(ifNull(league, '') = '') AS source_blank_or_null_league_rows
        FROM poe_trade.v_ps_items_enriched
    ) AS source_stats
    CROSS JOIN (
        SELECT
            count() AS gold_row_count,
            maxOrNull(toDateTime(time_bucket, 'UTC')) AS gold_latest_at,
            uniqExactIf(league, ifNull(league, '') != '') AS gold_distinct_league_count,
            countIf(ifNull(league, '') = '') AS gold_blank_or_null_league_rows
        FROM poe_trade.gold_set_ref_hour
    ) AS gold_stats
);

GRANT SELECT ON poe_trade.v_gold_mart_diagnostics TO poe_api_reader;
