# Learnings

- Canonical stash scan and valuation paths can stay handler-identical to the legacy aliases; only the route map naming and registration order need to change.
- The OpenAPI spec should keep the canonical result routes as the primary contract and mark `/api/v1/stash/tabs` plus `/api/v1/stash/scan/valuations` as deprecated aliases with matching summaries.
- Focused contract tests can stay small if they assert path presence, deprecation markers, and the exact response schema refs for the lifecycle routes.
2026-04-25: Canonical stash lifecycle coverage is strongest when it asserts both the route contract and the runtime header behavior on the accepted result paths.
2026-04-25: `stash_scan_status` can still resolve to `backend_unavailable` at the route layer even when the feature flag is disabled; route-level tests should pin the observed runtime branch, not the payload helper alone.
2026-04-25: In-process `ApiApp.handle()` smoke checks passed for `/api/v1/stash/scan/start`, `/api/v1/stash/scan`, `/api/v1/stash/scan/status`, `/api/v1/stash/scan/result`, `/api/v1/stash/tabs`, `/api/v1/stash/scan/valuations/status`, `/api/v1/stash/scan/valuations/result`, and `/api/v1/stash/scan/valuations`.
2026-04-25: Negative-path smoke confirmed `/api/v1/stash/tabs` without a session still raises `ApiError(status=401, code="auth_required")`.
2026-04-25: Oracle audit APPROVE — `poe_trade/api/app.py`, `poe_trade/api/ops.py`, `apispec.yml`, and the focused stash/spec tests match the plan's canonical route, legacy alias, OpenAPI, and regression objectives; extra `.sisyphus/*` worktree churn stayed outside product scope.
2026-04-25: Coverage split is clear, `tests/unit/test_apispec_contract.py` owns the OpenAPI checks for canonical result routes and deprecated aliases, `tests/unit/test_api_ops_routes.py` owns the route-map assertions, and `tests/unit/test_api_stash.py` plus `tests/unit/test_api_stash_valuations.py` own the runtime behavior checks.
2026-04-25: The spec test already covers path presence, deprecation markers, schema refs, response descriptions, and `503`/`404` response sets, so the likely follow-up edits are alias expectations and any ops contract strings that still present legacy paths as primary.

2026-04-25: `ApiApp._register_routes()` maps canonical stash lifecycle routes directly in `poe_trade/api/app.py` and keeps the legacy aliases on the same handlers: `/api/v1/stash/scan` -> `_stash_scan_start`, `/api/v1/stash/tabs` -> `_stash_tabs`, and `/api/v1/stash/scan/valuations` -> `_stash_scan_valuations`.
2026-04-25: There is no shared request parser between the valuations result route and the legacy POST alias; the POST alias goes through `_stash_scan_valuations_payload()` + `_stash_scan_valuations_request_body()`, while `GET /api/v1/stash/scan/valuations/result` calls `latest_stash_scan_valuations_payload()` directly.
2026-04-25: The ops contract keys already expose canonical and legacy stash paths in `poe_trade/api/ops.py`, and the current regression surface is `tests/unit/test_api_ops_routes.py`, `tests/unit/test_api_stash.py`, `tests/unit/test_api_stash_valuations.py`, and `tests/unit/test_apispec_contract.py`.

2026-04-25: A tiny typing-only cleanup in `tests/unit/test_api_stash_valuations.py` was enough to keep basedpyright green: typed helpers for the captured refresh payload and thread target fixed nested `object` access without changing runtime behavior.
