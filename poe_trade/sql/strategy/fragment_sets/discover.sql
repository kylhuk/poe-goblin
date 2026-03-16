SELECT
    toDateTime(time_bucket) AS time_bucket,
    realm,
    coalesce(league, '') AS league,
    concat(category, ':set') AS item_or_market_key,
    category,
    distinct_base_types,
    listing_count,
    listing_count AS sample_count,
    toFloat64(listing_count) * 0.05 AS expected_profit_chaos,
    if(distinct_base_types > 0, toFloat64(listing_count) / toFloat64(distinct_base_types), 0.0) AS expected_roi,
    least(1.0, toFloat64(distinct_base_types) / 30.0) AS confidence,
    'Fragment set supply remains limited relative to listing depth' AS why_it_fired,
    'Build fragment inventories while base type breadth stays below 30' AS buy_plan,
    'Exit when distinct base coverage expands or listing depth normalizes' AS exit_plan,
    updated_at
FROM poe_trade.gold_set_ref_hour
WHERE category = 'other';
