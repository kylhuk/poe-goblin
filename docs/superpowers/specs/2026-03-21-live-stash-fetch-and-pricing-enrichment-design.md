## Goal

Show private stash tabs and items immediately after a valid `POESESSID` login, using the authenticated Path of Exile stash API, without waiting for a published valuation scan. After the user starts price estimation, enrich those already-visible items with prediction metadata needed for pricing UX.

## Context

Current frontend behavior depends on published scan data:

- `frontend/src/components/tabs/StashViewerTab.tsx` loads `/api/v1/stash/status` and `/api/v1/stash/tabs`.
- `poe_trade/api/stash.py` exposes published stash tabs from ClickHouse-backed scan output.
- If no published scan exists, the UI shows `Connected but stash is empty`, even when the account is authenticated and the stash itself is not empty.

This mixes two separate concerns:

1. viewing live private stash contents
2. enriching stash items with predicted pricing metadata

The user wants these decoupled. Live stash contents should appear immediately. Predicted pricing is a second task that runs afterward.

## User-approved behavior

- After login succeeds and account name is known, the stash tab should fetch and render all available stash tabs/items immediately.
- The UI may show the current listed price immediately when an item has a public note price.
- Price prediction is a second step. Starting estimation should enrich visible items instead of gating stash visibility.

## Approaches considered

### 1. Live stash endpoint plus later enrichment (recommended)

Add a new backend endpoint that reads private stash tabs/items directly from Path of Exile using the saved `POESESSID`. Return tabs immediately with raw stash metadata and parsed listed prices. Keep valuation as a second API path that overlays prediction metadata on the same items.

Pros:

- matches user expectation exactly
- removes false empty-state behavior
- keeps stash viewing resilient even if estimation is slow or unavailable
- preserves existing scan pipeline for prediction/history workflows

Cons:

- introduces a second stash payload shape unless carefully normalized
- requires a merge strategy between live item data and valuation results

### 2. Keep published scan as the only stash source

Continue using published scan output for stash rendering and ask the user to run a scan before the stash appears.

Pros:

- minimal backend change

Cons:

- preserves current broken UX
- conflates stash visibility with pricing
- does not satisfy the approved behavior

### 3. Auto-run a full valuation scan before first render

Kick off a scan automatically once login succeeds and only show stash data after the scan publishes.

Pros:

- one data source after scan completes

Cons:

- slower first render
- operationally heavier
- still delays basic stash visibility
- turns a read action into a long-running pricing task

## Recommended design

### Status semantics

`/api/v1/stash/status` should no longer infer stash emptiness from published scan rows.

Its responsibility should be limited to connection and scan lifecycle state:

- `disconnected`
- `session_expired`
- `feature_unavailable`
- `connected`

Optional status metadata may still include:

- session/account info
- latest published scan id/timestamp
- current scan lifecycle/progress

Live stash emptiness should be determined only by the live stash payload, not by the status endpoint. This prevents the current false-empty state where auth is valid but no published scan exists yet.

### Backend architecture

Add a live private stash read path that uses the same server-side `POESESSID` credential storage already used by the private stash scanner.

This design does not require changing credential persistence scope as part of this task. The existing server-side credential source remains the authority for both live stash reads and later scan/enrichment actions.

New behavior:

- resolve the logged-in account from the current server-side session state
- validate that the stored `POESESSID` belongs to that account
- fetch private stash tabs directly from the Path of Exile stash endpoint
- fetch tab contents through the progressive per-tab live contract and normalize them into the frontend stash shape
- parse item note prices into listed-price fields
- return prediction fields as optional or null when no valuation has been run yet

The existing published scan APIs remain in place for:

- price estimation lifecycle
- valuation history
- previously published scan metadata

### Enrichment contract

Prediction remains a separate flow from live stash reads.

Frontend API usage after this change:

1. `GET /api/v1/stash/status` for connection/session and scan state only
2. `GET /api/v1/stash/live` for immediate stash tabs/items from Path of Exile
3. `POST /api/v1/stash/scan` to start valuation
4. `GET /api/v1/stash/scan/status` for progress
5. `GET /api/v1/stash/tabs` for valuation-enriched published tabs once a scan is published

This means the overlay source is still the existing published stash tabs payload, but it is no longer the source of first render.

The frontend may either:

- replace live items with published enriched items after publish, if identity matches are stable enough to preserve UI continuity, or
- merge prediction fields from published items onto visible live items by identity key

The preferred behavior is merge/overlay, but full replacement is acceptable if it preserves tab selection and does not create visible flicker.

### Data contract

Introduce live stash APIs that support progressive rendering:

- `GET /api/v1/stash/live` returns tab metadata only
- `GET /api/v1/stash/live/tabs/{tab_id}` returns one normalized tab with its items
- each item includes enough identity to support later enrichment

`tab_id` must be the exact stash tab id returned by the upstream Path of Exile payload for that tab. The backend should pass it through unchanged, and the frontend should treat it as the canonical per-tab identifier for subsequent live-tab requests and UI state.

Per-item fields in the per-tab response should include at least:

- item id from Path of Exile payload
- required `mergeKey`, derived server-side as the same lineage/fingerprint key used by the published scan pipeline
- tab id and tab index
- position key (`x`, `y`, `w`, `h`)
- name/type/rarity/class/icon
- raw note and parsed listed price/currency
- optional prediction fields (`estimatedPrice`, `estimatedPriceConfidence`, interval, trust, warning, fallback reason)

Prediction fields should be nullable for the live-fetch phase so the frontend can render without fake values.

The required enrichment contract is:

- live stash items must include `mergeKey`
- published valuation items must expose the same `mergeKey`
- the frontend merges enriched prediction fields by `mergeKey`

If a live item lacks a derivable `mergeKey`, that item is not eligible for prediction overlay and should continue rendering with listed-price-only data until a later refresh provides a valid key. This avoids ambiguous fallback matching rules in the frontend.

### Frontend architecture

Change the stash tab to treat live stash visibility as the primary source of truth.

Load sequence:

1. call stash status to confirm connection/session state
2. if connected, call `GET /api/v1/stash/live` to load tab chrome/order/metadata
3. request tab contents with `GET /api/v1/stash/live/tabs/{tab_id}`
4. render tabs/items as soon as each tab payload is available
5. show listed price if present
6. when the user starts estimation, poll scan/progress as needed
7. merge prediction metadata into already-visible items when results become available

The empty state should only mean that the live stash API confirmed the account has no stash tabs, or that every live tab fetch completed and all tabs contained zero items. A missing published scan should no longer produce `Connected but stash is empty`.

### Live fetch latency model

The Path of Exile private stash API requires one request for the tab list and then one request per tab for contents. Because of that, “show immediately” means:

- begin rendering as soon as the tab list is known
- progressively populate tab contents through the per-tab live endpoint as each tab request completes
- avoid blocking the whole stash view on fetching every tab in the account

Acceptable UX:

- tab chrome can appear first
- a selected tab may show loading placeholders while its contents are being fetched
- already-fetched tabs remain visible while later tabs continue loading
- permanently failed live tab requests should surface a degraded-fetch state and must not resolve to the true empty-state

UI empty-state rule:

- the client should eagerly request every tab payload in the background after `GET /api/v1/stash/live` returns
- do not show the empty-state while any live tab request is still pending
- show the empty-state only after all live tab payloads have completed and the total rendered item count is zero, or the tab list itself is empty

This preserves immediate visibility without pretending that a very large stash can be fully materialized in a single round-trip.

### Enrichment strategy

Prediction should overlay onto existing visible items rather than replace the stash payload wholesale.

Authoritative matching rule:

- merge prediction fields only by `mergeKey`
- do not use frontend-side fallback matching by item id or position
- if a published valuation row or live item lacks `mergeKey`, that item is excluded from overlay and remains listed-price-only in the current session
- any full UI replacement after publish is a render-source swap, not an item-matching strategy

This keeps the visual stash stable while avoiding ambiguous matches.

### Error handling

Separate these states clearly:

- auth disconnected/session expired
- live stash fetch failed
- live stash empty
- estimation running
- estimation failed but live stash still visible

If live stash fetch fails, show a stash-specific degraded state. Do not map that failure to an empty stash.

If estimation fails, keep the stash rendered and show estimation as unavailable or partial.

### Testing

Backend tests:

- live stash endpoint returns tabs/items for a valid session
- listed price is parsed from item notes
- invalid/mismatched `POESESSID` is rejected
- empty live stash produces a true empty response
- prediction fields are nullable before estimation

Frontend tests:

- connected session renders live stash immediately
- no false empty-state is shown just because no published scan exists
- empty-state appears only when the live stash tab list or per-tab item fetch confirms the stash is truly empty
- listed price renders before prediction exists
- starting estimation preserves visible stash contents
- completed estimation enriches existing items with prediction metadata
- estimation failure keeps live stash visible

## Non-goals

- replacing the existing published scan/history model
- redesigning stash valuation logic itself
- changing server-side credential persistence design beyond reusing the current stored `POESESSID`

## Open implementation notes

- Prefer one normalized stash item type in the frontend with optional prediction fields, instead of separate live and published item types.
- The backend should reuse existing normalization helpers where possible to avoid diverging stash item semantics between live fetch and published scan output.
- If direct lineage/fingerprint derivation requires the same helper stack as the scanner, reuse it so enrichment keys remain consistent.

## Success criteria

- Valid `POESESSID` login shows real stash tabs/items without requiring a prior published scan.
- Items with note prices show their current listed price immediately.
- Running price estimation enriches those visible items with prediction metadata afterward.
- The frontend no longer shows `Connected but stash is empty` solely because no published scan exists.
