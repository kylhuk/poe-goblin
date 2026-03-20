CREATE TABLE IF NOT EXISTS poe_trade.ml_item_mod_features_sql_stage_v1 (
    league String,
    item_id String,
    hour_ts DateTime64(3, 'UTC'),
    mod_count UInt64,
    max_as_of_ts DateTime64(3, 'UTC'),
    strength_value Float64,
    dexterity_value Float64,
    intelligence_value Float64,
    maximumlife_value Float64,
    maximummana_value Float64,
    maximumenergyshield_value Float64,
    evasionrating_value Float64,
    armor_value Float64,
    movementspeed_value Float64,
    criticalstrikechance_value Float64,
    criticalstrikemultiplier_value Float64,
    attackspeed_value Float64,
    castspeed_value Float64,
    physicaldamage_value Float64,
    firedamage_value Float64,
    colddamage_value Float64,
    lightningdamage_value Float64,
    chaosdamage_value Float64,
    elementaldamage_value Float64,
    spelldamage_value Float64,
    fireresistance_value Float64,
    coldresistance_value Float64,
    lightningresistance_value Float64,
    chaosresistance_value Float64,
    allelementalresistances_value Float64
) ENGINE = ReplacingMergeTree(max_as_of_ts)
ORDER BY (league, item_id, hour_ts);

ALTER TABLE poe_trade.ml_item_mod_features_sql_stage_v1
    ADD COLUMN IF NOT EXISTS hour_ts DateTime64(3, 'UTC') AFTER item_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_ml_item_mod_features_sql_stage_v1
TO poe_trade.ml_item_mod_features_sql_stage_v1 AS
SELECT
    league,
    item_id,
    toStartOfHour(as_of_ts) AS hour_ts,
    count() AS mod_count,
    max(as_of_ts) AS max_as_of_ts,
    maxIf(primary_numeric, position(token, 'to strength') > 0 OR position(token, 'all attributes') > 0) AS strength_value,
    maxIf(primary_numeric, position(token, 'to dexterity') > 0 OR position(token, 'all attributes') > 0) AS dexterity_value,
    maxIf(primary_numeric, position(token, 'to intelligence') > 0 OR position(token, 'all attributes') > 0) AS intelligence_value,
    maxIf(primary_numeric, position(token, 'maximum life') > 0 OR position(token, 'to life') > 0) AS maximumlife_value,
    maxIf(primary_numeric, position(token, 'maximum mana') > 0 OR position(token, 'to mana') > 0) AS maximummana_value,
    maxIf(primary_numeric, position(token, 'maximum energy shield') > 0 OR position(token, 'energy shield') > 0) AS maximumenergyshield_value,
    maxIf(primary_numeric, position(token, 'evasion') > 0) AS evasionrating_value,
    maxIf(primary_numeric, position(token, 'armor') > 0 OR position(token, 'armour') > 0) AS armor_value,
    maxIf(primary_numeric, position(token, 'movement speed') > 0) AS movementspeed_value,
    maxIf(primary_numeric, position(token, 'critical strike chance') > 0) AS criticalstrikechance_value,
    maxIf(primary_numeric, position(token, 'critical strike multiplier') > 0) AS criticalstrikemultiplier_value,
    maxIf(primary_numeric, position(token, 'attack speed') > 0 OR position(token, 'attack and cast speed') > 0) AS attackspeed_value,
    maxIf(primary_numeric, position(token, 'cast speed') > 0 OR position(token, 'attack and cast speed') > 0) AS castspeed_value,
    maxIf(if(physical_added_value > 0., physical_added_value, primary_numeric), position(token, 'physical damage') > 0) AS physicaldamage_value,
    maxIf(if(fire_added_value > 0., fire_added_value, primary_numeric), position(token, 'fire damage') > 0) AS firedamage_value,
    maxIf(if(cold_added_value > 0., cold_added_value, primary_numeric), position(token, 'cold damage') > 0) AS colddamage_value,
    maxIf(if(lightning_added_value > 0., lightning_added_value, primary_numeric), position(token, 'lightning damage') > 0) AS lightningdamage_value,
    maxIf(if(chaos_added_value > 0., chaos_added_value, primary_numeric), position(token, 'chaos damage') > 0) AS chaosdamage_value,
    maxIf(primary_numeric, position(token, 'elemental damage') > 0) AS elementaldamage_value,
    maxIf(primary_numeric, position(token, 'spell damage') > 0) AS spelldamage_value,
    maxIf(primary_numeric, position(token, 'fire resistance') > 0) AS fireresistance_value,
    maxIf(primary_numeric, position(token, 'cold resistance') > 0) AS coldresistance_value,
    maxIf(primary_numeric, position(token, 'lightning resistance') > 0) AS lightningresistance_value,
    maxIf(primary_numeric, position(token, 'chaos resistance') > 0) AS chaosresistance_value,
    maxIf(primary_numeric, position(token, 'all elemental resistances') > 0 OR position(token, 'to all elemental resistances') > 0) AS allelementalresistances_value
FROM (
    SELECT
        league,
        item_id,
        as_of_ts,
        replaceRegexpAll(
            replaceRegexpAll(
                replaceAll(lowerUTF8(trimBoth(mod_token)), '\"', '"'),
                '^"|"$',
                ''
            ),
            '\\s+',
            ' '
        ) AS token,
        if(
            toFloat64OrZero(extract(token, '(?:^|\\s)[+-]?(\\d+(?:\\.\\d+)?)\\s*%?')) > 0.,
            toFloat64OrZero(extract(token, '(?:^|\\s)[+-]?(\\d+(?:\\.\\d+)?)\\s*%?')),
            if(
                empty(extractAll(token, '\\d+(?:\\.\\d+)?')),
                0.,
                arrayReduce('max', arrayMap(x -> toFloat64OrZero(x), extractAll(token, '\\d+(?:\\.\\d+)?')))
            )
        ) AS primary_numeric,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+physical\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+physical\\s+damage'))
        ) AS physical_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+fire\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+fire\\s+damage'))
        ) AS fire_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+cold\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+cold\\s+damage'))
        ) AS cold_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+lightning\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+lightning\\s+damage'))
        ) AS lightning_added_value,
        greatest(
            toFloat64OrZero(extract(token, 'adds\\s+(\\d+(?:\\.\\d+)?)\\s+to\\s+\\d+(?:\\.\\d+)?\\s+chaos\\s+damage')),
            toFloat64OrZero(extract(token, 'adds\\s+\\d+(?:\\.\\d+)?\\s+to\\s+(\\d+(?:\\.\\d+)?)\\s+chaos\\s+damage'))
        ) AS chaos_added_value
    FROM poe_trade.ml_item_mod_tokens_v1
) raw
WHERE
    position(token, 'to strength') > 0
    OR position(token, 'all attributes') > 0
    OR position(token, 'to dexterity') > 0
    OR position(token, 'to intelligence') > 0
    OR position(token, 'maximum life') > 0
    OR position(token, 'to life') > 0
    OR position(token, 'maximum mana') > 0
    OR position(token, 'to mana') > 0
    OR position(token, 'maximum energy shield') > 0
    OR position(token, 'energy shield') > 0
    OR position(token, 'evasion') > 0
    OR position(token, 'armor') > 0
    OR position(token, 'armour') > 0
    OR position(token, 'movement speed') > 0
    OR position(token, 'critical strike chance') > 0
    OR position(token, 'critical strike multiplier') > 0
    OR position(token, 'attack speed') > 0
    OR position(token, 'attack and cast speed') > 0
    OR position(token, 'cast speed') > 0
    OR position(token, 'physical damage') > 0
    OR position(token, 'fire damage') > 0
    OR position(token, 'cold damage') > 0
    OR position(token, 'lightning damage') > 0
    OR position(token, 'chaos damage') > 0
    OR position(token, 'elemental damage') > 0
    OR position(token, 'spell damage') > 0
    OR position(token, 'fire resistance') > 0
    OR position(token, 'cold resistance') > 0
    OR position(token, 'lightning resistance') > 0
    OR position(token, 'chaos resistance') > 0
    OR position(token, 'all elemental resistances') > 0
    OR position(token, 'to all elemental resistances') > 0
GROUP BY league, item_id, hour_ts;
