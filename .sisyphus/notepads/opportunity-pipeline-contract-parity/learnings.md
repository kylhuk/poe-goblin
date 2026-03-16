
- Task 1: scanner recommendation metadata landed as additive nullable columns so legacy rows keep deserializing while new rows stamp provenance/version fields.
- Task 1: scanner cooldown reads now scope to `recommendation_contract_version = 2`, with legacy-query fallbacks so pre-migration tables do not hard-fail the worker or ops API.
- Task 1: ops contract/dashboard now expose a shared `deployment` shape early, with `recommendationContractVersion` populated and SHA fields left `null` until later deployment-plumbing work.
