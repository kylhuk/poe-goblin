DROP VIEW IF EXISTS poe_trade.v_account_stash_sold_items;

CREATE VIEW poe_trade.v_account_stash_sold_items AS
WITH snapshots AS (
    SELECT
        t.account_name,
        t.league,
        t.realm,
        t.tab_id AS stash_id,
        t.scan_id,
        t.captured_at AS observed_at,
        groupUniqArray(v.item_id) AS item_ids
    FROM poe_trade.account_stash_scan_tabs AS t
    INNER JOIN poe_trade.account_stash_item_valuations AS v
        ON v.scan_id = t.scan_id
       AND v.account_name = t.account_name
       AND v.league = t.league
       AND v.realm = t.realm
       AND v.tab_id = t.tab_id
    GROUP BY
        t.account_name,
        t.league,
        t.realm,
        stash_id,
        t.scan_id,
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
    item_id,
    d.sold_at,
    i.listed_price AS price
FROM diffed AS d
ARRAY JOIN d.item_ids AS item_id
INNER JOIN poe_trade.account_stash_item_valuations AS i
    ON i.scan_id = d.scan_id
   AND i.account_name = d.account_name
   AND i.league = d.league
   AND i.realm = d.realm
   AND i.tab_id = d.stash_id
   AND i.item_id = item_id
WHERE d.sold_at IS NOT NULL
  AND NOT has(d.next_item_ids, item_id)
  AND i.listed_price IS NOT NULL;
