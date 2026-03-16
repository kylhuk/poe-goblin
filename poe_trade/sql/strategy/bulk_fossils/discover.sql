SELECT
    time_bucket AS time_bucket,
    coalesce(realm, '') AS realm,
    coalesce(league, '') AS league,
    concat(category, ':bulk') AS item_or_market_key,
    (coalesce(median_small_price_amount, 0.0) - coalesce(median_bulk_price_amount, 0.0)) * toFloat64(bulk_threshold) AS expected_profit_chaos,
    if(coalesce(median_bulk_price_amount, 0.0) > 0.0, (coalesce(median_small_price_amount, 0.0) - coalesce(median_bulk_price_amount, 0.0)) / coalesce(median_bulk_price_amount, 0.0), 0.0) AS expected_roi,
    least(1.0, toFloat64(bulk_listing_count) / 60.0) AS confidence,
    bulk_listing_count AS sample_count,
    'Bulk fossil spread between bulk and small listings' AS why_it_fired,
    'Acquire bulk fossils as long as small price carries a premium' AS buy_plan,
    'Close trade when small listings compress or bulk price retreats' AS exit_plan,
    '1h' AS expected_hold_time,
    category,
    bulk_threshold,
    bulk_listing_count,
    small_listing_count,
    median_bulk_price_amount,
    median_small_price_amount
FROM poe_trade.gold_bulk_premium_hour
WHERE category = 'fossil';
