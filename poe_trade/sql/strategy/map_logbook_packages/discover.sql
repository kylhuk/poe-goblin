SELECT
    toDateTime(time_bucket) AS time_bucket,
    realm,
    coalesce(league, '') AS league,
    concat(category, ':set') AS item_or_market_key,
    category,
    distinct_base_types,
    listing_count,
    listing_count AS sample_count,
    toFloat64(listing_count) * 0.06 AS expected_profit_chaos,
    if(distinct_base_types > 0, toFloat64(listing_count) / toFloat64(distinct_base_types), 0.0) AS expected_roi,
    least(1.0, toFloat64(distinct_base_types) / 20.0) AS confidence,
    'Map/logbook package depth stays scarce across base types' AS why_it_fired,
    'Buy map/logbook bundles before coverage expands' AS buy_plan,
    'Exit once distinct base breadth surpasses 20 or listing depth rebounds' AS exit_plan,
    updated_at
FROM poe_trade.gold_set_ref_hour
WHERE category IN ('map', 'logbook');
