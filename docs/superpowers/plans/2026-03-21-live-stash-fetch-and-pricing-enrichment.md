# Live Stash Fetch And Pricing Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show private stash tabs/items immediately from a valid `POESESSID`, including listed prices from item notes, then enrich those visible items with predicted pricing metadata after the valuation scan publishes.

**Architecture:** Split stash rendering into two data sources with distinct responsibilities. The backend adds a live private-stash API backed by the Path of Exile stash endpoint plus normalized `mergeKey` item identity, while keeping the existing published scan API for valuation output. The frontend switches first render to the live stash API, eagerly loads every tab in the background, and merges published valuation fields onto visible live items by `mergeKey` only.

**Tech Stack:** Python 3.11, existing `poe_trade` API/ingestion modules, ClickHouse-backed published scan queries, React, TypeScript, Vitest.

---

## File map

- Modify: `poe_trade/api/app.py` - register live stash routes and update stash status semantics.
- Modify: `poe_trade/api/stash.py` - add live stash payload helpers, status contract changes, and shared response shaping.
- Modify: `poe_trade/ingestion/account_stash_harvester.py` - reuse private stash request/ordering helpers from a read-only path if possible.
- Modify: `poe_trade/stash_scan.py` - expose normalized live item helpers and consistent `mergeKey`/fingerprint shaping shared by live and published payloads.
- Modify: `tests/unit/test_api_stash.py` - add backend coverage for live stash endpoints, status semantics, empty-state semantics, and merge identity fields.
- Modify: `tests/unit/test_api_ops_routes.py` if route registration/assertions are covered there - add route-level coverage for the new live stash endpoints if existing patterns require it.
- Modify: `frontend/src/types/api.ts` - add live stash response types and make stash status/live item prediction fields nullable/compatible.
- Modify: `frontend/src/services/api.ts` - add `getLiveStashTabs()` and `getLiveStashTab()` client methods plus normalization helpers.
- Modify: `frontend/src/services/api.stash.test.ts` - add frontend service tests for the live stash endpoints.
- Modify: `frontend/src/components/tabs/StashViewerTab.tsx` - swap first render to live stash, eagerly load tab contents, preserve scan polling, and overlay published prediction fields by `mergeKey`.
- Modify: `frontend/src/components/tabs/StashViewerTab.test.tsx` - verify immediate live stash rendering, true empty/degraded states, eager tab loading, and post-scan enrichment.

### Task 1: Normalize backend live stash contracts

**Files:**
- Modify: `poe_trade/stash_scan.py`
- Modify: `poe_trade/ingestion/account_stash_harvester.py`
- Test: `tests/unit/test_api_stash.py`

- [ ] **Step 1: Write the failing backend identity/normalization tests**

Add tests that exercise a helper returning live stash tab/item payloads with these expectations:

```python
def test_live_item_payload_includes_merge_key_and_nullable_prediction_fields() -> None:
    item = {
        "id": "item-1",
        "name": "Grim Bane",
        "typeLine": "Samite Helmet",
        "itemClass": "Helmet",
        "frameType": 2,
        "x": 0,
        "y": 1,
        "w": 2,
        "h": 2,
        "note": "~price 40 chaos",
        "icon": "https://web.poecdn.com/item.png",
    }

    payload = to_live_api_item(item, tab_id="tab-2", tab_index=1)

    assert payload["mergeKey"] == "item:item-1"
    assert payload["listedPrice"] == 40.0
    assert payload["currency"] == "chaos"
    assert payload["estimatedPrice"] is None
    assert payload["estimatedPriceConfidence"] is None
    assert payload["interval"] == {"p10": None, "p90": None}
    assert payload["estimateTrust"] == "normal"
    assert payload["estimateWarning"] == ""
    assert payload["fallbackReason"] == ""
    assert payload["note"] == "~price 40 chaos"
```

- [ ] **Step 2: Run the focused backend test and verify it fails**

Run: `.venv/bin/pytest tests/unit/test_api_stash.py -k live_item_payload -v`
Expected: FAIL because `to_live_api_item` or equivalent helper does not exist yet.

- [ ] **Step 3: Implement minimal shared live-item helpers**

Add focused helpers that reuse existing lineage and listed-price logic instead of duplicating scanner behavior:

```python
def to_live_api_item(item: dict[str, Any], *, tab_id: str, tab_index: int) -> dict[str, Any]:
    listed = parse_listed_price(str(item.get("note") or ""))
    listed_price = listed[0] if listed else None
    currency = listed[1] if listed else None
    return {
        "id": str(item.get("id") or ""),
        "mergeKey": lineage_key_for_item(item),
        "fingerprint": lineage_key_for_item(item),
        "tabId": tab_id,
        "tabIndex": tab_index,
        "x": int(item.get("x") or 0),
        "y": int(item.get("y") or 0),
        "w": int(item.get("w") or 1),
        "h": int(item.get("h") or 1),
        "name": str(item.get("name") or item.get("typeLine") or "Unknown"),
        "itemClass": str(item.get("itemClass") or "Unknown"),
        "rarity": _rarity_from_frame_type(item.get("frameType")),
        "note": str(item.get("note") or ""),
        "listedPrice": listed_price,
        "currency": currency,
        "estimatedPrice": None,
        "estimatedPriceConfidence": None,
        "priceDeltaChaos": None,
        "priceDeltaPercent": None,
        "priceEvaluation": None,
        "interval": {"p10": None, "p90": None},
        "estimateTrust": "normal",
        "estimateWarning": "",
        "fallbackReason": "",
    }
```

- [ ] **Step 4: Run the focused backend test and verify it passes**

Run: `.venv/bin/pytest tests/unit/test_api_stash.py -k live_item_payload -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_api_stash.py poe_trade/stash_scan.py poe_trade/ingestion/account_stash_harvester.py
git commit -m "test: add live stash item normalization"
```

### Task 2: Add live stash backend endpoints and status semantics

**Files:**
- Modify: `poe_trade/api/stash.py`
- Modify: `poe_trade/api/app.py`
- Test: `tests/unit/test_api_stash.py`

- [ ] **Step 1: Write failing tests for live stash status and routes**

Add tests covering:

```python
def test_stash_status_reports_connected_without_published_empty_state(...) -> None:
    payload = stash_status_payload(...)
    assert payload["status"] == "connected"
    assert payload["connected"] is True


def test_fetch_live_stash_tabs_returns_tab_metadata_for_valid_session(...) -> None:
    payload = fetch_live_stash_tabs(...)
    assert payload["stashTabs"] == [{"id": "tab-2", "name": "Currency", "type": "currency"}]


def test_fetch_live_stash_tab_returns_normalized_items(...) -> None:
    payload = fetch_live_stash_tab(..., tab_id="tab-2")
    assert payload["tab"]["id"] == "tab-2"
    assert payload["tab"]["items"][0]["mergeKey"] == "item:item-1"


def test_fetch_live_stash_rejects_mismatched_saved_session_account(...) -> None:
    with pytest.raises(ApiError) as exc:
        fetch_live_stash_tabs(...)
    assert exc.value.code == "auth_required"


def test_fetch_live_stash_rejects_invalid_poe_session(...) -> None:
    with pytest.raises(ApiError) as exc:
        fetch_live_stash_tabs(...)
    assert exc.value.code == "invalid_poe_session"
```

- [ ] **Step 2: Run the focused backend tests and verify they fail**

Run: `.venv/bin/pytest tests/unit/test_api_stash.py -k "live_stash or connected_without_published_empty_state" -v`
Expected: FAIL because the live helpers/routes and new status contract do not exist yet.

- [ ] **Step 3: Implement backend live stash readers and status change**

Implement:

```python
def stash_status_payload(...):
    return {
        "status": "connected",
        "connected": True,
        "tabCount": 0,
        "itemCount": 0,
        "session": {...},
        "publishedScanId": published_scan_id,
        "publishedAt": published_at,
        "scanStatus": scan_status,
    }


def fetch_live_stash_tabs(...):
    tabs_payload = poe_client.request(..., params=_private_stash_params(..., tabs="1", tab_index="0"), ...)
    return {"stashTabs": _ordered_private_tabs_from_payload(tabs_payload)}


def fetch_live_stash_tab(..., tab_id: str):
    payload = poe_client.request(...tab_index=str(tab_index)...)
    return {"tab": normalized_tab}
```

Register routes in `poe_trade/api/app.py` for:

- `GET /api/v1/stash/live`
- `GET /api/v1/stash/live/tabs/{tab_id}`

Use the existing credential validation pattern from `start_private_stash_scan()` so the live read path reuses the same auth guarantees.

- [ ] **Step 4: Run the focused backend tests and verify they pass**

Run: `.venv/bin/pytest tests/unit/test_api_stash.py -k "live_stash or connected_without_published_empty_state" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_api_stash.py poe_trade/api/stash.py poe_trade/api/app.py
git commit -m "feat: add live stash api endpoints"
```

### Task 3: Add frontend live stash API clients and types

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/services/api.ts`
- Test: `frontend/src/services/api.stash.test.ts`

- [ ] **Step 1: Write failing frontend service tests for live stash calls**

Add tests like:

```ts
test('fetches live stash tab metadata', async () => {
  const result = await api.getLiveStashTabs();
  expect(result.stashTabs[0].id).toBe('tab-2');
});

test('fetches one live stash tab payload', async () => {
  const result = await api.getLiveStashTab('tab-2');
  expect(result.tab.items[0].mergeKey).toBe('item:item-1');
  expect(result.tab.items[0].estimatedPrice).toBeNull();
});
```

- [ ] **Step 2: Run the focused frontend service tests and verify they fail**

Run: `npm test -- src/services/api.stash.test.ts`
Working dir: `frontend/`
Expected: FAIL because the live stash methods/types do not exist yet.

- [ ] **Step 3: Implement live stash types and client methods**

Extend the existing stash item contract instead of introducing a separate item shape. Add live stash response types and required `mergeKey` support with nullable prediction fields:

```ts
export interface LiveStashTabsResponse { stashTabs: Array<{ id: string; name: string; type: string; tabIndex: number }>; }
export interface LiveStashTabResponse { tab: StashTab & { tabIndex: number }; }
```

Add API methods:

```ts
async getLiveStashTabs() {
  const league = await primaryLeague();
  return request<LiveStashTabsResponse>(`/api/v1/stash/live?league=${encodeURIComponent(league)}&realm=pc`);
}

async getLiveStashTab(tabId: string) {
  const league = await primaryLeague();
  return request<LiveStashTabResponse>(`/api/v1/stash/live/tabs/${encodeURIComponent(tabId)}?league=${encodeURIComponent(league)}&realm=pc`);
}
```

- [ ] **Step 4: Run the focused frontend service tests and verify they pass**

Run: `npm test -- src/services/api.stash.test.ts`
Working dir: `frontend/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/services/api.ts frontend/src/services/api.stash.test.ts
git commit -m "feat: add frontend live stash api client"
```

### Task 4: Switch stash viewer to live-first rendering

**Files:**
- Modify: `frontend/src/components/tabs/StashViewerTab.tsx`
- Test: `frontend/src/components/tabs/StashViewerTab.test.tsx`

- [ ] **Step 1: Write failing component tests for live-first behavior**

Add tests covering:

```tsx
test('renders live stash tabs immediately without published scan data', async () => {
  expect(await screen.findByText('Currency')).toBeInTheDocument();
  expect(await screen.findByText('Grim Bane')).toBeInTheDocument();
});

test('does not show connected-empty while live tab requests are pending', async () => {
  render(<StashViewerTab />);
  expect(screen.queryByText('Connected but stash is empty')).not.toBeInTheDocument();
});

test('shows empty only after all live tabs finish with zero items', async () => {
  expect(await screen.findByTestId('state-empty')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused component tests and verify they fail**

Run: `npm test -- src/components/tabs/StashViewerTab.test.tsx`
Working dir: `frontend/`
Expected: FAIL because the component still depends on `getStashTabs()` for first render.

- [ ] **Step 3: Implement live-first stash loading with eager per-tab fetches**

Refactor the component into two clear flows:

```tsx
const loadLiveStash = useCallback(async () => {
  const status = await api.getStashStatus();
  setStatus(status.status);
  if (!status.connected) return;

  const meta = await api.getLiveStashTabs();
  setTabs(meta.stashTabs.map((tab) => ({ ...tab, items: [], loading: true })));

  await Promise.all(meta.stashTabs.map(async (tab) => {
    const payload = await api.getLiveStashTab(tab.id);
    setTabs((current) => mergeTabPayload(current, payload.tab));
  }));
});
```

Key rules:

- eager background fetch for every tab after tab metadata loads
- no empty-state while any live tab request is pending
- true empty-state only after all live requests finish and all tabs have zero items
- degraded state for permanent tab fetch failure
- keep published scan id / scan progress UI for the valuation flow

- [ ] **Step 4: Run the focused component tests and verify they pass**

Run: `npm test -- src/components/tabs/StashViewerTab.test.tsx`
Working dir: `frontend/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tabs/StashViewerTab.tsx frontend/src/components/tabs/StashViewerTab.test.tsx
git commit -m "feat: render live stash before valuation"
```

### Task 5: Overlay published prediction data onto live items

**Files:**
- Modify: `frontend/src/components/tabs/StashViewerTab.tsx`
- Modify: `frontend/src/types/api.ts`
- Test: `frontend/src/components/tabs/StashViewerTab.test.tsx`

- [ ] **Step 1: Write failing overlay tests**

Add tests like:

```tsx
test('keeps live stash visible while scan runs and overlays predictions after publish', async () => {
  fireEvent.click(screen.getByRole('button', { name: /scan/i }));
  expect(screen.getByText('Grim Bane')).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText(/45 chaos/i)).toBeInTheDocument());
});

test('does not overlay predictions for items without mergeKey', async () => {
  expect(screen.queryByText(/45 chaos/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused overlay tests and verify they fail**

Run: `npm test -- src/components/tabs/StashViewerTab.test.tsx`
Working dir: `frontend/`
Expected: FAIL because no `mergeKey`-based overlay logic exists yet.

- [ ] **Step 3: Implement `mergeKey`-only overlay after publish**

Create a focused helper:

```tsx
function overlayPublishedPredictions(liveTabs: LiveTab[], publishedTabs: StashTab[]): LiveTab[] {
  const publishedByKey = new Map<string, StashItem>();
  for (const tab of publishedTabs) {
    for (const item of tab.items) {
      if (item.mergeKey) publishedByKey.set(item.mergeKey, item);
    }
  }
  return liveTabs.map((tab) => ({
    ...tab,
    items: tab.items.map((item) => {
      const published = item.mergeKey ? publishedByKey.get(item.mergeKey) : undefined;
      return published ? { ...item, ...pickPredictionFields(published) } : item;
    }),
  }));
}
```

On scan publish:

- keep current live tabs visible
- call `api.getStashTabs()`
- overlay prediction-only fields by `mergeKey`
- update published scan metadata in the header

- [ ] **Step 4: Run the focused overlay tests and verify they pass**

Run: `npm test -- src/components/tabs/StashViewerTab.test.tsx`
Working dir: `frontend/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tabs/StashViewerTab.tsx frontend/src/components/tabs/StashViewerTab.test.tsx frontend/src/types/api.ts
git commit -m "feat: overlay published stash predictions onto live stash"
```

### Task 6: Run broader verification and clean up test/docs fallout

**Files:**
- Modify: any touched files above if verification exposes issues
- Test: `tests/unit/test_api_stash.py`
- Test: `frontend/src/services/api.stash.test.ts`
- Test: `frontend/src/components/tabs/StashViewerTab.test.tsx`

- [ ] **Step 1: Run backend verification**

Run: `.venv/bin/pytest tests/unit/test_api_stash.py -v`
Expected: PASS.

- [ ] **Step 2: Run frontend stash verification**

Run: `npm test -- src/services/api.stash.test.ts src/components/tabs/StashViewerTab.test.tsx`
Working dir: `frontend/`
Expected: PASS.

- [ ] **Step 3: Run one broader related backend suite**

Run: `.venv/bin/pytest tests/unit/test_account_stash_harvester.py tests/unit/test_account_stash_service.py -v`
Expected: PASS.

- [ ] **Step 4: Fix any failures minimally and rerun affected tests**

If failures appear, update only the touched contract surfaces and rerun the smallest failing command first, then rerun the full verification commands above.

- [ ] **Step 5: Commit**

```bash
git add poe_trade/api/app.py poe_trade/api/stash.py poe_trade/stash_scan.py tests/unit/test_api_stash.py frontend/src/types/api.ts frontend/src/services/api.ts frontend/src/services/api.stash.test.ts frontend/src/components/tabs/StashViewerTab.tsx frontend/src/components/tabs/StashViewerTab.test.tsx
git commit -m "feat: load live stash before pricing scan"
```
