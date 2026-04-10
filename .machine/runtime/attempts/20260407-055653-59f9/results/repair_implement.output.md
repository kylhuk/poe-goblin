Implemented the stash valuation cache repair in the backend and added the missing regressions.

What changed:
- `poe_trade/api/app.py`
  - Start and status paths now verify `_PENDING_STASH_VALUATIONS[scope]` against the current `publishedScanId` before reusing it.
  - Stale pending entries are evicted instead of being reused.
  - Status lookup now resolves the current published scan before returning any cached payload.
- `poe_trade/stash_scan.py`
  - Added `fetch_latest_published_valuation_refresh_run(...)`.
  - Updated `fetch_valuation_refresh_status_payload(...)` to recover a `published` valuation refresh from persisted storage after cache loss/restart.
- `tests/unit/test_api_stash_valuations.py`
  - Added regressions for stale pending refresh reuse on both start and status routes.
  - Added a restart-style status test that clears in-memory valuation caches and proves the published refresh is recovered from persisted storage.
- `tests/unit/test_stash_scan.py`
  - Added helper-level coverage for the new published-scan lookup.
  - Added a restart-safe status payload regression.
- `.machine/runtime/Documentation.md`
  - Logged the repair progress and verification evidence.

Verification:
- `.venv/bin/pytest tests/unit/test_api_stash_valuations.py` — 40 passed
- `.venv/bin/pytest tests/unit/test_stash_scan.py` — 29 passed
- `.venv/bin/pytest tests/unit/test_account_stash_harvester.py tests/unit/test_api_stash.py tests/unit/test_api_stash_valuations.py tests/unit/test_apispec_contract.py tests/unit/test_migrations.py tests/unit/test_stash_scan.py tests/unit/test_valuation_helpers.py` — 161 passed
- `npx vitest run src/components/tabs/StashViewerTab.test.tsx src/services/api.stash.test.ts` — 14 passed

I left the unrelated dirty worktree files untouched.