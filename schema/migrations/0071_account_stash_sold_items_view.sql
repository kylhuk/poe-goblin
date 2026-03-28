CREATE VIEW IF NOT EXISTS poe_trade.v_account_stash_sold_items AS
WITH snapshots AS (
    SELECT
        account_name,
        league,
        realm,
        tab_id AS stash_id,
        observed_at,
        groupUniqArray(item_id) AS item_ids
    FROM poe_trade.silver_account_stash_items
    WHERE item_id != ''
    GROUP BY
        account_name,
        league,
        realm,
        stash_id,
        observed_at
),
diffed AS (
    SELECT
        *,
        leadInFrame(observed_at, 1, observed_at) OVER w AS sold_at,
        leadInFrame(item_ids, 1, item_ids) OVER w AS next_item_ids
    FROM snapshots
    WINDOW w AS (
        PARTITION BY account_name, league, realm, stash_id
        ORDER BY observed_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
)
SELECT
    d.stash_id,
    i.item_id,
    d.sold_at,
    i.listed_price AS price
FROM diffed AS d
ARRAY JOIN d.item_ids AS item_id
INNER JOIN poe_trade.silver_account_stash_items AS i
    ON i.account_name = d.account_name
   AND i.league = d.league
   AND i.realm = d.realm
   AND i.tab_id = d.stash_id
   AND i.observed_at = d.observed_at
   AND i.item_id = item_id
WHERE NOT has(d.next_item_ids, item_id);
