# Private Stash Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an async private-stash scan flow for `Mirage` that prices every item in every stash tab, publishes only fully completed scans, preserves upstream tab order, and exposes item history with error bands to the frontend.

**Architecture:** Reuse the existing server-side `POESESSID` session bootstrap and the existing private stash harvester path, but add durable scan-run storage, ordered tab snapshots, staged valuation rows, and a published-scan pointer. Extend the stash API and stash UI so the frontend can start a scan, poll status, keep reading the last published snapshot until the new one is complete, and open per-item history popups from a stable lineage key.

**Tech Stack:** Python 3.11, ClickHouse SQL migrations, existing `poe_trade.api` and `poe_trade.ingestion` modules, React + Vite frontend in the nested `frontend/` repo, pytest, vitest.

---

## File Structure Map

- Create: `schema/migrations/0056_private_stash_scan_storage.sql` - additive tables for scan runs, ordered tab snapshots, item valuations, a durable active-scan pointer, and the published-scan pointer.
- Create: `poe_trade/stash_scan.py` - stash-scan domain helpers for item lineage keys, clipboard serialization, pricing normalization, scan persistence helpers, and published-read queries.
- Modify: `poe_trade/ingestion/account_stash_harvester.py` - fetch upstream tab metadata with exact tab order, iterate tabs by `tabIndex`, price every item, write staged rows, and publish atomically.
- Modify: `poe_trade/services/account_stash_harvester.py` - add one-shot scan mode wiring that uses saved credential state and surfaces scan-specific options.
- Modify: `poe_trade/api/stash.py` - publish-aware stash status, published tab reads, ordered tabs, scan-status payloads, and item-history payloads.
- Modify: `poe_trade/api/app.py` - add `POST /api/v1/stash/scan`, `GET /api/v1/stash/scan/status`, and `GET /api/v1/stash/items/{fingerprint}/history` routes, plus the non-blocking background launcher and duplicate-scan protection.
- Test: `tests/unit/test_stash_scan.py` - unit coverage for lineage keys, pricing normalization, publish-pointer behavior, tab ordering, and history shaping.
- Modify: `tests/unit/test_api_stash.py` - published-only reads, scan status, ordered tabs, and item history endpoint helpers.
- Modify: `tests/unit/test_account_stash_harvester.py` - private tab-list fetches, ordered `tabIndex` iteration, and atomic publish/failure behavior.
- Modify: `tests/unit/test_account_stash_service.py` - service wiring for scan start mode and saved `POESESSID` handling.
- Modify: `tests/unit/test_migrations.py` - migration listing and additive-shape assertions.
- Create: `scripts/private_stash_scan_smoke.py` - live smoke script that reads `POESESSID` from the environment and prints only non-sensitive validation output.
- Modify: `README.md` - document the private stash scan endpoints, publish semantics, and verification commands.
- Modify: `frontend/src/types/api.ts` - stash scan status, enriched stash tab/item contracts, and item-history DTOs.
- Modify: `frontend/src/services/api.ts` - scan start/status/history methods and enriched stash response parsing.
- Create: `frontend/src/services/api.stash.test.ts` - focused frontend API tests for stash scan start, status, and history contracts.
- Modify: `frontend/src/components/tabs/StashViewerTab.tsx` - `Scan` button, polling, freshness/progress UI, ordered tabs, and item-history popup/dialog.
- Create: `frontend/src/components/tabs/StashViewerTab.test.tsx` - UI tests for scan polling, published-data preservation, ordered tab rendering, and history popup behavior.

### Task 1: Add ClickHouse Storage For Private Scan Runs And Published Snapshots

**Files:**
- Create: `schema/migrations/0056_private_stash_scan_storage.sql`
- Modify: `tests/unit/test_migrations.py`

- [ ] **Step 1: Write the failing migration tests**

```python
def test_private_stash_scan_migration_is_listed() -> None:
    migration = Path(__file__).resolve().parents[2] / "schema" / "migrations" / "0056_private_stash_scan_storage.sql"
    assert migration.exists()

def test_private_stash_scan_migration_defines_ordered_tab_and_publish_tables() -> None:
    sql = (Path(__file__).resolve().parents[2] / "schema" / "migrations" / "0056_private_stash_scan_storage.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_tabs" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_item_valuations" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_active_scans" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_published_scans" in sql
```

- [ ] **Step 2: Run the migration tests to verify they fail**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_migrations.py -k "0056 or private_stash_scan" -v`
Expected: FAIL because `0056_private_stash_scan_storage.sql` does not exist yet.

- [ ] **Step 3: Write the additive migration**

```sql
CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_runs (
    scan_id String,
    account_name String,
    league String,
    realm String,
    status LowCardinality(String),
    started_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    completed_at Nullable(DateTime64(3, 'UTC')),
    published_at Nullable(DateTime64(3, 'UTC')),
    failed_at Nullable(DateTime64(3, 'UTC')),
    tabs_total UInt32,
    tabs_processed UInt32,
    items_total UInt32,
    items_processed UInt32,
    error_message String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY (league, toYYYYMMDD(started_at))
ORDER BY (account_name, realm, league, scan_id);

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_tabs (
    scan_id String,
    account_name String,
    league String,
    realm String,
    tab_id String,
    tab_index UInt16,
    tab_name String,
    tab_type String,
    captured_at DateTime64(3, 'UTC'),
    tab_meta_json String,
    payload_json String
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(captured_at))
ORDER BY (account_name, realm, league, scan_id, tab_index, tab_id);

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_item_valuations (
    scan_id String,
    account_name String,
    league String,
    realm String,
    tab_id String,
    tab_index UInt16,
    lineage_key String,
    content_signature String,
    item_id String,
    item_name String,
    item_class String,
    rarity LowCardinality(String),
    x UInt16,
    y UInt16,
    w UInt16,
    h UInt16,
    listed_price Nullable(Float64),
    currency LowCardinality(String),
    predicted_price Float64,
    confidence Float64,
    price_p10 Nullable(Float64),
    price_p90 Nullable(Float64),
    fallback_reason String,
    priced_at DateTime64(3, 'UTC'),
    icon_url String,
    payload_json String
) ENGINE = MergeTree()
PARTITION BY (league, toYYYYMMDD(priced_at))
ORDER BY (account_name, realm, league, lineage_key, priced_at, scan_id, tab_index);

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_active_scans (
    account_name String,
    league String,
    realm String,
    scan_id String,
    is_active UInt8,
    started_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY league
ORDER BY (account_name, realm, league);

CREATE TABLE IF NOT EXISTS poe_trade.account_stash_published_scans (
    account_name String,
    league String,
    realm String,
    scan_id String,
    published_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(published_at)
PARTITION BY league
ORDER BY (account_name, realm, league);
```

- [ ] **Step 4: Add grants in the same migration**

```sql
GRANT SELECT, INSERT ON poe_trade.account_stash_scan_runs TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_scan_tabs TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_item_valuations TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_active_scans TO poe_api_reader;
GRANT SELECT, INSERT ON poe_trade.account_stash_published_scans TO poe_api_reader;
GRANT INSERT ON poe_trade.account_stash_scan_runs TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_scan_tabs TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_item_valuations TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_active_scans TO poe_ingest_writer;
GRANT INSERT ON poe_trade.account_stash_published_scans TO poe_ingest_writer;
```

- [ ] **Step 5: Re-run the migration tests**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_migrations.py -k "0056 or private_stash_scan" -v`
Expected: PASS.

- [ ] **Step 6: Commit the storage layer**

```bash
git add schema/migrations/0056_private_stash_scan_storage.sql tests/unit/test_migrations.py
git commit -m "feat: add private stash scan storage"
```

### Task 2: Build The Shared Private Stash Scan Domain Helpers

**Files:**
- Create: `poe_trade/stash_scan.py`
- Create: `tests/unit/test_stash_scan.py`

- [ ] **Step 1: Write the failing unit tests**

```python
def test_lineage_key_prefers_upstream_item_id() -> None:
    item = {"id": "item-123", "name": "Chaos Orb", "typeLine": "Chaos Orb"}
    assert lineage_key_for_item(item, prior_matches={}) == "item:item-123"

def test_content_signature_ignores_position_changes() -> None:
    a = {"name": "Grim Bane", "typeLine": "Hubris Circlet", "x": 1, "y": 1, "explicitMods": ["+93 to maximum Life"]}
    b = {"name": "Grim Bane", "typeLine": "Hubris Circlet", "x": 4, "y": 7, "explicitMods": ["+93 to maximum Life"]}
    assert content_signature_for_item(a) == content_signature_for_item(b)

def test_normalize_stash_prediction_keeps_interval_fields() -> None:
    result = normalize_stash_prediction({"predictedValue": 42.0, "confidence": 78.0, "interval": {"p10": 35.0, "p90": 55.0}})
    assert result.predicted_price == 42.0
    assert result.price_p10 == 35.0
    assert result.price_p90 == 55.0

def test_lineage_key_uses_prior_signature_match_before_position_tie_break() -> None:
    item = {"name": "Grim Bane", "typeLine": "Hubris Circlet", "explicitMods": ["+93 to maximum Life"]}
    assert lineage_key_from_previous_scan(
        signature="sig-123",
        prior_signature_matches={"sig-123": "sig:existing-lineage"},
        prior_position_matches={"tab-1:4:7": "sig:position-lineage"},
        position_key="tab-1:4:7",
    ) == "sig:existing-lineage"

def test_serialize_item_to_clipboard_keeps_name_base_and_mod_lines() -> None:
    item = {"name": "Grim Bane", "typeLine": "Hubris Circlet", "explicitMods": ["+93 to maximum Life"]}
    clipboard = serialize_stash_item_to_clipboard(item)
    assert "Grim Bane" in clipboard
    assert "Hubris Circlet" in clipboard
    assert "+93 to maximum Life" in clipboard
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_stash_scan.py -v`
Expected: FAIL because `poe_trade/stash_scan.py` does not exist.

- [ ] **Step 3: Implement the domain helpers**

```python
@dataclass(frozen=True)
class StashPrediction:
    predicted_price: float
    currency: str
    confidence: float
    price_p10: float | None
    price_p90: float | None
    fallback_reason: str

def content_signature_for_item(item: Mapping[str, Any]) -> str:
    stable = {
        "name": str(item.get("name") or "").strip(),
        "typeLine": str(item.get("typeLine") or item.get("baseType") or "").strip(),
        "rarity": item.get("frameType"),
        "itemClass": str(item.get("itemClass") or "").strip(),
        "mods": _normalized_mod_lines(item),
        "icon": str(item.get("icon") or "").strip(),
    }
    return sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()

def lineage_key_for_item(item: Mapping[str, Any], *, prior_matches: Mapping[str, str]) -> str:
    item_id = str(item.get("id") or "").strip()
    if item_id:
        return f"item:{item_id}"
    signature = content_signature_for_item(item)
    if signature in prior_matches:
        return prior_matches[signature]
    return f"sig:{signature}"

def lineage_key_from_previous_scan(*, signature: str, prior_signature_matches: Mapping[str, str], prior_position_matches: Mapping[str, str], position_key: str) -> str:
    if signature in prior_signature_matches:
        return prior_signature_matches[signature]
    if position_key in prior_position_matches:
        return prior_position_matches[position_key]
    return f"sig:{signature}"
```

- [ ] **Step 4: Add published-read query helpers in the same module**

```python
def published_scan_id(client: ClickHouseClient, *, account_name: str, league: str, realm: str) -> str | None:
    ...

def fetch_published_tabs(client: ClickHouseClient, *, account_name: str, league: str, realm: str) -> dict[str, Any]:
    ...

def fetch_item_history(client: ClickHouseClient, *, account_name: str, league: str, realm: str, lineage_key: str, limit: int = 20) -> dict[str, Any]:
    ...
```

- [ ] **Step 5: Re-run the focused unit tests**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_stash_scan.py -v`
Expected: PASS.

- [ ] **Step 6: Commit the domain layer**

```bash
git add poe_trade/stash_scan.py tests/unit/test_stash_scan.py
git commit -m "feat: add private stash scan helpers"
```

### Task 3: Extend The Private Harvester To Run Ordered Full-Stash Scans And Publish Atomically

**Files:**
- Modify: `poe_trade/ingestion/account_stash_harvester.py`
- Modify: `poe_trade/services/account_stash_harvester.py`
- Modify: `tests/unit/test_account_stash_harvester.py`
- Modify: `tests/unit/test_account_stash_service.py`

- [ ] **Step 1: Write the failing harvester/service tests**

```python
def test_harvester_fetches_tab_list_with_tabs_flag_and_preserves_upstream_order() -> None:
    ...

def test_harvester_prices_every_item_before_publish_pointer_swap() -> None:
    ...

def test_harvester_leaves_previous_published_scan_when_new_scan_fails() -> None:
    ...

def test_harvester_fails_scan_when_any_item_lacks_concrete_valuation() -> None:
    ...

def test_harvester_preserves_fast_sale_and_trust_metadata_from_pricing_result() -> None:
    ...

def test_service_scan_mode_uses_saved_poe_session_cookie() -> None:
    ...
```

- [ ] **Step 2: Run the focused harvester/service tests to verify they fail**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_account_stash_harvester.py tests/unit/test_account_stash_service.py -v`
Expected: FAIL because scan-mode behavior and publish semantics do not exist yet.

- [ ] **Step 3: Add scan orchestration to the harvester**

```python
class AccountStashHarvester:
    def run_private_scan(self, *, realm: str, league: str, price_item: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> dict[str, Any]:
        scan_id = new_scan_id()
        self._record_scan_started(...)
        self._mark_scan_active(scan_id, is_active=1)
        tabs_payload = self._client.request("GET", stash_endpoint(realm, league), params={"tabs": "1"}, headers=self._request_headers)
        ordered_tabs = _ordered_tabs_from_payload(tabs_payload)
        self._write_tab_rows(scan_id, ordered_tabs)
        for tab in ordered_tabs:
            payload = self._client.request("GET", stash_endpoint(realm, league), params={"tabs": "0", "tabIndex": str(tab["i"])}, headers=self._request_headers)
            self._write_priced_items(scan_id, tab, payload, price_item)
            self._record_progress(...)
        self._assert_every_item_has_concrete_valuation(scan_id)
        self._publish_scan(scan_id)
        self._mark_scan_active(scan_id, is_active=0)
        return {"scanId": scan_id, "status": "published"}
```

- [ ] **Step 4: Wire a scan-specific service mode**

```python
parser.add_argument("--scan-once", action="store_true", help="Run one private stash pricing scan and exit")

if args.scan_once:
    harvester.run_private_scan(...)
    return 0
```

- [ ] **Step 5: Re-run the focused backend tests**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_account_stash_harvester.py tests/unit/test_account_stash_service.py tests/unit/test_stash_scan.py -v`
Expected: PASS.

- [ ] **Step 6: Commit the scan orchestrator**

```bash
git add poe_trade/ingestion/account_stash_harvester.py poe_trade/services/account_stash_harvester.py tests/unit/test_account_stash_harvester.py tests/unit/test_account_stash_service.py tests/unit/test_stash_scan.py
git commit -m "feat: add ordered private stash scan flow"
```

### Task 4: Expose Published Scan Reads, Scan Status, And Item History Through The API

**Files:**
- Modify: `poe_trade/api/stash.py`
- Modify: `poe_trade/api/app.py`
- Modify: `tests/unit/test_api_stash.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_stash_tabs_returns_only_published_scan_rows_in_tab_index_order() -> None:
    ...

def test_stash_tabs_returns_snapshot_metadata_and_running_summary() -> None:
    ...

def test_stash_scan_status_reports_running_progress_and_current_published_scan() -> None:
    ...

def test_stash_item_history_returns_newest_first_entries_with_error_bands() -> None:
    ...

def test_start_scan_requires_connected_session() -> None:
    ...

def test_start_scan_reuses_active_scan_when_duplicate_request_arrives() -> None:
    ...

def test_start_scan_returns_scope_and_started_at_fields() -> None:
    ...
```

- [ ] **Step 2: Run the focused API tests to verify they fail**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_api_stash.py -v`
Expected: FAIL because the new routes and published-scan read behavior do not exist yet.

- [ ] **Step 3: Add stash API helpers**

```python
def stash_scan_status_payload(...):
    return {
        "status": status,
        "activeScanId": active_scan_id,
        "publishedScanId": published_scan_id,
        "startedAt": started_at,
        "updatedAt": updated_at,
        "publishedAt": published_at,
        "progress": {...},
        "error": error_message,
    }

def stash_item_history_payload(...):
    return {
        "fingerprint": lineage_key,
        "item": {"name": item_name, "rarity": rarity, "itemClass": item_class, "iconUrl": icon_url},
        "history": rows,
    }

def fetch_stash_tabs(...):
    return {
        "scanId": published_scan_id,
        "publishedAt": published_at,
        "isStale": is_stale,
        "scanStatus": running_summary,
        "stashTabs": ordered_tabs,
    }
```

- [ ] **Step 4: Register the new routes and non-blocking launcher in `ApiApp`**

```python
self.router.add("/api/v1/stash/scan", ("POST", "OPTIONS"), self._stash_scan_start)
self.router.add("/api/v1/stash/scan/status", ("GET", "OPTIONS"), self._stash_scan_status)
self.router.add("/api/v1/stash/items/{fingerprint}/history", ("GET", "OPTIONS"), self._stash_item_history)

def _stash_scan_start(self, context: Mapping[str, object]) -> Response:
    existing = active_scan_for_scope(self.client, account_name=account_name, league=league, realm=realm)
    if existing is not None and existing.is_active:
        return json_response({
            "scanId": existing.scan_id,
            "status": "running",
            "startedAt": existing.started_at,
            "accountName": account_name,
            "league": league,
            "realm": realm,
            "deduplicated": True,
        }, status=202)
    scan_id = create_scan_run(...)
    mark_active_scan(...)
    thread = threading.Thread(target=self._run_private_stash_scan, args=((account_name, league, realm), scan_id), daemon=True)
    thread.start()
    return json_response({
        "scanId": scan_id,
        "status": "running",
        "startedAt": started_at,
        "accountName": account_name,
        "league": league,
        "realm": realm,
    }, status=202)
```

- [ ] **Step 5: Re-run the focused API tests**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_api_stash.py tests/unit/test_stash_scan.py -v`
Expected: PASS.

- [ ] **Step 6: Commit the API layer**

```bash
git add poe_trade/api/app.py poe_trade/api/stash.py tests/unit/test_api_stash.py tests/unit/test_stash_scan.py
git commit -m "feat: add published stash scan api"
```

### Task 5: Extend Frontend Contracts And API Wiring For Scan Start, Polling, And History

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/services/api.ts`
- Create: `frontend/src/services/api.stash.test.ts`

- [ ] **Step 1: Write the failing frontend API-contract tests**

```tsx
it('starts a stash scan and returns scan metadata', async () => {
  ...
})

it('fetches stash scan status and item history', async () => {
  ...
  expect(result.item.name).toBe('Grim Bane')
  expect(result.history[0].interval.p10).toBe(35)
})
```

- [ ] **Step 2: Run the new frontend contract tests to verify they fail**

Run: `npm_config_node_options="--require=$PWD/frontend/vitest-ensure-tmp.cjs" npm --prefix frontend test -- src/services/api.stash.test.ts`
Expected: FAIL because the stash scan methods and DTOs do not exist yet.

- [ ] **Step 3: Extend the stash DTOs**

```ts
export interface StashScanStatus {
  status: 'idle' | 'running' | 'publishing' | 'published' | 'failed';
  activeScanId: string | null;
  publishedScanId: string | null;
  startedAt: string | null;
  updatedAt: string | null;
  publishedAt: string | null;
  progress: { tabsTotal: number; tabsProcessed: number; itemsTotal: number; itemsProcessed: number };
  error?: string | null;
}

export interface StashScanStartResponse {
  scanId: string;
  status: 'running';
  startedAt: string;
  accountName: string;
  league: string;
  realm: string;
  deduplicated?: boolean;
}

export interface StashTabsResponse {
  scanId: string | null;
  publishedAt: string | null;
  isStale: boolean;
  scanStatus?: StashScanStatus | null;
  stashTabs: StashTab[];
}

export interface StashItemHistoryEntry {
  scanId: string;
  pricedAt: string;
  predictedValue: number;
  confidence: number;
  interval: { p10: number | null; p90: number | null };
  priceRecommendationEligible?: boolean;
  estimateTrust?: string;
  fallbackReason?: string;
}

export interface StashItemHistoryResponse {
  fingerprint: string;
  item: {
    name: string;
    rarity: string;
    itemClass?: string;
    iconUrl?: string;
  };
  history: StashItemHistoryEntry[];
}
```

- [ ] **Step 4: Add frontend API methods**

```ts
async startStashScan() {
  return request<StashScanStartResponse>('/api/v1/stash/scan', { method: 'POST' });
}

async getStashScanStatus() {
  return request<StashScanStatus>('/api/v1/stash/scan/status');
}

async getStashItemHistory(fingerprint: string) {
  return request<StashItemHistoryResponse>(`/api/v1/stash/items/${encodeURIComponent(fingerprint)}/history`);
}
```

- [ ] **Step 5: Re-run the frontend contract tests**

Run: `npm_config_node_options="--require=$PWD/frontend/vitest-ensure-tmp.cjs" npm --prefix frontend test -- src/services/api.stash.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit the frontend contract layer**

```bash
git -C frontend add src/types/api.ts src/services/api.ts src/services/api.stash.test.ts
git -C frontend commit -m "feat: add stash scan frontend api contracts"
```

### Task 6: Update The Stash UI For Scan Progress, Ordered Tabs, And Item History

**Files:**
- Modify: `frontend/src/components/tabs/StashViewerTab.tsx`
- Create: `frontend/src/components/tabs/StashViewerTab.test.tsx`

- [ ] **Step 1: Write the failing stash UI tests**

```tsx
it('keeps rendering the last published stash while a new scan is running', async () => {
  ...
})

it('renders tabs in backend order and opens history details for an item', async () => {
  ...
  expect(screen.getByText('Grim Bane')).toBeInTheDocument()
  expect(screen.getByText(/Hubris Circlet|Helmet|Rare/i)).toBeInTheDocument()
})

it('starts a scan, polls status, and refreshes once the scan publishes', async () => {
  ...
})
```

- [ ] **Step 2: Run the new stash UI tests to verify they fail**

Run: `npm_config_node_options="--require=$PWD/frontend/vitest-ensure-tmp.cjs" npm --prefix frontend test -- src/components/tabs/StashViewerTab.test.tsx`
Expected: FAIL because the UI has no scan button, polling, or history popup behavior yet.

- [ ] **Step 3: Refactor `StashViewerTab` around explicit load and poll flows**

```tsx
const loadPublished = useCallback(async () => {
  const [stashStatus, tabs] = await Promise.all([api.getStashStatus(), api.getStashTabs()]);
  setStatus(stashStatus.status);
  setTabs(tabs);
}, []);

const startScan = async () => {
  await api.startStashScan();
  setScanPolling(true);
};

useEffect(() => {
  if (!scanPolling) return;
  const timer = window.setInterval(async () => {
    const next = await api.getStashScanStatus();
    setScanStatus(next);
    if (next.status === 'published') {
      window.clearInterval(timer);
      await loadPublished();
    }
  }, 1500);
  return () => window.clearInterval(timer);
}, [scanPolling, loadPublished]);
```

- [ ] **Step 4: Add a history popup and richer item fields**

```tsx
<Button onClick={startScan} disabled={scanBusy}>Scan</Button>
<Dialog open={historyOpen} onOpenChange={setHistoryOpen}>...</Dialog>
```

- [ ] **Step 5: Re-run the new stash UI tests**

Run: `npm_config_node_options="--require=$PWD/frontend/vitest-ensure-tmp.cjs" npm --prefix frontend test -- src/components/tabs/StashViewerTab.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit the stash UI**

```bash
git -C frontend add src/components/tabs/StashViewerTab.tsx src/components/tabs/StashViewerTab.test.tsx
git -C frontend commit -m "feat: add private stash scan ui"
```

### Task 7: Update Docs And Run Full Feature Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ops-runbook.md` (only if scan operations need operator guidance)
- Create: `scripts/private_stash_scan_smoke.py`

- [ ] **Step 1: Write the failing doc assertions or checklist notes**

```markdown
- document `POST /api/v1/stash/scan`
- document `GET /api/v1/stash/scan/status`
- document `GET /api/v1/stash/items/{fingerprint}/history`
- document that `GET /api/v1/stash/tabs` returns the last published scan only
```

- [ ] **Step 2: Update the docs with implemented behavior only**

```markdown
- `POST /api/v1/stash/scan` starts one private stash scan for the authenticated account.
- `GET /api/v1/stash/scan/status` reports run progress while `GET /api/v1/stash/tabs` continues to serve the last published scan.
- `GET /api/v1/stash/items/{fingerprint}/history` returns per-item estimate history with `p10`/`p90` bands.
```

- [ ] **Step 3: Add the live smoke script**

```python
session = os.environ["POESESSID"].strip()
client = PoeClient(...)
payload = client.request(
    "GET",
    "character-window/get-stash-items",
    params={"accountName": account_name, "realm": realm, "league": league, "tabs": "1", "tabIndex": "0"},
    headers={"Cookie": f"POESESSID={session}"},
)
print(json.dumps({"tabCount": len(payload.get("tabs") or []), "firstTabName": first_tab_name}, indent=2))
```

- [ ] **Step 4: Run backend verification for the touched area**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_migrations.py tests/unit/test_stash_scan.py tests/unit/test_api_stash.py tests/unit/test_account_stash_harvester.py tests/unit/test_account_stash_service.py`
Expected: PASS.

- [ ] **Step 5: Run broader backend verification**

Run: `/home/hal9000/docker/poe_trade/.venv/bin/pytest tests/unit/test_auth_session.py tests/unit/test_api_ml_routes.py`
Expected: PASS.

- [ ] **Step 6: Run frontend verification for the touched area**

Run: `npm_config_node_options="--require=$PWD/frontend/vitest-ensure-tmp.cjs" npm --prefix frontend test -- src/services/api.stash.test.ts src/components/tabs/StashViewerTab.test.tsx`
Expected: PASS.

- [ ] **Step 7: Run frontend build verification**

Run: `npm_config_node_options="--require=$PWD/frontend/vitest-ensure-tmp.cjs" npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 8: Run one safe live validation against Path of Exile without recording the secret**

Run: `POESESSID=<set in local environment, do not paste into shell history> /home/hal9000/docker/poe_trade/.venv/bin/python scripts/private_stash_scan_smoke.py --league Mirage --realm pc`
Expected: PASS with ordered tab metadata and at least one successful private stash response, or a clear upstream auth/rate-limit error without leaking credentials.

- [ ] **Step 9: Commit the docs and verification-ready state**

```bash
git add README.md docs/ops-runbook.md
git commit -m "docs: add private stash scan runbook"
```

## Execution Notes

- The root repo and the nested `frontend/` repo must both be updated in the same feature workspace.
- The frontend worktree needs the absolute preload override for Node commands in this workspace:
  - `npm_config_node_options="--require=$PWD/frontend/vitest-ensure-tmp.cjs" npm --prefix frontend ...`
- The current frontend baseline is not clean in unrelated areas (`src/services/api.test.ts`, `src/components/tabs/DashboardTab.test.tsx`, `src/components/tabs/OpportunitiesTab.test.tsx`). Do not claim a globally green frontend baseline unless those pre-existing failures are addressed too.
