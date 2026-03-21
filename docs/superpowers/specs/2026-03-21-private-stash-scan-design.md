# Private Stash Scan Design

## Goal

Let an authenticated frontend user start a private `Mirage` stash scan using their configured `POESESSID`, price every item in every stash tab including non-public tabs, and expose only the last fully published result set to the frontend together with per-item estimate history and error bands.

## Problem Statement

The repo can already:

- accept `POESESSID` from the frontend and resolve an account name,
- fetch account-scoped stash snapshots,
- price a single item,
- render published stash tabs in the frontend.

It cannot yet:

- trigger a private stash scan on demand from the UI,
- fetch and preserve actual stash-tab order from the upstream account,
- price every item in a full stash snapshot,
- keep old published data visible while a new scan is still running,
- expose scan progress and failure state,
- return per-item valuation history for frontend popups.

## User-Facing Outcome

From the stash tab, the user should be able to:

1. connect once with `POESESSID`,
2. click `Scan`,
3. see scan progress while the previous published stash view remains visible,
4. receive a newly published stash snapshot only after the full scan completes,
5. inspect item valuation history and interval bands in a popup.

There is no character dropdown in scope. The scan target is the authenticated account stash for league `Mirage`.

## Non-Goals

- pricing equipped items or character inventories,
- supporting leagues other than the existing allowed stash/ML league flow,
- introducing a general job queue platform,
- storing or exposing unrelated cookies such as `cf_clearance` or `POETOKEN`,
- replacing the existing single-item pricing contract.

## Design Overview

The feature extends the current account-stash path rather than creating a separate subsystem.

The backend will use the saved server-side `POESESSID` to call the private Path of Exile stash endpoint in two phases:

1. fetch ordered tab metadata for the account in `Mirage`,
2. fetch each tab by `tabIndex`, price every item, and stage results under a new `scan_id`.

Results are published atomically. Reads always resolve to the most recent successful published scan. If a new scan is running or fails, the previous published snapshot remains the frontend truth.

## Existing Foundations To Reuse

- `frontend/src/components/UserMenu.tsx` already collects `POESESSID`.
- `frontend/src/services/auth.tsx` already boots a server-side auth session.
- `poe_trade/api/auth_session.py` already stores account-scoped credential state and resolves account identity using `POESESSID`.
- `poe_trade/ingestion/account_stash_harvester.py` already knows how to call private stash endpoints with account cookies.
- `poe_trade/api/stash.py` already shapes stash-tab responses.
- `poe_trade/api/ml.py` and the existing price-check path already define the pricing fields the stash valuation flow should reuse.

## Architecture

### 1. Scan Lifecycle

Each scan is represented by a durable run record keyed by `scan_id`, `account_name`, `league`, and `realm`.

The run lifecycle is:

- `queued` or `running` once started,
- `publishing` after all tab/item pricing has succeeded,
- `published` once the published pointer is flipped,
- `failed` if upstream fetch or write steps fail.

Only one active scan is allowed per account+league+realm. Starting a scan while one is already active should either return the current active run or reject with a deterministic `scan_in_progress` response. The key requirement is that concurrent clicks do not create conflicting publishes.

### 2. Upstream Fetch Strategy

The scan uses the authenticated private stash endpoint:

- first request with `tabs=1` to obtain tab metadata and the upstream tab order,
- subsequent requests with each `tabIndex` to fetch actual tab item payloads.

The backend must preserve upstream tab order exactly as returned by the account. That order is stored with the scan and returned in the published API payload so the frontend can draw stash tabs in the same sequence the user sees in game/web.

The scan remains account-scoped. No character or equipped-item context is applied.

### 3. Pricing Strategy

Every fetched stash item is converted into the same canonical pricing input shape used by the single-item estimator.

The pricing result stored per item should preserve at least:

- predicted value,
- currency,
- confidence,
- `p10` and `p90` interval values,
- fast-sale or recommendation eligibility fields if available,
- fallback reason or trust metadata if pricing fell back.

The stash flow should not invent a separate pricing contract. It should normalize single-item pricing output into stash-scan storage and API payloads.

### 4. Atomic Publish Model

Scan data is written in staged tables keyed by `scan_id`.

The publish rule is strict:

- do not replace the currently published snapshot until all tabs are fetched, all items are priced, and all staged rows are durable,
- if any step fails, mark the run failed and leave the published pointer unchanged,
- once the staged run is complete, write a single published-pointer update for that account+league+realm.

This guarantees that the frontend never reads half-finished data.

### 5. History Model

Each item valuation row is append-only and tied to a stable item fingerprint.

The identity strategy must avoid both false merges and needless history breaks:

- prefer the upstream item id when present,
- also persist a canonical content signature built from stable item descriptors such as name, base/type line, rarity, item class, normalized modifier lines, socket or influence state when present, and icon or art identifiers if available,
- when an upstream item id is missing, create a synthetic lineage key by matching the current item against the previous published scan within the same account+league+realm using the canonical content signature first and stash position only as a last-resort tie-breaker,
- if no safe prior match exists, start a new lineage key rather than merging two potentially distinct items.

History is queried by lineage key and sorted newest-first by `priced_at` or scan completion time.

The history payload should include at least:

- `scanId`,
- `pricedAt`,
- predicted value and currency,
- confidence,
- `p10` and `p90`,
- listed price when present,
- fallback reason or estimate warning.

## Storage Design

Additive ClickHouse tables should cover four responsibilities.

### Scan Runs

Stores one row per scan status transition with:

- `scan_id`, `account_name`, `league`, `realm`,
- status fields,
- started/completed/failed/published timestamps,
- tab and item progress counters,
- error message,
- freshness metadata.

### Ordered Tab Snapshots

Stores staged tab metadata and fetched tab payloads with:

- `scan_id`,
- `tab_id`, `tab_index`, `tab_name`, `tab_type`,
- upstream tab metadata JSON,
- account/league/realm scope,
- capture timestamp.

This table is the source of truth for tab ordering.

### Scan Items And Valuations

Stores one row per staged item plus its pricing result with:

- stable lineage key, canonical content signature, and optional upstream item id,
- stash position (`x`, `y`, `w`, `h`),
- item display fields,
- listed price fields,
- predicted value, confidence, bands, and pricing diagnostics,
- raw item payload JSON for deterministic reconstruction if needed.

This can be stored as one wide table or split into staged item rows and valuation rows. The deciding principle is that published reads and history queries remain simple and additive.

### Published Pointer

Stores the currently published `scan_id` for each account+league+realm.

Published stash reads resolve through this pointer first, then read tab/item rows only for that scan.

## API Design

### `POST /api/v1/stash/scan`

Starts a background scan for the authenticated account.

Response shape:

- `scanId`,
- `status`,
- `startedAt`,
- `accountName`, `league`, `realm`.

Behavior:

- requires an authenticated server-side session,
- uses the stored `POESESSID` on the server,
- refuses or coalesces duplicate active scans,
- never blocks until scan completion.

### `GET /api/v1/stash/scan/status`

Returns current run state for the authenticated account.

Response fields:

- `status` (`idle`, `running`, `publishing`, `published`, `failed`),
- `activeScanId`,
- `progress` counters for tabs/items,
- `startedAt`, `updatedAt`, `publishedAt`,
- `error` when failed,
- `publishedScanId` for the snapshot the frontend is currently reading.

### `GET /api/v1/stash/tabs`

Continues to be the main stash read endpoint, but it becomes explicitly published-snapshot-only.

Response adds:

- ordered tabs by stored upstream `tabIndex`,
- snapshot metadata such as `scanId`, `publishedAt`, `isStale`,
- per-item pricing fields including a stable `fingerprint`, confidence, and interval bands,
- optional high-level scan-status summary so the UI can show that a newer scan is still running.

Until a new scan publishes, this endpoint returns the previous published snapshot unchanged.

### `GET /api/v1/stash/items/{fingerprint}/history`

Returns valuation history for one published or historical item fingerprint.

Response includes:

- identifying item fields for the popup header,
- newest-first estimate history entries,
- predicted value, confidence, listed price, `p10`, `p90`, fallback reason, and timestamp for each entry.

## Frontend Design

`frontend/src/components/tabs/StashViewerTab.tsx` remains the primary UI surface.

Changes:

- add a `Scan` button near the stash header,
- poll `GET /api/v1/stash/scan/status` while a scan is active,
- keep rendering the last published stash tabs from `GET /api/v1/stash/tabs`,
- show progress and freshness labels without swapping to partial data,
- show item history in a popup or dialog backed by the history endpoint,
- render tabs in the exact order returned by the backend.

The old mount-time fetch can be refactored into a reusable refresh flow:

- initial load fetches status + published tabs,
- scan click starts a run then starts polling,
- successful publish triggers one published-tabs refetch,
- failed scan preserves the old tab set and shows an error state.

## Error Handling

### Session Errors

- Missing or expired session prevents scan start.
- Published stash reads may still return the last successful snapshot if available.
- The UI should distinguish `session_expired` from scan failure.

### Upstream Fetch Errors

- Any failure to fetch tab metadata or tab payloads marks the run failed.
- No partial publish occurs.
- Status endpoint exposes the error for the frontend.

### Pricing Errors

- Item-level pricing fallback is allowed only when the pricing stack still returns a concrete structured estimate for that item, including a predicted value plus fallback or trust metadata.
- Every published stash item must have a non-null valuation payload. A scan that cannot produce a concrete estimate for one or more items must fail rather than publish a partially priced snapshot.
- Backend-wide pricing unavailability should fail the scan rather than silently publishing unpriced data.

### Concurrent Scan Requests

- Duplicate active scans for the same account scope must be prevented.
- The frontend can disable `Scan` while status is active, but backend enforcement is still required.

## Security And Privacy

- Continue storing only the server-side `POESESSID` needed for private stash access.
- Do not persist or expose browser-specific cookies unrelated to the feature.
- Do not send `POESESSID` back to the frontend after bootstrap.
- Scope all stash reads and scan operations to the authenticated account session.

## Testing Strategy

### Backend Unit Tests

- private stash tab-list parsing and exact tab-order preservation,
- scan-run creation, progress updates, failure transitions, and atomic publish,
- published-read behavior while a new scan is running,
- item fingerprint stability and history query shape,
- API auth behavior for scan start, scan status, published tabs, and item history.

### Backend Integration-Style Unit Tests

- scan orchestration with stubbed private stash responses,
- per-item pricing normalization using the existing price-check contract,
- failed scan leaves published pointer unchanged,
- successful scan swaps the published pointer and updates freshness metadata.

### Frontend Tests

- stash tab renders ordered tabs from backend response,
- `Scan` button starts polling and disables appropriately,
- old published data stays visible during `running`,
- a completed publish refreshes the stash view once,
- item history popup renders estimate history and interval bands.

## Rollout Notes

- Reuse the current account-stash feature flag boundary rather than introducing a second feature family.
- Keep the existing stash endpoint readable for older snapshots until the new published-scan tables are populated.
- Prefer additive migrations and backward-compatible API expansion.

## Success Criteria

- A connected user can click `Scan` and trigger a private full-stash scan for `Mirage`.
- The backend fetches all account stash tabs, including non-public tabs, in upstream order.
- The frontend continues to receive the last published snapshot until the new scan fully completes.
- On success, the frontend receives a newly published ordered tab set with per-item pricing and interval fields.
- On failure, the frontend still receives the previous published snapshot.
- The frontend can fetch per-item estimate history suitable for a popup with error bands.
