# Search and Low-Investment Outliers Design

## Goal

Fix the Analytics tab's item search so exact item names rank first, and reshape pricing outlier analytics into an actionable low-investment flip view that highlights items commonly underpriced by newer players with a default buy-in cap of `100c`.

## Problem Statement

The current Analytics tab already exposes:

- search suggestions from `analytics_search_suggestions`,
- historical listing search from `analytics_search_history`,
- percentile-based outlier analytics from `analytics_pricing_outliers`.

It does not yet reliably answer the actual operator question:

- "when I search for an item, show me the right item first,"
- "show me cheap items worth buying, not just percentile summaries,"
- "surface items that are regularly underpriced,"
- "keep the analysis focused on low-risk, low-investment flips."

Today the search endpoints use substring matching with simple count-based ordering, and the outlier panel is dominated by descriptive percentile columns such as `p10`, `median`, `p90`, and `items_total`. That is useful as raw research output, but it is not a good trading workflow for finding `<=100c` opportunities with strong upside.

## User-Facing Outcome

From the existing Analytics tab, the user should be able to:

1. type an item such as `Mageblood` and see exact matches before broader partial matches,
2. inspect listing history for the intended item without unrelated names crowding the top of the results,
3. switch to the outlier view and immediately see low-investment opportunities ranked by actionable value,
4. understand buy-in, fair value, expected profit, ROI, and how often the item gets listed too cheaply,
5. keep the experience scoped to cheap flips by default with a `100c` max buy-in ceiling.

## Non-Goals

- replacing the Analytics tab with a new standalone route,
- building a general recommendation engine outside the current analytics endpoints,
- introducing a live trade API integration or real-time alerting workflow,
- redefining the single-item price-check contract,
- adding cross-tab search behavior outside the existing Analytics search and outlier panels.

## Design Overview

The design keeps the current Analytics tab structure and improves the two existing flows that already exist in `frontend/src/components/tabs/AnalyticsTab.tsx`.

1. Search relevance moves from naive substring ordering to explicit relevance ranking: exact label match, then prefix match, then broader substring match.
2. Pricing outliers move from raw percentile summaries to opportunity-oriented rows built around cheap-entry thresholds.
3. The backend remains the source of truth for relevance and opportunity scoring so the frontend only renders shaped results and lightweight controls.

This avoids frontend-only heuristics that would drift from the actual data model and keeps the behavior consistent across search suggestions, listing history, and outlier analytics.

## Existing Foundations To Reuse

- `poe_trade/api/ops.py` already owns `analytics_search_suggestions`, `analytics_search_history`, and `analytics_pricing_outliers`.
- `frontend/src/components/tabs/AnalyticsTab.tsx` already contains `SearchHistoryPanel` and `PricingOutliersPanel`.
- `frontend/src/services/api.ts` already serializes analytics query params; `search-history` and `pricing-outliers` still need explicit response normalizers.
- `frontend/src/types/api.ts` already defines the search and outlier contracts.
- the existing `ml_price_dataset_v1`, `ml_item_mod_tokens_v1`, and `ml_mod_catalog_v1` queries already provide the historical price and affix data needed for this feature.

## Architecture

### 1. Search Relevance Model

Both search suggestions and search-history rows should use the same relevance model for the user-entered query text.

For a normalized query string trimmed of leading and trailing whitespace:

- rank `0`: exact item-label match,
- rank `1`: prefix match,
- rank `2`: substring match,
- tie-breakers: stronger support counts first, then stable alphabetical ordering.

The label expression remains the existing unique-name-or-base-type expression so unique items still rank by unique name while normal items rank by base type.

The matching rule should remain case-insensitive, but the ordering should no longer allow a high-volume substring match to outrank an exact search intent.

### 2. Search Suggestions

`analytics_search_suggestions` should continue to return lightweight suggestion rows, but ordering should be driven by relevance first and `match_count` second.

Returned fields can stay small:

- `itemName`,
- `itemKind`,
- `matchCount`.

The key fix is query semantics, not a larger payload. The frontend can keep its current datalist and suggestion-chip rendering once the ordering is correct.

### 3. Search History

`analytics_search_history` should continue to provide filters, histograms, and result rows, but row ordering should preserve search intent only where that does not conflict with an explicit operator sort.

The frontend default search-history request should change from time-first sorting to `sort=item_name` and `order=asc` so the default experience puts the intended item first.

The history endpoint should:

- keep existing league, time, and price filters,
- preserve histogram behavior,
- order exact matches ahead of broader matches for the `item_name` sort,
- avoid returning misleading top rows for a highly specific query.

Ordering rules should be explicit:

- `item_name` with `order=asc`: order by relevance rank, then `item_name ASC`, then `added_on DESC`,
- `item_name` with `order=desc`: order by relevance rank, then `item_name DESC`, then `added_on DESC`,
- `added_on`: keep `added_on` as the primary sort and do not prepend relevance,
- `listed_price`: keep `listed_price` as the primary sort and do not prepend relevance,
- `league`: keep `league` as the primary sort and do not prepend relevance.

This preserves exact-match intent for name-oriented browsing without surprising the user when they deliberately sort by price or time.

### 4. Low-Investment Opportunity Model

`analytics_pricing_outliers` should shift from a pure percentile summary to a low-investment flip opportunity view.

The new default interpretation is:

- entry threshold is bounded by a `max_buy_in` query param defaulting to `100`,
- a row is only actionable if its cheap-entry threshold is at or below that cap,
- ranking should follow a deterministic opportunity sort.

The intent is not merely to show items with low percentiles. It is to show items where low entry cost combines with enough historical underpricing to be worth attention.

### 5. Opportunity Metrics

Each outlier row should include fields that answer "should I buy this under 100c?"

Recommended fields:

- `itemName`,
- `affixAnalyzed`,
- `analysisLevel`,
- `entryPrice` - defined as the row's raw `p10` value in chaos; filtering and derived metrics use the raw value, while the response may round it to two decimals for display stability,
- `expectedProfit` - `median - entryPrice`,
- `roi` - `expectedProfit / entryPrice` when `entryPrice > 0`,
- `underpricedRate` - `count(distinct weeks with at least one listing <= p10) / count(distinct observed weeks for the cohort)`, rounded to four decimals,
- `itemsPerWeek`,
- `itemsTotal`,
- `p10`, `p90` as secondary context if still useful.

These metrics should be computed in the backend query so the frontend receives a stable contract and does not invent its own financial logic.

Filtering rules should also be explicit:

- `entryPrice` is the same as `p10` for both item-level and affix-level rows,
- actionable rows must satisfy `entryPrice <= max_buy_in`,
- actionable rows must satisfy the existing `min_total` support threshold,
- no additional hidden recurrence gate is applied in v1 of this design.

Default ranking should be:

- primary: `expectedProfit DESC`,
- tie-break 1: `roi DESC`,
- tie-break 2: `underpricedRate DESC`,
- tie-break 3: `itemsTotal DESC`,
- tie-break 4: `itemName ASC`, `affixAnalyzed ASC`.

Supported sort values should include at least:

- `expected_profit`,
- `roi`,
- `underpriced_rate`,
- `entry_price`,
- `fair_value` as an alias for sorting by `median`,
- `items_per_week`,
- `items_total`,
- `item_name`.

### 6. Affix vs Item-Level Rows

The current outlier flow already emits both item-level and affix-level rows. That should remain because many useful flips come from specific modifiers rather than the whole base item.

However, the new ranking should treat the two row types consistently:

- item-level rows represent whole-item cheap-entry opportunities,
- affix-level rows represent modifier-scoped opportunities where the historical spread is meaningful,
- both rows are filtered through the same `max_buy_in` ceiling and minimum support controls.

The frontend should continue to label the analysis scope clearly so users can tell whether they are looking at a broad base-item opportunity or a mod-specific one.

## API Design

### `GET /api/v1/ops/analytics/search-suggestions`

No route change.

Behavior changes:

- exact matches rank before prefix matches,
- prefix matches rank before broader substrings,
- support count remains a tie-breaker rather than the primary ordering rule.

### `GET /api/v1/ops/analytics/search-history`

No route change.

Behavior changes:

- item relevance is incorporated into row ordering when applicable,
- existing filter and histogram shape stays intact,
- query results better reflect exact item intent.

Response shape remains:

- `query`,
- `filters`,
- `histograms`,
- `rows`.

Frontend contract target:

- `SearchHistoryResponse.query` is an object with `text`, `league`, `sort`, and `order`,
- omitting `limit` from `SearchHistoryResponse.query` is intentional so the frontend treats row count as a request concern rather than a persisted analytics filter,
- `SearchHistoryResponse.filters` keeps `leagueOptions`, `price`, and `datetime`,
- `SearchHistoryResponse.histograms` keeps `price` and `datetime`,
- `SearchHistoryResponse.rows` keeps `itemName`, `league`, `listedPrice`, `currency`, and `addedOn`.

### `GET /api/v1/ops/analytics/pricing-outliers`

Add or rename parameters to make the opportunity contract explicit:

- `query` - optional text filter; row queries may match item labels or affix text, while weekly queries match item labels only,
- `league` - existing league filter,
- `sort` - include opportunity-oriented fields such as `expected_profit`, `roi`, `underpriced_rate`, `entry_price`,
- `order` - existing direction control,
- `min_total` - existing minimum support control,
- `max_buy_in` - new, defaults to `100`; non-numeric input falls back to `100`, numeric input below `1` clamps to `1`, and numeric input above `1000` clamps to `1000`,
- `limit` - existing row cap.

Response shape should evolve from pure percentile rows to opportunity rows.

Compatibility rules should be explicit:

- continue accepting the existing sort values `items_total`, `items_per_week`, `p10`, `median`, `p90`, `item_name`, and `affix_analyzed` during rollout,
- new sort values are additive rather than replacing the old ones,
- keep existing percentile fields `p10`, `median`, `p90`, `itemsPerWeek`, `itemsTotal`, `analysisLevel`, and `affixAnalyzed`,
- add `entryPrice`, `expectedProfit`, `roi`, and `underpricedRate`,
- preserve the top-level response shape as `{ query, rows, weekly }`,
- frontend normalization in `frontend/src/services/api.ts` should treat missing new derived fields as `null` for `entryPrice`, `expectedProfit`, `roi`, and `underpricedRate`,
- existing percentile/support fields continue to normalize as zero-compatible numeric fields the same way they do today,
- `frontend/src/types/api.ts` should be updated to represent the expanded row contract rather than replacing the old shape outright.

Example top-level response fields:

- `query` with the exact effective fields `query`, `league`, `sort`, `order`, `minTotal`, `maxBuyIn`, and `limit`,
- `rows` as actionable opportunity rows,
- `weekly` as historical too-cheap counts over time.

Frontend contract target:

- `PricingOutliersResponse.query` is an object with `query`, `league`, `sort`, `order`, `minTotal`, `maxBuyIn`, and `limit`,
- `PricingOutliersResponse.rows` contains `PricingOutlierRow[]`,
- `PricingOutliersResponse.weekly` contains weekly item-level too-cheap buckets,
- `PricingOutlierRow` keeps current fields `itemName`, `affixAnalyzed`, `p10`, `median`, `p90`, `itemsPerWeek`, `itemsTotal`, `analysisLevel` and adds nullable `entryPrice`, `expectedProfit`, `roi`, and `underpricedRate`.

Implementation requirement:

- `frontend/src/services/api.ts` should introduce explicit normalizers for `search-history` and `pricing-outliers` instead of relying on raw `request<T>` casting.
- `frontend/src/types/api.ts` must be reconciled to the nested `query` payloads already returned by `analytics_search_history` and `analytics_pricing_outliers`.

## Frontend Design

### 1. Search History Panel

`SearchHistoryPanel` remains in place, but the copy should emphasize that suggestions and history now prioritize exact item matches first.

The panel should keep:

- the existing item search input,
- league filter,
- price and time sliders,
- histograms,
- historical rows table.

The key user-visible change is better ranking and more trustworthy search behavior, not a new layout.

### 2. Outliers Panel

`PricingOutliersPanel` should be reframed as a low-investment opportunity view rather than a generic percentile dump.

Recommended UI changes:

- rename the panel copy toward "Low-Investment Flip Opportunities" or equivalent,
- update the search control copy so it clearly says item or affix filter,
- default the buy-in control to `100c`,
- default the initial request to `sort=expected_profit`, `order=desc`, and `max_buy_in=100`,
- lead the table with actionable columns such as buy-in, fair value (rendered from `median`), profit, ROI, and underpriced frequency,
- keep sample size and analysis scope visible,
- relegate raw percentile context to secondary columns or helper copy,
- expose sort controls for at least `expected_profit`, `roi`, `underpriced_rate`, `items_total`, and `item_name`.

The current weekly histogram can stay because it helps answer whether underpricing is recurring or isolated.

Its filter rules should be deterministic:

- it uses the same `league`, `min_total`, and `max_buy_in` filters as the item-level opportunity query,
- it remains item-level only in v1, even if the table mixes item and affix rows,
- it applies `query` only against item labels, not affix text,
- it ignores `sort` and `limit`,
- it first builds the filtered item-level cohort only, deduplicated by `item_name`, then aggregates weekly too-cheap counts across that cohort,
- it counts listings at or below each filtered item row's `p10` threshold by week.

This means an affix-only text match affects the table rows but does not create a separate affix weekly histogram in v1.

If a query only matches affix text and no item-label weekly series applies, the frontend should keep rendering the table results and show an explicit empty-state message in the chart area such as "Weekly trend is available for item-name matches only."

### 3. Empty and Degraded States

The frontend should remain conservative when data is sparse or unavailable.

- if a query has no relevant matches, show an empty state that explicitly says no matching historical listings were found,
- if the outlier query returns no cheap opportunities under the current cap, say so clearly rather than implying the feature is broken,
- if backend fields are missing or the request fails, show the existing degraded state instead of rendering incomplete finance metrics.

## Query Strategy

The backend query work should stay additive and bounded.

- Continue using `ml_price_dataset_v1` as the primary history source.
- Reuse existing item-label SQL helpers so unique items and base items stay consistent.
- Add relevance expressions in SQL rather than post-processing rows in Python.
- Compute opportunity metrics inside the `pricing-outliers` SQL pipeline so ranking and filtering happen close to the data.
- Preserve the existing weekly histogram query and make it use the same effective `league`, `min_total`, and `max_buy_in` filters as the item-level opportunity rows, with `query` applied only to item labels.

## Testing Strategy

### Backend

Add unit coverage for `poe_trade/api/ops.py` that verifies:

- exact search matches outrank prefix and substring matches,
- `search-history` preserves the intended query semantics,
- `pricing-outliers` applies the default `100c` buy-in cap,
- opportunity rows compute `entryPrice`, `expectedProfit`, `roi`, and `underpricedRate` correctly,
- invalid numeric params clamp or fall back safely.

### Frontend

Add or extend frontend tests that verify:

- analytics API requests include the new buy-in parameter,
- the outlier panel defaults to `100c`,
- the table renders profit- and ROI-oriented columns,
- empty and degraded states remain correct,
- search results and suggestions reflect the newer relevance-first behavior from the mocked API payloads.

### API Client

Extend `frontend/src/services/api.test.ts` and related normalization tests to cover:

- request serialization for `max_buy_in`,
- response normalization for any new outlier row fields,
- backwards-compatible handling if older payloads omit newer optional fields.

The implementation should also reconcile the existing analytics contract shapes in `frontend/src/types/api.ts` and the response-normalization logic in `frontend/src/services/api.ts` so the frontend type layer matches the backend payload actually returned by `poe_trade/api/ops.py`.

## Risks and Guardrails

- Search relevance can become confusing if exact-match and sort semantics fight each other. Relevance should only dominate where the user expects it.
- Very cheap, very sparse items can look attractive but be statistically noisy. Keep minimum support and underpriced recurrence visible.
- ROI alone can over-promote tiny edges on near-zero price items. Ranking should consider both ROI and absolute profit.
- Frontend-only opportunity math would drift from backend truth. Keep financial calculations server-side.

## Rollout Notes

- The route surface stays stable, but the `pricing-outliers` row contract expands and requires coordinated backend, API-normalization, and type updates.
- Frontend code should tolerate both old and new outlier fields during development to reduce lockstep breakage.
- Existing search and analytics panels stay in their current location, minimizing user retraining.
