Added red tests in:
- [tests/unit/test_apispec_contract.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_apispec_contract.py)
- [tests/unit/test_api_stash_valuations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_api_stash_valuations.py)
- [src/components/tabs/StashViewerTab.test.tsx](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/components/tabs/StashViewerTab.test.tsx)

What the new failures cover:
- Explicit OpenAPI schema properties for published stash payloads, valuation refresh lifecycle metadata, and item history price-quality fields.
- Refresh start payload fields for `scanKind` and `sourceScanId`.
- Viewer history dialog surfacing backend price quality text.

Objective failure evidence:
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_apispec_contract.py -k 'published_stash_result_fields or valuation_refresh_lifecycle_metadata or item_history_price_quality_fields'`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_api_stash_valuations.py -k 'start_payload_exposes_refresh_lifecycle_metadata'`
- `bash .machine/runtime/bin/vitest_cmd.sh run src/components/tabs/StashViewerTab.test.tsx -t 'shows backend price quality inside the item history dialog'`

These are still red, as intended for the TDD test-authoring pass.