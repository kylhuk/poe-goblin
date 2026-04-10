# Follow-up tasks

Record useful but non-required follow-up work here instead of implementing it during the current task.

- Add a stash-specific repro script under `.machine/runtime/repros/` that exercises `scan/start -> valuations/start -> valuations/result -> item history` against the local stack so final acceptance can use a Docker-backed product smoke instead of only targeted unit / vitest coverage.
- After the task lands, collapse the duplicated valuation-refresh cache reconciliation in `poe_trade/api/app.py` into a shared helper so start, status, and result cannot drift again; this cleanup is not required to finish the current task.
- Add a narrow unit test that proves `run_private_scan()` writes the initial running lifecycle row and active-scan row before any remote stash traversal begins; the current matrix covers this behavior indirectly through a broader publication-path test.
- Audit and trim the current frontend harness dependency churn (`package.json`, `package-lock.json`, `.npmrc`, `vitest.config.ts`) once the stash-viewer behavior is stable; that cleanup is not required to complete this task.
- Add a small runtime helper that compares `git diff --name-only` against `.machine/runtime/VerificationPlan.json` `allowed_paths` so scope-compliance can be machine-checked during acceptance.
- Extend the runtime guard scripts so they also validate that every referenced pytest and vitest selector exists in the live tree; this planning pass found stale selector drift that the current guards did not catch.
- Remove duplicated frontend price-evaluation fallback logic once backend `priceEvaluation` is guaranteed on every stash/history path; this task only preserves backend labels and keeps the local fallback as a compatibility path.
- Consolidate duplicated chaos-normalization and local price-derivation helpers across `poe_trade/stash_scan.py`, `poe_trade/api/valuation.py`, and `src/components/tabs/StashViewerTab.tsx` after this task lands; the current task freezes behavior and proof first.
- Add a seeded local-stack latency smoke or ClickHouse sanity query that proves `published scan -> latest items` and `fingerprint -> history` reads stay fast on realistic data volumes; this task freezes correctness, retention, and query-path shape but does not benchmark performance.
- Backfill or migrate older published scans until persisted valuation refresh no longer needs any compatibility fallback from `account_stash_item_valuations`; this task keeps the fallback path because the rollout is additive.
