SELECT
    time_bucket AS time_bucket,
    coalesce(realm, '') AS realm,
    coalesce(league, '') AS league,
    concat(category, ':reroll') AS item_or_market_key,
    concat(category, ':reroll') AS semantic_key,
    (coalesce(median_small_price_amount, 0.0) - coalesce(median_bulk_price_amount, 0.0)) * toFloat64(bulk_threshold) AS expected_profit_chaos,
    if(coalesce(median_bulk_price_amount, 0.0) > 0.0, (coalesce(median_small_price_amount, 0.0) - coalesce(median_bulk_price_amount, 0.0)) / coalesce(median_bulk_price_amount, 0.0), 0.0) AS expected_roi,
    least(1.0, toFloat64(bulk_listing_count) / 50.0) AS confidence,
    bulk_listing_count AS sample_count,
    'Scarab reroll spread between bulk and small lots' AS why_it_fired,
    'Buy bulk scarabs to reroll while small price premium stays wide' AS buy_plan,
    'Add to reroll queue until small listings compress under the reroll budget' AS transform_plan,
    'Exit when rerolled scarabs trade near bulk threshold or bulk price drops' AS exit_plan,
    '1.5h' AS expected_hold_time,
    category,
    bulk_threshold,
    bulk_listing_count,
    small_listing_count,
    median_bulk_price_amount,
    median_small_price_amount
FROM poe_trade.gold_bulk_premium_hour
WHERE category = 'scarab';
