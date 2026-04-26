# Decisions

- Kept all stash backend helpers and auth/session gating untouched.
- Exposed explicit canonical scan/valuation route keys in the ops contract and renamed legacy entries with `_legacy` suffixes for consistency.
- Aligned the OpenAPI wording with runtime by keeping canonical `/result` routes first and documenting the old aliases as deprecated, without adding new payload fields or headers.
2026-04-25: Kept the regression scope limited to unit tests, adding one canonical route failure check and CORS/header assertions on the accepted stash result and valuation routes instead of changing runtime wiring or OpenAPI docs.
