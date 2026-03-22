# Search and Low-Investment Outliers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Analytics tab search put exact item names first by default and turn pricing outliers into a low-investment (`<=100c`) opportunity workflow with explicit profit, ROI, and recurrence signals.

**Architecture:** Keep the existing Analytics tab and API routes, but move search relevance and opportunity scoring into `poe_trade/api/ops.py` so both suggestion/history ordering and outlier ranking come from one backend truth. Update the TypeScript contract layer to normalize the nested analytics payloads explicitly, then reshape `AnalyticsTab.tsx` to request the new defaults and render opportunity-first columns and states.

**Tech Stack:** Python 3.11, ClickHouse SQL assembled in `poe_trade.api.ops`, pytest, React, TypeScript, Vitest, Testing Library.

---

## File Structure Map

- Modify: `poe_trade/api/ops.py` - add reusable search relevance SQL/order helpers, implement default name-first search-history behavior, add `max_buy_in` parsing, expand pricing-outlier rows with opportunity metrics, and make weekly aggregation deterministic.
- Modify: `tests/unit/test_api_ops_analytics.py` - add backend tests for search ordering, nested query payload echoes, buy-in clamping, opportunity metrics, and weekly aggregation rules.
- Modify: `frontend/src/types/api.ts` - reconcile `SearchHistoryResponse` and `PricingOutliersResponse` with the backend nested `query` contract and add nullable derived outlier fields.
- Modify: `frontend/src/services/api.ts` - send `max_buy_in`, introduce explicit analytics normalizers, and keep compatibility with partially rolled-out payloads.
- Modify: `frontend/src/services/api.test.ts` - cover query serialization and normalization for search-history and pricing-outliers.
- Create: `frontend/src/components/tabs/AnalyticsTab.test.tsx` - focused panel tests for search defaults, outlier defaults, table rendering, and empty/degraded states.
- Modify: `frontend/src/components/tabs/AnalyticsTab.tsx` - change default search-history sort, adjust panel copy, add `maxBuyIn` state/control, update sort options, and render new opportunity columns and chart messaging.

### Task 1: Lock Down Search Relevance In Backend Tests

**Files:**
- Modify: `tests/unit/test_api_ops_analytics.py`
- Modify: `poe_trade/api/ops.py`

- [ ] **Step 1: Write failing tests for suggestion ordering and search-history defaults**

```python
from poe_trade.api.ops import analytics_search_history, analytics_search_suggestions


def test_analytics_search_suggestions_orders_exact_before_prefix_and_substring() -> None:
    client = _FixtureClickHouse(
        {
            "GROUP BY item_name, item_kind": (
                '{"item_name":"Mageblood","item_kind":"unique_name","match_count":5}\n'
                '{"item_name":"Mageblood Replica","item_kind":"unique_name","match_count":20}\n'
                '{"item_name":"The Mageblood Map","item_kind":"base_type","match_count":30}\n'
            )
        }
    )

    payload = analytics_search_suggestions(client, query="Mageblood")

    assert [row["itemName"] for row in payload["suggestions"]][:3] == [
        "Mageblood",
        "Mageblood Replica",
        "The Mageblood Map",
    ]


def test_analytics_search_suggestions_breaks_same-rank_ties_by_match_count_then_name() -> None:
    client = _FixtureClickHouse(
        {
            "GROUP BY item_name, item_kind": (
                '{"item_name":"Mageblood Replica","item_kind":"unique_name","match_count":20}\n'
                '{"item_name":"Mageblood Reserve","item_kind":"unique_name","match_count":20}\n'
                '{"item_name":"Mageblood Reliquary","item_kind":"unique_name","match_count":10}\n'
            )
        }
    )

    payload = analytics_search_suggestions(client, query="Mageblood R")

    assert [row["itemName"] for row in payload["suggestions"]] == [
        "Mageblood Replica",
        "Mageblood Reserve",
        "Mageblood Reliquary",
    ]


def test_analytics_search_history_returns_nested_query_object_and_name_first_default() -> None:
    client = _FixtureClickHouse(
        {
            "ORDER BY": '{"item_name":"Mageblood","league":"Mirage","listed_price":95.0,"added_on":"2026-03-15 12:00:00"}\n'
        }
    )

    payload = analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": ["item_name"], "order": ["asc"]},
        default_league="Mirage",
    )

    assert payload["query"] == {
        "text": "Mageblood",
        "league": "Mirage",
        "sort": "item_name",
        "order": "asc",
    }


def test_analytics_search_history_orders_exact_prefix_then_substring_for_item_name_sort() -> None:
    client = _FixtureClickHouse(
        {
            "FROM poe_trade.ml_price_dataset_v1": (
                '{"item_name":"Mageblood","league":"Mirage","listed_price":95.0,"added_on":"2026-03-15 12:00:00"}\n'
                '{"item_name":"Mageblood Replica","league":"Mirage","listed_price":90.0,"added_on":"2026-03-15 11:00:00"}\n'
                '{"item_name":"The Mageblood Map","league":"Mirage","listed_price":80.0,"added_on":"2026-03-15 10:00:00"}\n'
            )
        }
    )

    payload = analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": ["item_name"], "order": ["asc"]},
        default_league="Mirage",
    )

    assert [row["itemName"] for row in payload["rows"][:3]] == [
        "Mageblood",
        "Mageblood Replica",
        "The Mageblood Map",
    ]


def test_analytics_search_history_keeps_non_name_sorts_primary() -> None:
    client = _RecordingClickHouse()

    analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": ["added_on"], "order": ["desc"]},
        default_league="Mirage",
    )

    assert any("ORDER BY added_on DESC" in query for query in client.queries)
    assert not any("relevance_rank ASC, added_on" in query for query in client.queries)

    analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": ["item_name"], "order": ["desc"]},
        default_league="Mirage",
    )
    analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": ["listed_price"], "order": ["asc"]},
        default_league="Mirage",
    )
    analytics_search_history(
        client,
        query_params={"query": ["Mageblood"], "sort": ["league"], "order": ["asc"]},
        default_league="Mirage",
    )

    assert any("ORDER BY relevance_rank ASC, item_name DESC, added_on DESC" in query for query in client.queries)
    assert any("ORDER BY listed_price ASC, added_on DESC" in query for query in client.queries)
    assert any("ORDER BY league ASC, added_on DESC" in query for query in client.queries)
```

- [ ] **Step 2: Run tests to verify they fail for the current implementation**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "search_suggestions or search_history" -v`
Expected: FAIL because `poe_trade/api/ops.py` still uses substring/count ordering and current coverage does not enforce the nested/defaulted search contract.

- [ ] **Step 3: Implement reusable search relevance helpers in `poe_trade/api/ops.py`**

```python
def _normalized_query(value: str) -> str:
    return value.strip()


def _search_relevance_sql(label_expr: str, query_text: str) -> str:
    quoted = _quote_sql_string(query_text)
    return (
        "multiIf("
        f"lowerUTF8({label_expr}) = lowerUTF8({quoted}), 0, "
        f"startsWith(lowerUTF8({label_expr}), lowerUTF8({quoted})), 1, "
        f"positionCaseInsensitiveUTF8({label_expr}, {quoted}) > 0, 2, "
        "3)"
    )


def _history_order_sql(sort: str, order: str, *, query_text: str | None = None) -> str:
    if sort == "item_name" and query_text:
        label_expr = _search_item_label_sql()
        direction = "ASC" if order == "asc" else "DESC"
        return f"relevance_rank ASC, item_name {direction}, added_on DESC"
    if sort == "league":
        direction = "ASC" if order == "asc" else "DESC"
        return f"league {direction}, added_on DESC"
    if sort == "listed_price":
        direction = "ASC" if order == "asc" else "DESC"
        return f"listed_price {direction}, added_on DESC"
    return f"added_on {'ASC' if order == 'asc' else 'DESC'}"
```

- [ ] **Step 4: Update search suggestions and history queries to use the helpers**

```python
compact_query = _normalized_query(query)
relevance_sql = _search_relevance_sql(label_expr, compact_query)

rows = _safe_json_rows(
    client,
    " ".join(
        [
            "SELECT",
            f"{label_expr} AS item_name,",
            f"{kind_expr} AS item_kind,",
            f"{relevance_sql} AS relevance_rank,",
            "count() AS match_count",
            "FROM poe_trade.ml_price_dataset_v1",
            "WHERE normalized_price_chaos IS NOT NULL",
            "AND normalized_price_chaos > 0",
            f"AND positionCaseInsensitiveUTF8({label_expr}, {_quote_sql_string(compact_query)}) > 0",
            "GROUP BY item_name, item_kind, relevance_rank",
            "ORDER BY relevance_rank ASC, match_count DESC, item_name ASC",
            f"LIMIT {query_limit} FORMAT JSONEachRow",
        ]
    ),
)

row_rows = _safe_json_rows(
    client,
    " ".join(
        [
            "SELECT",
            f"{label_expr} AS item_name,",
            "league,",
            "normalized_price_chaos AS listed_price,",
            "as_of_ts AS added_on,",
            f"{relevance_sql} AS relevance_rank",
            "FROM poe_trade.ml_price_dataset_v1",
            rows_where,
            f"ORDER BY {_history_order_sql(sort, order, query_text=compact_query)}",
            f"LIMIT {query_limit} FORMAT JSONEachRow",
        ]
    ),
)
```

- [ ] **Step 5: Run the focused backend search tests again**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "search_suggestions or search_history" -v`
Expected: PASS.

- [ ] **Step 6: Commit the search-relevance backend slice**

```bash
git add poe_trade/api/ops.py tests/unit/test_api_ops_analytics.py
git commit -m "feat: rank analytics search results by relevance"
```

### Task 2: Add Opportunity Metrics And Buy-In Filtering In Backend TDD Steps

**Files:**
- Modify: `tests/unit/test_api_ops_analytics.py`
- Modify: `poe_trade/api/ops.py`

- [ ] **Step 1: Write failing tests for outlier defaults, derived fields, and weekly aggregation**

```python
from poe_trade.api.ops import analytics_pricing_outliers


def test_analytics_pricing_outliers_defaults_to_100c_buy_in_and_expected_profit_sort() -> None:
    client = _SequentialFixtureClickHouse([
        '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":1.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.4}\n',
        '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
    ])

    payload = analytics_pricing_outliers(client, query_params={}, default_league="Mirage")

    assert payload["query"] == {
        "query": "",
        "league": "Mirage",
        "sort": "expected_profit",
        "order": "desc",
        "minTotal": 20,
        "maxBuyIn": 100,
        "limit": 100,
    }
    assert payload["rows"][0]["entryPrice"] == pytest.approx(90.0)
    assert payload["rows"][0]["expectedProfit"] == pytest.approx(60.0)
    assert payload["rows"][0]["roi"] == pytest.approx(60.0 / 90.0)


def test_analytics_pricing_outliers_keeps_negative_expected_profit_when_median_is_below_entry() -> None:
    client = _SequentialFixtureClickHouse([
        '{"item_name":"Bad Deal","affix_analyzed":"","p10":120.0,"median":100.0,"p90":140.0,"items_per_week":1.0,"items_total":30,"analysis_level":"item","underpriced_rate":0.125}\n',
        '{"week_start":"2026-03-10 00:00:00","too_cheap_count":1}\n',
    ])

    payload = analytics_pricing_outliers(client, query_params={}, default_league="Mirage")

    assert payload["rows"][0]["expectedProfit"] == pytest.approx(-20.0)
    assert payload["rows"][0]["roi"] == pytest.approx(-20.0 / 120.0)


def test_analytics_pricing_outliers_rounds_underpriced_rate_to_four_decimals() -> None:
    client = _SequentialFixtureClickHouse([
        '{"item_name":"Mageblood","affix_analyzed":"","p10":90.0,"median":150.0,"p90":220.0,"items_per_week":1.5,"items_total":40,"analysis_level":"item","underpriced_rate":0.428571}\n',
        '{"week_start":"2026-03-10 00:00:00","too_cheap_count":2}\n',
    ])

    payload = analytics_pricing_outliers(client, query_params={}, default_league="Mirage")

    assert payload["rows"][0]["underpricedRate"] == pytest.approx(0.4286)


def test_analytics_pricing_outliers_weekly_query_reuses_effective_filters() -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(
        client,
        query_params={"query": ["Mageblood"], "league": ["Mirage"], "min_total": ["25"], "max_buy_in": ["100"]},
        default_league="Mirage",
    )

    assert any("league = 'Mirage'" in query for query in client.queries)
    assert any("HAVING items_total >= 25" in query for query in client.queries)
    assert any("<= 100" in query for query in client.queries)
    assert any("positionCaseInsensitiveUTF8(item_name" in query for query in client.queries)
    assert not any("positionCaseInsensitiveUTF8(affix_analyzed" in query and "week_start" in query for query in client.queries)


def test_analytics_pricing_outliers_clamps_non_numeric_and_out_of_range_buy_in() -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(client, query_params={"max_buy_in": ["nope"]}, default_league="Mirage")
    analytics_pricing_outliers(client, query_params={"max_buy_in": ["0"]}, default_league="Mirage")
    analytics_pricing_outliers(client, query_params={"max_buy_in": ["5001"]}, default_league="Mirage")

    assert any("<= 100" in query for query in client.queries)
    assert any("<= 1" in query for query in client.queries)
    assert any("<= 1000" in query for query in client.queries)
```

- [ ] **Step 2: Run the focused outlier tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "pricing_outliers" -v`
Expected: FAIL because `analytics_pricing_outliers` still defaults to `items_total`, has no `max_buy_in`, and does not emit derived opportunity fields.

- [ ] **Step 3: Add failing tests for sort compatibility, alias handling, and deterministic tie-break ordering**

```python
def test_analytics_pricing_outliers_accepts_new_and_legacy_sort_values() -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(client, query_params={"sort": ["fair_value"]}, default_league="Mirage")
    analytics_pricing_outliers(client, query_params={"sort": ["median"]}, default_league="Mirage")
    analytics_pricing_outliers(client, query_params={"sort": ["p10"]}, default_league="Mirage")

    assert any("ORDER BY median" in query for query in client.queries)
    assert any("ORDER BY p10" in query for query in client.queries)


def test_analytics_pricing_outliers_uses_specified_tie_break_order() -> None:
    client = _RecordingClickHouse()

    analytics_pricing_outliers(client, query_params={}, default_league="Mirage")

    assert any(
        "ORDER BY expected_profit DESC, roi DESC, underpriced_rate DESC, items_total DESC, item_name ASC, affix_analyzed ASC"
        in query
        for query in client.queries
    )
```

- [ ] **Step 4: Run the expanded outlier test slice to verify the new assertions fail**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "pricing_outliers" -v`
Expected: FAIL with missing sort normalization, tie-break ordering, and weekly filter behavior assertions.

- [ ] **Step 5: Add parameter parsing and deterministic sort mapping**

```python
max_buy_in = _query_param_float_with_bounds(
    query_params,
    "max_buy_in",
    default=100.0,
    minimum=1.0,
    maximum=1000.0,
)
sort = _normalize_outlier_sort(_first_query_param(query_params, "sort") or "expected_profit")
order = _normalize_sort_order(_first_query_param(query_params, "order"), default="desc")
```

- [ ] **Step 6: Extend `_normalize_outlier_sort` and `_outlier_order_sql` for new and legacy values**

```python
def _normalize_outlier_sort(raw: str) -> str:
    allowed = {
        "expected_profit",
        "roi",
        "underpriced_rate",
        "entry_price",
        "fair_value",
        "items_per_week",
        "items_total",
        "item_name",
        "affix_analyzed",
        "p10",
        "median",
        "p90",
    }
    return raw if raw in allowed else "expected_profit"


def _outlier_order_sql(sort: str, order: str) -> str:
    if sort == "expected_profit":
        return "expected_profit DESC, roi DESC, underpriced_rate DESC, items_total DESC, item_name ASC, affix_analyzed ASC"
    if sort == "fair_value":
        sort = "median"
    direction = "ASC" if order == "asc" else "DESC"
    if sort == "entry_price":
        return f"entry_price {direction}, item_name ASC, affix_analyzed ASC"
    if sort == "roi":
        return f"roi {direction}, expected_profit DESC, items_total DESC, item_name ASC, affix_analyzed ASC"
    if sort == "underpriced_rate":
        return f"underpriced_rate {direction}, expected_profit DESC, items_total DESC, item_name ASC, affix_analyzed ASC"
    if sort in {"median", "p10", "p90", "items_per_week", "items_total", "item_name", "affix_analyzed"}:
        return f"{sort} {direction}, item_name ASC, affix_analyzed ASC"
    return "expected_profit DESC, roi DESC, underpriced_rate DESC, items_total DESC, item_name ASC, affix_analyzed ASC"
```

- [ ] **Step 7: Extend the outlier SQL and response mapping with derived fields**

```python
"SELECT * FROM ("
"WITH base AS (SELECT {_search_item_label_sql('d')} AS item_name, d.base_type AS base_type, ifNull(d.rarity, '') AS rarity, d.item_id AS item_id, d.as_of_ts AS as_of_ts, toFloat64(d.normalized_price_chaos) AS listed_price FROM poe_trade.ml_price_dataset_v1 AS d WHERE {league_clause} AND d.normalized_price_chaos IS NOT NULL AND d.normalized_price_chaos > 0),"
"item_thresholds AS (SELECT item_name, base_type, rarity, quantileTDigest(0.1)(listed_price) AS p10, quantileTDigest(0.5)(listed_price) AS median, quantileTDigest(0.9)(listed_price) AS p90, count() AS items_total FROM base GROUP BY item_name, base_type, rarity HAVING items_total >= {minimum_support}),"
"item_weekly AS (SELECT t.item_name, t.base_type, t.rarity, toStartOfWeek(b.as_of_ts) AS week_start, countIf(b.listed_price <= t.p10) AS too_cheap_count FROM base AS b INNER JOIN item_thresholds AS t ON b.item_name = t.item_name AND b.base_type = t.base_type AND b.rarity = t.rarity GROUP BY t.item_name, t.base_type, t.rarity, week_start),"
"item_rows AS (SELECT t.item_name AS item_name, '' AS affix_analyzed, t.p10 AS p10, t.median AS median, t.p90 AS p90, round(avg(w.too_cheap_count), 4) AS items_per_week, t.items_total AS items_total, uniq(w.week_start) AS observed_weeks, countIf(w.too_cheap_count > 0) AS cheap_weeks, 'item' AS analysis_level FROM item_thresholds AS t LEFT JOIN item_weekly AS w ON t.item_name = w.item_name AND t.base_type = w.base_type AND t.rarity = w.rarity GROUP BY t.item_name, t.p10, t.median, t.p90, t.items_total),"
"affix_base AS (SELECT b.item_name, b.base_type, b.rarity, b.as_of_ts, b.listed_price, coalesce(nullIf(c.mod_text, ''), nullIf(t.mod_token, '')) AS affix_analyzed FROM base AS b INNER JOIN poe_trade.ml_item_mod_tokens_v1 AS t ON assumeNotNull(b.item_id) = t.item_id AND t.league = {_quote_sql_string(league)} LEFT JOIN poe_trade.ml_mod_catalog_v1 AS c ON c.mod_token = t.mod_token WHERE b.item_id IS NOT NULL),"
"affix_thresholds AS (SELECT item_name, base_type, rarity, affix_analyzed, quantileTDigest(0.1)(listed_price) AS p10, quantileTDigest(0.5)(listed_price) AS median, quantileTDigest(0.9)(listed_price) AS p90, count() AS items_total FROM affix_base WHERE affix_analyzed IS NOT NULL GROUP BY item_name, base_type, rarity, affix_analyzed HAVING items_total >= {minimum_support}),"
"affix_weekly AS (SELECT t.item_name, t.base_type, t.rarity, t.affix_analyzed, toStartOfWeek(a.as_of_ts) AS week_start, countIf(a.listed_price <= t.p10) AS too_cheap_count FROM affix_base AS a INNER JOIN affix_thresholds AS t ON a.item_name = t.item_name AND a.base_type = t.base_type AND a.rarity = t.rarity AND a.affix_analyzed = t.affix_analyzed GROUP BY t.item_name, t.base_type, t.rarity, t.affix_analyzed, week_start),"
"affix_rows AS (SELECT t.item_name AS item_name, t.affix_analyzed AS affix_analyzed, t.p10 AS p10, t.median AS median, t.p90 AS p90, round(avg(w.too_cheap_count), 4) AS items_per_week, t.items_total AS items_total, uniq(w.week_start) AS observed_weeks, countIf(w.too_cheap_count > 0) AS cheap_weeks, 'affix' AS analysis_level FROM affix_thresholds AS t LEFT JOIN affix_weekly AS w ON t.item_name = w.item_name AND t.base_type = w.base_type AND t.rarity = w.rarity AND t.affix_analyzed = w.affix_analyzed GROUP BY t.item_name, t.affix_analyzed, t.p10, t.median, t.p90, t.items_total),"
"table_rows AS (SELECT * FROM item_rows WHERE {item_query_filter} UNION ALL SELECT * FROM affix_rows WHERE {item_or_affix_query_filter}),"
"SELECT item_name, affix_analyzed, p10, median, p90, items_per_week, items_total, analysis_level, observed_weeks, cheap_weeks,"
" p10 AS entry_price,"
" round(median - p10, 4) AS expected_profit,"
" if(p10 > 0, round((median - p10) / p10, 4), null) AS roi,"
" round(toFloat64(cheap_weeks) / nullIf(observed_weeks, 0), 4) AS underpriced_rate"
" FROM table_rows"
") WHERE entry_price <= {max_buy_in} "
f"ORDER BY {_outlier_order_sql(sort, order)} "
```

- [ ] **Step 8: Make weekly aggregation item-level, deduplicated, and independent of sort/limit while reusing effective filters**

```python
item_query_filter = (
    f"positionCaseInsensitiveUTF8(item_name, {_quote_sql_string(query_text)}) > 0"
    if query_text
    else "1"
)

item_or_affix_query_filter = (
    "positionCaseInsensitiveUTF8(item_name, {quoted}) > 0 OR positionCaseInsensitiveUTF8(affix_analyzed, {quoted}) > 0".format(
        quoted=_quote_sql_string(query_text)
    )
    if query_text
    else "1"
)

"filtered_item_rows AS ("
"SELECT DISTINCT item_name, p10, items_total FROM item_rows WHERE {item_query_filter}"
"),"
"weekly_input AS (SELECT item_name, p10 FROM filtered_item_rows WHERE items_total >= {minimum_support} AND p10 <= {max_buy_in}),"
"SELECT toStartOfWeek(b.as_of_ts) AS week_start,"
" countIf(b.listed_price <= f.p10) AS too_cheap_count"
" FROM base AS b"
" INNER JOIN weekly_input AS f ON b.item_name = f.item_name"
" GROUP BY week_start ORDER BY week_start ASC"
```

- [ ] **Step 9: Run the focused outlier tests again**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "pricing_outliers" -v`
Expected: PASS.

- [ ] **Step 10: Commit the backend opportunity slice**

```bash
git add poe_trade/api/ops.py tests/unit/test_api_ops_analytics.py
git commit -m "feat: add low-investment outlier metrics"
```

### Task 3: Reconcile Analytics Types And Add Explicit API Normalizers
- **Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/services/api.test.ts`

- [ ] **Step 1: Write failing client tests for nested analytics payloads and `max_buy_in` serialization**

```typescript
test('serializes analytics pricing outliers max_buy_in and normalizes nested query payload', async () => {
  const fetchMock = vi.fn(() => createResponse({
    query: { query: 'Mageblood', league: 'Mirage', sort: 'expected_profit', order: 'desc', minTotal: 20, maxBuyIn: 100, limit: 100 },
    rows: [{ itemName: 'Mageblood', affixAnalyzed: '', p10: 90, median: 150, p90: 220, itemsPerWeek: 1.5, itemsTotal: 40, analysisLevel: 'item', entryPrice: 90, expectedProfit: 60, roi: 0.6667, underpricedRate: 0.4 }],
    weekly: [],
  }));
  vi.stubGlobal('fetch', fetchMock);

  const result = await api.getAnalyticsPricingOutliers({ query: 'Mageblood', maxBuyIn: 100 });

  const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
  const proxiedUrl = new URL(`https://example.com${(init.headers as Record<string, string>)['x-proxy-path']}`);
  expect(proxiedUrl.searchParams.get('max_buy_in')).toBe('100');
  expect(result.query.maxBuyIn).toBe(100);
  expect(result.rows[0].expectedProfit).toBe(60);
});

test('normalizes nested search-history query payloads', async () => {
  const fetchMock = vi.fn(() => createResponse({
    query: { text: 'Mageblood', league: 'Mirage', sort: 'item_name', order: 'asc' },
    filters: { leagueOptions: ['Mirage'], price: { min: 1, max: 100 }, datetime: { min: null, max: null } },
    histograms: { price: [], datetime: [] },
    rows: [],
  }));
  vi.stubGlobal('fetch', fetchMock);

  const result = await api.getAnalyticsSearchHistory({ query: 'Mageblood' });

  expect(result.query).toEqual({ text: 'Mageblood', league: 'Mirage', sort: 'item_name', order: 'asc' });
});

test('normalizes older pricing outlier payloads without derived fields', async () => {
  const fetchMock = vi.fn(() => createResponse({
    query: { query: 'Mageblood', league: 'Mirage', sort: 'median', order: 'desc', minTotal: 20, maxBuyIn: 100, limit: 100 },
    rows: [{ itemName: 'Mageblood', affixAnalyzed: '', p10: 90, median: 150, p90: 220, itemsPerWeek: 1.5, itemsTotal: 40, analysisLevel: 'item' }],
    weekly: [],
  }));
  vi.stubGlobal('fetch', fetchMock);

  const result = await api.getAnalyticsPricingOutliers({ query: 'Mageblood' });

  expect(result.rows[0].entryPrice).toBeNull();
  expect(result.rows[0].expectedProfit).toBeNull();
  expect(result.rows[0].roi).toBeNull();
  expect(result.rows[0].underpricedRate).toBeNull();
});
```

- [ ] **Step 2: Run the client tests to verify they fail**

Run: `npm --prefix frontend test -- src/services/api.test.ts`
Expected: FAIL because `PricingOutliersRequest` has no `maxBuyIn` field and the analytics helpers still use raw `request<T>` casts without normalizers.

- [ ] **Step 3: Update the analytics TypeScript contracts in `frontend/src/types/api.ts`**

```typescript
export interface SearchHistoryResponse {
  query: { text: string; league: string; sort: string; order: 'asc' | 'desc' };
  filters: {
    leagueOptions: string[];
    price: { min: number; max: number };
    datetime: { min: string | null; max: string | null };
  };
  histograms: {
    price: SearchHistoryPriceBucket[];
    datetime: SearchHistoryDatetimeBucket[];
  };
  rows: SearchHistoryRow[];
}

export interface PricingOutlierRow {
  itemName: string;
  affixAnalyzed: string | null;
  p10: number;
  median: number;
  p90: number;
  itemsPerWeek: number;
  itemsTotal: number;
  analysisLevel: string;
  entryPrice: number | null;
  expectedProfit: number | null;
  roi: number | null;
  underpricedRate: number | null;
}

export interface PricingOutliersResponse {
  query: { query: string; league: string; sort: string; order: 'asc' | 'desc'; minTotal: number; maxBuyIn: number; limit: number };
  rows: PricingOutlierRow[];
  weekly: PricingOutlierWeek[];
}

export interface PricingOutliersRequest {
  query?: string;
  league?: string;
  sort?: string;
  order?: 'asc' | 'desc';
  minTotal?: number;
  maxBuyIn?: number;
  limit?: number;
}
```

- [ ] **Step 4: Add explicit normalizers and request serialization in `frontend/src/services/api.ts`**

```typescript
function normalizeSearchHistoryResponse(payload: unknown): SearchHistoryResponse {
  const source = asObject(payload);
  const query = asObject(source.query);
  const filters = asObject(source.filters);
  const histograms = asObject(source.histograms);
  return {
    query: {
      text: optString(query.text) ?? '',
      league: optString(query.league) ?? '',
      sort: optString(query.sort) ?? 'item_name',
      order: optString(query.order) === 'asc' ? 'asc' : 'desc',
    },
    filters: {
      leagueOptions: Array.isArray(filters.leagueOptions) ? filters.leagueOptions.filter((v): v is string => typeof v === 'string') : [],
      price: normalizePriceRange(asObject(filters.price)),
      datetime: normalizeDatetimeRange(asObject(filters.datetime)),
    },
    histograms: {
      price: normalizePriceBuckets(histograms.price),
      datetime: normalizeDatetimeBuckets(histograms.datetime),
    },
    rows: normalizeSearchHistoryRows(source.rows),
  };
}

function normalizePricingOutliersResponse(payload: unknown): PricingOutliersResponse {
  const source = asObject(payload);
  const query = asObject(source.query);
  return {
    query: {
      query: optString(query.query) ?? '',
      league: optString(query.league) ?? '',
      sort: optString(query.sort) ?? 'expected_profit',
      order: optString(query.order) === 'asc' ? 'asc' : 'desc',
      minTotal: optNumber(query.minTotal) ?? 20,
      maxBuyIn: optNumber(query.maxBuyIn) ?? 100,
      limit: optNumber(query.limit) ?? 100,
    },
    rows: normalizePricingOutlierRows(source.rows),
    weekly: normalizePricingOutlierWeeks(source.weekly),
  };
}

export async function getAnalyticsPricingOutliers(params: PricingOutliersRequest = {}) {
  const queryString = buildQueryString({
    query: params.query,
    league: params.league,
    sort: params.sort,
    order: params.order,
    min_total: params.minTotal,
    max_buy_in: params.maxBuyIn,
    limit: params.limit,
  });
  return normalizePricingOutliersResponse(await request(`/api/v1/ops/analytics/pricing-outliers${queryString}`));
}
```

- [ ] **Step 5: Run the client tests again**

Run: `npm --prefix frontend test -- src/services/api.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit the contract/normalizer slice**

```bash
git add frontend/src/types/api.ts frontend/src/services/api.ts frontend/src/services/api.test.ts
git commit -m "feat: normalize analytics search and outlier payloads"
```

### Task 4: Update SearchHistoryPanel Defaults And Panel Messaging Via Frontend TDD

**Files:**
- Create: `frontend/src/components/tabs/AnalyticsTab.test.tsx`
- Modify: `frontend/src/components/tabs/AnalyticsTab.tsx`

- [ ] **Step 1: Write a failing Analytics tab test for name-first search defaults**

```tsx
test('requests search history with item-name ascending defaults and renders exact-match-first helper copy', async () => {
  getAnalyticsSearchHistoryMock.mockResolvedValueOnce({
    query: { text: 'Mageblood', league: 'Mirage', sort: 'item_name', order: 'asc' },
    filters: { leagueOptions: ['Mirage'], price: { min: 1, max: 100 }, datetime: { min: null, max: null } },
    histograms: { price: [], datetime: [] },
    rows: [{ itemName: 'Mageblood', league: 'Mirage', listedPrice: 95, currency: 'chaos', addedOn: '2026-03-15T12:00:00Z' }],
  });

  render(<AnalyticsTab subtab="search" />);
  fireEvent.change(screen.getByTestId('search-history-input'), { target: { value: 'Mageblood' } });

  await waitFor(() => {
    expect(getAnalyticsSearchHistoryMock).toHaveBeenCalledWith(expect.objectContaining({ sort: 'item_name', order: 'asc' }));
  });

  expect(screen.getByText(/exact item matches first/i)).toBeTruthy();
});
```

- [ ] **Step 2: Run the new Analytics tab test file to verify it fails**

Run: `npm --prefix frontend test -- src/components/tabs/AnalyticsTab.test.tsx`
Expected: FAIL because no dedicated Analytics tab tests exist yet and `SearchHistoryPanel` still defaults to `added_on/desc`.

- [ ] **Step 3: Add a focused `AnalyticsTab.test.tsx` scaffold with mocked API/UI primitives**

```tsx
vi.mock('@/services/api', () => ({
  getAnalyticsSearchSuggestions: getAnalyticsSearchSuggestionsMock,
  getAnalyticsSearchHistory: getAnalyticsSearchHistoryMock,
  getAnalyticsPricingOutliers: getAnalyticsPricingOutliersMock,
  getAnalyticsReport: vi.fn(),
  getRolloutControls: vi.fn(),
  updateRolloutControls: vi.fn(),
}));

vi.mock('../shared/RenderState', () => ({
  RenderState: ({ message }: { message?: string }) => <div>{message}</div>,
}));

vi.mock('../ui/card', () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardTitle: ({ children }: { children: React.ReactNode }) => <h3>{children}</h3>,
}));

test('renders relevance-first suggestions from the backend payload', async () => {
  getAnalyticsSearchSuggestionsMock.mockResolvedValueOnce({
    query: 'Mageblood',
    suggestions: [
      { itemName: 'Mageblood', itemKind: 'unique_name', matchCount: 5 },
      { itemName: 'Mageblood Replica', itemKind: 'unique_name', matchCount: 20 },
    ],
  });

  render(<AnalyticsTab subtab="search" />);
  fireEvent.change(screen.getByTestId('search-history-input'), { target: { value: 'Mageblood' } });

  expect(await screen.findByText('Mageblood')).toBeTruthy();
  expect(screen.getByText('Mageblood Replica')).toBeTruthy();
});
```

- [ ] **Step 4: Change `SearchHistoryPanel` defaults and reset behavior in `AnalyticsTab.tsx`**

```tsx
const [sort, setSort] = useState('item_name');
const [order, setOrder] = useState<'asc' | 'desc'>('asc');

const resetFilters = () => {
  setLeague('');
  setPriceMin(undefined);
  setPriceMax(undefined);
  setCommittedPriceMin(undefined);
  setCommittedPriceMax(undefined);
  setTimeFrom(undefined);
  setTimeTo(undefined);
  setCommittedTimeFrom(undefined);
  setCommittedTimeTo(undefined);
  setSort('item_name');
  setOrder('asc');
};
```

- [ ] **Step 5: Update copy and empty-state wording, then rerun the full Analytics tab test file**

Run: `npm --prefix frontend test -- src/components/tabs/AnalyticsTab.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit the search-panel frontend slice**

```bash
git add frontend/src/components/tabs/AnalyticsTab.tsx frontend/src/components/tabs/AnalyticsTab.test.tsx
git commit -m "feat: default analytics search to exact-match ordering"
```

### Task 5: Rework The Outliers Panel Into A Low-Investment Opportunity View

**Files:**
- Modify: `frontend/src/components/tabs/AnalyticsTab.tsx`
- Modify: `frontend/src/components/tabs/AnalyticsTab.test.tsx`

- [ ] **Step 1: Add failing tests for outlier defaults, opportunity columns, and affix-only weekly empty messaging**

```tsx
test('requests low-investment outliers with expected-profit sorting and renders opportunity columns', async () => {
  getAnalyticsPricingOutliersMock.mockResolvedValueOnce({
    query: { query: 'Mageblood', league: 'Mirage', sort: 'expected_profit', order: 'desc', minTotal: 25, maxBuyIn: 100, limit: 100 },
    rows: [{ itemName: 'Mageblood', affixAnalyzed: null, p10: 90, median: 150, p90: 220, itemsPerWeek: 1.5, itemsTotal: 40, analysisLevel: 'item', entryPrice: 90, expectedProfit: 60, roi: 0.6667, underpricedRate: 0.4 }],
    weekly: [],
  });

  render(<AnalyticsTab subtab="outliers" />);

  await waitFor(() => {
    expect(getAnalyticsPricingOutliersMock).toHaveBeenCalledWith(expect.objectContaining({ sort: 'expected_profit', order: 'desc', maxBuyIn: 100 }));
  });

  expect(screen.getByText('Low-Investment Flip Opportunities')).toBeTruthy();
  expect(screen.getByText('Expected Profit')).toBeTruthy();
  expect(screen.getByText('ROI')).toBeTruthy();
  expect(screen.getByText(/weekly trend is available for item-name matches only/i)).toBeTruthy();
});

test('renders required low-investment sort controls', async () => {
  getAnalyticsPricingOutliersMock.mockResolvedValueOnce({
    query: { query: '', league: 'Mirage', sort: 'expected_profit', order: 'desc', minTotal: 25, maxBuyIn: 100, limit: 100 },
    rows: [],
    weekly: [],
  });

  render(<AnalyticsTab subtab="outliers" />);

  expect(await screen.findByRole('option', { name: /expected profit/i })).toBeTruthy();
  expect(screen.getByRole('option', { name: /roi/i })).toBeTruthy();
  expect(screen.getByRole('option', { name: /underpriced rate/i })).toBeTruthy();
  expect(screen.getByRole('option', { name: /items total/i })).toBeTruthy();
  expect(screen.getByRole('option', { name: /item name/i })).toBeTruthy();
});

test('shows empty state when no cheap opportunities are returned under the current cap', async () => {
  getAnalyticsPricingOutliersMock.mockResolvedValueOnce({
    query: { query: '', league: 'Mirage', sort: 'expected_profit', order: 'desc', minTotal: 25, maxBuyIn: 100, limit: 100 },
    rows: [],
    weekly: [],
  });

  render(<AnalyticsTab subtab="outliers" />);

  expect(await screen.findByText(/no cheap opportunities found under the current cap/i)).toBeTruthy();
});

test('shows degraded state when the outlier request fails', async () => {
  getAnalyticsPricingOutliersMock.mockRejectedValueOnce(new Error('pricing offline'));

  render(<AnalyticsTab subtab="outliers" />);

  expect(await screen.findByText('pricing offline')).toBeTruthy();
});

test('shows degraded state when derived opportunity fields are missing from returned rows', async () => {
  getAnalyticsPricingOutliersMock.mockResolvedValueOnce({
    query: { query: '', league: 'Mirage', sort: 'expected_profit', order: 'desc', minTotal: 25, maxBuyIn: 100, limit: 100 },
    rows: [{ itemName: 'Mageblood', affixAnalyzed: null, p10: 90, median: 150, p90: 220, itemsPerWeek: 1.5, itemsTotal: 40, analysisLevel: 'item', entryPrice: null, expectedProfit: null, roi: null, underpricedRate: null }],
    weekly: [],
  });

  render(<AnalyticsTab subtab="outliers" />);

  expect(await screen.findByText(/missing opportunity metrics/i)).toBeTruthy();
});
```

- [ ] **Step 2: Run the outlier-focused Analytics tests to verify they fail**

Run: `npm --prefix frontend test -- src/components/tabs/AnalyticsTab.test.tsx`
Expected: FAIL because `PricingOutliersPanel` still requests `items_total`, has no `maxBuyIn`, and renders percentile-first columns only.

- [ ] **Step 3: Add `maxBuyIn` state/control and new default sort in `AnalyticsTab.tsx`**

```tsx
const [sort, setSort] = useState('expected_profit');
const [order, setOrder] = useState<'asc' | 'desc'>('desc');
const [maxBuyIn, setMaxBuyIn] = useState(100);

getAnalyticsPricingOutliers({
  query: query.trim() || undefined,
  league: league.trim() || undefined,
  sort,
  order,
  minTotal,
  maxBuyIn,
  limit: 100,
})
```

- [ ] **Step 4: Replace the percentile-first table columns with opportunity-first columns**

```tsx
<TableHead>Buy-In</TableHead>
<TableHead>Fair Value</TableHead>
<TableHead>Expected Profit</TableHead>
<TableHead>ROI</TableHead>
<TableHead>Underpriced Rate</TableHead>
<TableHead>Items/wk</TableHead>
<TableHead>Items total</TableHead>
```

- [ ] **Step 5: Render chart/table empty states for affix-only searches and no-opportunity cases**

```tsx
if (data.rows.some(row => row.entryPrice == null || row.expectedProfit == null || row.roi == null || row.underpricedRate == null)) {
  return <RenderState kind="degraded" message="Missing opportunity metrics from analytics backend." />;
}

{data.weekly.length === 0 ? (
  <p className="text-xs text-muted-foreground">Weekly trend is available for item-name matches only.</p>
) : (
  <MiniHistogram dataTestId="pricing-outliers-weekly-chart" title="Too cheap per week" buckets={weeklyBuckets} formatLabel={value => formatShortDate(String(value))} />
)}
```

- [ ] **Step 6: Run the full Analytics tab test file**

Run: `npm --prefix frontend test -- src/components/tabs/AnalyticsTab.test.tsx`
Expected: PASS.

- [ ] **Step 7: Run the combined frontend verification slice**

Run: `npm --prefix frontend test -- src/services/api.test.ts src/components/tabs/AnalyticsTab.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit the outlier-panel frontend slice**

```bash
git add frontend/src/components/tabs/AnalyticsTab.tsx frontend/src/components/tabs/AnalyticsTab.test.tsx
git commit -m "feat: surface low-investment pricing opportunities"
```

### Task 6: Final Verification

**Files:**
- Modify: none

- [ ] **Step 1: Run backend analytics tests**

Run: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -v`
Expected: PASS.

- [ ] **Step 2: Run frontend analytics tests**

Run: `npm --prefix frontend test -- src/services/api.test.ts src/components/tabs/AnalyticsTab.test.tsx`
Expected: PASS.

- [ ] **Step 3: Run a frontend build to catch TS/JSX contract drift**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 4: Run the broader unit suite most likely to catch contract drift**

Run: `.venv/bin/pytest tests/unit/test_api_ops_routes.py tests/unit/test_api_ops_analytics.py -v`
Expected: PASS.

- [ ] **Step 5: Record any follow-up mismatches before wider execution**

```text
If route tests or frontend type checks expose additional analytics contract drift, fix those issues before expanding scope.
```
