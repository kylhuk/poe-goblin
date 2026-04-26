# Issues

2026-04-25: `tests/unit/test_api_ops_routes.py::test_stash_scan_result_route_translates_backend_unavailable` uses stash-disabled settings, so `_stash_tabs()` will fail with `feature_unavailable` before the monkeypatched backend error can surface. The test is pinned to the wrong runtime branch.

2026-04-25: `tests/unit/test_api_stash_valuations.py` defines `test_stash_scan_valuations_result_route_translates_backend_unavailable` twice. The earlier copy is shadowed and never collected, so one intended assertion path is lost.

2026-04-25: Repair pass confirmed the scan-result backend-unavailable route test is exercising the enabled stash branch, and the valuations file now has only one collected backend-unavailable test after dropping the duplicate plus a small helper cast cleanup.

2026-04-25 final-wave review: APPROVE. The scan-result backend-unavailable regression now exercises the enabled stash branch, grep shows only one collected `test_stash_scan_valuations_result_route_translates_backend_unavailable`, and diagnostics on the reviewed tests show no errors beyond existing warnings.

- 2026-04-25 scope fidelity (F4): APPROVE for scope. Touched product files stayed inside the planned routing/OpenAPI/tests surface (`poe_trade/api/app.py`, `poe_trade/api/ops.py`, `apispec.yml`, and stash/OpenAPI test modules). No valuation algorithm, storage/schema, auth-flow redesign, or unrelated product modules changed. Note: diagnostics flagged a duplicate test declaration in `tests/unit/test_api_stash_valuations.py`; this is a QA concern, not scope creep. Unrelated planning/orchestration artifacts (`.sisyphus/*`, `roller-plan.md`) were excluded from the runtime-scope verdict.

2026-04-25: The valuation regression file had a few nested `captured[...]` lookups inferred as `object`; wrapping them in typed helpers/casts was necessary to satisfy diagnostics before verification could pass.
