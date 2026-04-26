# PoE-Goblin Phase 1 - Game Data Ingestion and Ontology

## TL;DR
> **Summary**: Implement the Phase 1 foundation from `roller-plan.md` only: current-game data ingestion, stat/mod ontology, passive tree and ascendancy modeling, item possibility modeling, gem/config modeling, and league-mechanics registry. This is a data/contracts phase, not optimizer, pricing, PoB round-trip, or UI/API work.
> **Deliverables**: deterministic ingestion modules, canonical ontology package, additive schema updates where needed, focused unit/contract tests, and coverage for Mirage-era mechanics and version-gated fixtures.
> **Effort**: XL
> **Parallel**: YES - 5 waves
> **Critical Path**: ingest/validate 3.28 data → ontology primitives → tree/ascendancy → item/gem/mechanics models → regression/coverage verification

## Context
### Original Request
The request is to create a Sisyphus plan that focuses only on **Phase 1** of `roller-plan.md` after Phase 0 is already implemented.

### Interview Summary
- Phase 1 covers only the game-data and ontology backlog from `roller-plan.md` (`P1-E1` through `P1-E5`).
- Repo conventions discovered during planning:
  - source/workflow code lives under `poe_trade/ingestion/`
  - canonical typed contracts tend to be small frozen dataclasses or tiny contract modules
  - tests are mostly local pytest modules with file-local doubles and exact assertions
  - schema evolution is append-only and layered
- Phase 1 should stay as data/modeling work only. Optimizer, pricing, PoB runtime, API/UI exposure, and later-phase search engines stay out of scope.
- Official source rules are guardrails for any live-data integration: OAuth/documented endpoints only, eventual consistency for public feeds, and no real-time/freshness claims without direct browser verification.
- PoB remains a downstream oracle, not an exhaustive truth source: unsupported/red modifiers must lower confidence rather than silently normalize.

### Metis Review (gaps addressed)
- Added explicit package boundaries: `poe_trade/ingestion/` for source/workflow code and a new typed ontology package for canonical game-data models if needed.
- Added explicit guardrails to keep Phase 1 from drifting into later phases: no optimizer logic, no pricing service, no UI/API exposure, no full PoB round-trip implementation.
- Added explicit version-policy assumptions: current-game data is 3.28/Mirage scoped, and anything ambiguous or unsupported must be surfaced as a warning/error rather than silently accepted.
- Added a task decomposition that follows the actual Phase 1 epics instead of a vague “implement data layer” story.

## Work Objectives
### Core Objective
Build the Phase 1 data foundation for the optimizer: ingest current 3.28 game data, normalize it into canonical ontology types, and cover the important mechanics that later phases will consume.

### Deliverables
- Ingestion of current game data and schema validation.
- Canonical stat/mod translation and parser drift coverage.
- Passive tree, ascendancy, mastery, tattoo, and runegraft models.
- Base item, legality, unique, flask, jewel, cluster, and Timeless Jewel models.
- Gem catalog, compatibility, and skill configuration models.
- League-mechanics registry with Mirage-era coverage.
- Focused unit/contract tests for each domain.

### Definition of Done (verifiable conditions with commands)
- `.venv/bin/pytest tests/unit` passes.
- Focused module tests for the touched Phase 1 areas pass.
- `make ci-deterministic` passes if shared contracts/migrations are added.
- Any new migration files are applied and covered by `tests/unit/test_migrations.py` patterns.

### Must Have
- Preserve Phase 0 outputs as the only source-policy foundation.
- Keep all Phase 1 behavior deterministic and version-gated.
- Use additive schema evolution only.
- Keep tests local, explicit, and fixture-driven.
- Model unsupported/ambiguous mechanics explicitly.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No optimizer search engine, Pareto frontier, or scoring work.
- No pricing service, market lookup, or budget feasibility logic.
- No PoB runtime/oracle implementation or Build IR round-trip.
- No UI/API exposure work.
- No “magic” one-off exceptions without source metadata and tests.
- No broad new testing framework or property/snapshot infrastructure if the repo does not already use it.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: **tests-first / contract-first** for every Phase 1 task.
- QA policy: every task includes a happy path and a negative/edge path.
- Evidence: `.sisyphus/evidence/phase1-task-{N}-{slug}.md` and `.sisyphus/evidence/phase1-task-{N}-{slug}-error.md`.

## Execution Strategy
### Parallel Execution Waves
> Target: 5 waves. Wave 1 creates the ingestion/ontology foundation; later waves fan out across tree, items, gems, and mechanics once the shared primitives exist.

Wave 1: current-data ingestion + stat/mod ontology

Wave 2: passive tree + ascendancy + mastery/tattoo/runegraft models

Wave 3: base items + legality + uniques + flasks/jewels/cluster/Timeless models

Wave 4: gem catalog + compatibility + skill config models

Wave 5: league-mechanics registry + Mirage-era coverage

### Dependency Matrix (full, all tasks)
- Task 1 blocks Task 2.
- Task 2 blocks Tasks 3-12.
- Task 3 blocks Tasks 4-5.
- Task 6 blocks Tasks 7-9.
- Task 10 blocks Task 11.
- Task 12 depends on Tasks 2, 5, 6, 9, and 10 being in place.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 2 tasks → deep, unspecified-high
- Wave 2 → 3 tasks → deep
- Wave 3 → 4 tasks → unspecified-high
- Wave 4 → 2 tasks → unspecified-high
- Wave 5 → 1 task → deep

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. `poe_trade/ingestion/game_data_ingestor.py` + `poe_trade/ingestion/repoe_loader.py` + `schema/migrations/0035_game_data_ingestion.sql` + `tests/unit/test_game_data_ingestor.py`: ingest current 3.28 game data and validate the source payloads before they reach the ontology layer

  **What to do**: Pull the Phase 1 game-data export set (RePoE/PyPoE/current patch exports) into a deterministic ingestion module that validates checksums, validates required tables/sections, and writes additive schema/contracts for the canonical raw/normalized rows. Reject non-3.28 exports and malformed source payloads up front; generate a data-quality report for missing/unknown references.

  **Must NOT do**: Do not build PoB evaluation, candidate search, or pricing logic here. Do not invent source-policy rules; consume the Phase 0 source registry/policy layer. Do not hard-code mechanics that should come from the export.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: ingestion pipeline, schema, and validation rules cross multiple files.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ingestion/market_harvester.py` - source/workflow ingestion style with queue/checkpoint/status writes.
  - Pattern: `poe_trade/ingestion/cxapi_sync.py` - source-specific ingest contract with deterministic state writes.
  - Pattern: `poe_trade/ingestion/account_stash_harvester.py` - payload normalization and scan lifecycle style.
  - Pattern: `poe_trade/ingestion/sync_contract.py` - tiny contract-module pattern.
  - Pattern: `poe_trade/ingestion/sync_state.py` - compact state dataclass + DB lookup style.
  - Pattern: `schema/migrations/0022_queue_based_ingest_telemetry.sql` - additive telemetry contract pattern.
  - Pattern: `schema/migrations/0023_queue_based_ingest_views.sql` - view layering over raw ingestion state.
  - Pattern: `schema/migrations/0034_account_stash_items.sql` - source-specific silver storage pattern.
  - Pattern: `tests/unit/test_account_stash_harvester.py` - local fixture-heavy ingest tests.
  - Pattern: `tests/unit/test_cxapi_sync.py` - deterministic source ingestion contract tests.
  - Pattern: `tests/unit/test_migrations.py` - migration runner contract and ordering checks.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Valid 3.28 export fixtures ingest successfully and persist the expected normalized rows.
  - [ ] Non-3.28 or malformed source payloads fail with explicit errors.
  - [ ] Checksums/source metadata are recorded for every ingested source artifact.
  - [ ] The ingestion path produces a readable data-quality report for missing references.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Ingest valid 3.28 export
    Tool: Bash
    Steps: Run the focused ingestion tests for the new loader module against a known-good 3.28 fixture.
    Expected: The ingestion succeeds, writes expected normalized rows, and reports no schema violations.
    Evidence: .sisyphus/evidence/phase1-task-1-game-data.md

  Scenario: Reject wrong-version export
    Tool: Bash
    Steps: Run the same ingestion path with a 3.27 or malformed fixture.
    Expected: The run fails deterministically with a version/schema error and no downstream writes.
    Evidence: .sisyphus/evidence/phase1-task-1-game-data-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/ingestion/game_data_ingestor.py, poe_trade/ingestion/repoe_loader.py, schema/migrations/0035_game_data_ingestion.sql, tests/unit/test_game_data_ingestor.py]

- [ ] 2. `poe_trade/game_ontology/stats.py` + `poe_trade/game_ontology/modifiers.py` + `poe_trade/game_ontology/stat_translation.py` + `tests/unit/test_stat_ontology.py` + `tests/unit/test_stat_translation.py`: create the canonical stat/mod ontology and translation layer used by later Phase 1 models

  **What to do**: Define normalized stat and modifier dataclasses, value ranges, alias handling, and translation patterns for numeric/range/signed/conditional mod lines. Add ambiguity reporting, unknown-line tracking, and explicit unsupported-stat registration.

  **Must NOT do**: Do not build item legality, tree pathing, or any optimizer-facing metric aggregation here. Keep the module as the canonical ontology/translation layer only.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: shared domain model and parser semantics affect every later model.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [3, 4, 5, 6, 7, 8, 9, 10, 11, 12] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ml/contract.py` - frozen dataclass / constant contract style.
  - Pattern: `poe_trade/config/constants.py` - stable identifiers and enums by constant.
  - Pattern: `tests/unit/test_sync_contract.py` - exact contract assertions.
  - Pattern: `tests/unit/test_sync_state.py` - narrow DB-boundary assertions.
  - Pattern: `tests/unit/test_market_harvester.py` - deterministic fixture and negative-path style.
  - Pattern: `tests/unit/test_migrations.py` - data-contract evolution checks.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Every supported stat/mod shape has a canonical normalized representation.
  - [ ] Ambiguous translation lines are reported, not silently misparsed.
  - [ ] Unknown/unsupported lines are tracked explicitly.
  - [ ] The ontology module round-trips through its own serialization without losing required fields.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Translate supported mod lines
    Tool: Bash
    Steps: Run the stat-translation unit tests over simple numeric, range, signed, percentage, and conditional lines.
    Expected: Known lines map to the expected normalized stat IDs and value ranges.
    Evidence: .sisyphus/evidence/phase1-task-2-stat-ontology.md

  Scenario: Flag ambiguous or unknown lines
    Tool: Bash
    Steps: Run the same translator against intentionally ambiguous and unsupported fixture lines.
    Expected: The module reports ambiguity/unsupported status and does not invent a canonical mapping.
    Evidence: .sisyphus/evidence/phase1-task-2-stat-ontology-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/stats.py, poe_trade/game_ontology/modifiers.py, poe_trade/game_ontology/stat_translation.py, tests/unit/test_stat_ontology.py, tests/unit/test_stat_translation.py]

- [ ] 3. `poe_trade/game_ontology/passive_tree.py` + `poe_trade/game_ontology/tree_pathing.py` + `tests/unit/test_passive_tree_graph.py` + `tests/unit/test_tree_pathing.py`: load the versioned passive tree JSON and add valid path/edit-distance utilities

  **What to do**: Build a strict passive-tree graph loader, reject stale tree versions, expose shortest-path and k-shortest-path utilities, and add tree edit-distance helpers for later optimizers. Keep the implementation graph-centric and version-gated; no build search or optimizer scoring yet.

  **Must NOT do**: Do not add optimizer candidate generation or PoB validation. Do not accept tree sources whose version does not match the active game version.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: graph modeling and version-gated path utilities are foundational and cross-cutting.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [] | Blocked By: [2]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ml/contract.py` - frozen dataclass contract style.
  - Pattern: `schema/migrations/0002_bronze.sql` - baseline layered data storage.
  - Pattern: `schema/migrations/0003_silver.sql` - normalized storage pattern.
  - Pattern: `schema/migrations/0004_gold.sql` - derived/current view pattern.
  - Pattern: `tests/unit/test_migrations.py` - migration/test ordering and SQL splitting pattern.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Valid 3.28 passive tree JSON loads successfully into a graph model.
  - [ ] Version-mismatched tree data is rejected deterministically.
  - [ ] Shortest-path and k-shortest-path helpers return legal connected paths.
  - [ ] Tree edit-distance helpers are symmetric where expected and stable across repeated runs.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Load and path a current tree
    Tool: Bash
    Steps: Run the passive-tree graph tests using a 3.28 tree fixture and request a target notable path.
    Expected: The graph loads and returns legal connected paths within the expected point budget.
    Evidence: .sisyphus/evidence/phase1-task-3-tree-graph.md

  Scenario: Reject stale tree data
    Tool: Bash
    Steps: Repeat with a stale or mismatched tree export.
    Expected: The loader fails with a version mismatch error and no path utility runs on invalid data.
    Evidence: .sisyphus/evidence/phase1-task-3-tree-graph-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/passive_tree.py, poe_trade/game_ontology/tree_pathing.py, tests/unit/test_passive_tree_graph.py, tests/unit/test_tree_pathing.py]

- [ ] 4. `poe_trade/game_ontology/ascendancy.py` + `tests/unit/test_ascendancy_model.py`: model class/ascendancy mappings, point limits, and special ascendancy mechanics

  **What to do**: Add base-class to ascendancy mappings, ascendancy passive point limits, Scion behavior, the 3.28 Reliquarian, and legacy/standard variants. Model rejectable cases explicitly so later build generators can reason about them without guessing.

  **Must NOT do**: Do not implement any ascendancy-dependent optimizer logic or passive-tree search heuristics here.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: ascendancy constraints are tightly coupled to the passive-tree model.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [] | Blocked By: [2, 3]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ml/contract.py` - typed contract style.
  - Pattern: `tests/unit/test_sync_contract.py` - small exact contract checks.
  - Pattern: `tests/unit/test_ml_v3_routes.py` - behavior statement naming style.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Every base class maps to the correct ascendancy options.
  - [ ] Scion and Reliquarian cases are represented and validated.
  - [ ] Passive-point limits are enforced.
  - [ ] Impossible ascendancy allocations are rejected with explicit errors.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Validate a legal ascendancy mapping
    Tool: Bash
    Steps: Run the ascendancy model tests against known valid class/ascendancy pairs.
    Expected: The model accepts the mapping and reports the correct point limit.
    Evidence: .sisyphus/evidence/phase1-task-4-ascendancy.md

  Scenario: Reject impossible ascendancy allocation
    Tool: Bash
    Steps: Run the tests with an invalid class/ascendancy pair.
    Expected: The model rejects the pair with a deterministic validation error.
    Evidence: .sisyphus/evidence/phase1-task-4-ascendancy-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/ascendancy.py, tests/unit/test_ascendancy_model.py]

- [ ] 5. `poe_trade/game_ontology/masteries.py` + `poe_trade/game_ontology/tattoos.py` + `poe_trade/game_ontology/runegrafts.py` + `tests/unit/test_masteries.py` + `tests/unit/test_tattoos.py` + `tests/unit/test_runegrafts.py`: represent mastery, tattoo, and runegraft legality as versioned tree transformations

  **What to do**: Model mastery allocation constraints, tattoo eligibility/limits, and runegraft eligibility/uniqueness as tree transformations that can be validated independently. Keep PoB round-trip references as fixtures only; do not create a PoB runtime.

  **Must NOT do**: Do not implement tree optimizer search or item pricing. Do not bypass the 50 tattoo limit or one-of-type runegraft rule.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: these mechanics are tree-adjacent and share validation rules.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [] | Blocked By: [3, 4]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ml/contract.py` - frozen dataclass and constant contract style.
  - Pattern: `tests/unit/test_migrations.py` - additive contract evolution.
  - Pattern: `tests/unit/test_sync_state.py` - exact validation semantics around state lookups.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Mastery allocation rules are enforced consistently.
  - [ ] Tattoo application is limited to eligible allocated passives and respects the 50 tattoo limit.
  - [ ] Runegraft application is limited to eligible mastery passives and one-of-type constraints are enforced.
  - [ ] Illegal combinations are rejected rather than normalized away.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Apply legal tattoo/runegraft transformations
    Tool: Bash
    Steps: Run the masteries/tattoos/runegrafts tests against legal fixtures.
    Expected: Legal transformations succeed and produce the expected transformed tree metadata.
    Evidence: .sisyphus/evidence/phase1-task-5-tree-transformations.md

  Scenario: Reject illegal transformation combinations
    Tool: Bash
    Steps: Run the same tests with an over-limit tattoo fixture or duplicate runegraft type.
    Expected: The validator rejects the combination with a clear error.
    Evidence: .sisyphus/evidence/phase1-task-5-tree-transformations-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/masteries.py, poe_trade/game_ontology/tattoos.py, poe_trade/game_ontology/runegrafts.py, tests/unit/test_masteries.py, tests/unit/test_tattoos.py, tests/unit/test_runegrafts.py]

- [ ] 6. `poe_trade/game_ontology/items/base_items.py` + `poe_trade/game_ontology/item_states.py` + `tests/unit/test_base_items.py` + `tests/unit/test_item_states.py`: define canonical base-item metadata and legal item-state transitions

  **What to do**: Model item base definitions, item class compatibility, attribute requirements, and state flags such as rarity, identified, corrupted, mirrored, split, fractured, synthesized, influenced, eldritch, veiled, enchanted, crafted, quality, sockets, and links. Reject illegal combinations and preserve legacy/permanent-league variants.

  **Must NOT do**: Do not estimate price or generate market candidates here. Do not introduce optimizer-specific item scoring.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: item model breadth is large and impacts later candidate generation.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [] | Blocked By: [2]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ingestion/account_stash_harvester.py` - item-shape handling from source payloads.
  - Pattern: `poe_trade/ingestion/market_harvester.py` - item/source metadata and deterministic state.
  - Pattern: `tests/unit/test_account_stash_harvester.py` - local fixture-heavy item assertions.
  - Pattern: `tests/unit/test_market_harvester.py` - exact state/row assertions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Base-item compatibility and requirement rules are canonicalized.
  - [ ] Illegal item-state combinations are rejected deterministically.
  - [ ] Legacy/permanent-league variants remain representable.
  - [ ] State transitions are reversible only where the game rules allow it.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Validate a legal item state
    Tool: Bash
    Steps: Run the base-item/item-state tests against a valid item fixture.
    Expected: The model accepts the item and preserves all required metadata.
    Evidence: .sisyphus/evidence/phase1-task-6-item-model.md

  Scenario: Reject an impossible item state
    Tool: Bash
    Steps: Run the same tests with a corrupted + mirrored + split combination or other impossible state.
    Expected: Validation fails with a clear state-combination error.
    Evidence: .sisyphus/evidence/phase1-task-6-item-model-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/items/base_items.py, poe_trade/game_ontology/item_states.py, tests/unit/test_base_items.py, tests/unit/test_item_states.py]

- [ ] 7. `poe_trade/game_ontology/mod_applicability.py` + `poe_trade/game_ontology/rare_candidate_generation.py` + `tests/unit/test_mod_applicability.py` + `tests/unit/test_rare_candidate_generation.py`: encode affix legality and deterministic rare-item candidate generation

  **What to do**: Implement `canApplyMod(...)`, prefix/suffix count checks, domain and influence restrictions, and deterministic rare-item candidate generation that emits legality proof metadata. Candidate generation should be constrained and plausible; it must not enumerate the full rare-item space.

  **Must NOT do**: Do not build a pricing model, acquisition planner, or optimizer ranking. Do not accept illegal affix combinations.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: legality rules and candidate generation are broad and combinatorial.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [] | Blocked By: [6, 2]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ml/contract.py` - immutable contract style for candidate metadata.
  - Pattern: `tests/unit/test_sync_contract.py` - exact rule/contract assertions.
  - Pattern: `tests/unit/test_ml_v3_sql_contract.py` - schema-like contract testing style.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Affix legality is enforced by base tags, item class, item level, domain, generation type, and influence restrictions.
  - [ ] Prefix/suffix count limits are enforced.
  - [ ] Rare candidate generation is deterministic under a fixed seed.
  - [ ] Each candidate carries a legality proof or explanation payload.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Generate a legal rare candidate set
    Tool: Bash
    Steps: Run the rare-candidate generator tests against a constrained slot/base fixture.
    Expected: The generator returns plausible legal candidates and proof metadata.
    Evidence: .sisyphus/evidence/phase1-task-7-affix-legality.md

  Scenario: Reject an illegal affix combination
    Tool: Bash
    Steps: Re-run with an impossible base-tag or prefix/suffix configuration.
    Expected: The validator refuses the candidate instead of normalizing it.
    Evidence: .sisyphus/evidence/phase1-task-7-affix-legality-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/mod_applicability.py, poe_trade/game_ontology/rare_candidate_generation.py, tests/unit/test_mod_applicability.py, tests/unit/test_rare_candidate_generation.py]

- [ ] 8. `poe_trade/game_ontology/uniques.py` + `tests/unit/test_unique_items.py`: model unique items, roll ranges, variants, and obtainability/legacy state

  **What to do**: Ingest unique-item definitions with roll ranges and variant IDs, represent current obtainability versus legacy/unobtainable variants, and support exact/min/max/median roll instantiation for later consumers.

  **Must NOT do**: Do not add price lookup or acquisition planning. Do not collapse variant data into a single flat record.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: unique-item modeling has many edge cases and legacy states.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [] | Blocked By: [6]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ingestion/account_stash_harvester.py` - item normalization and source metadata.
  - Pattern: `tests/unit/test_account_stash_harvester.py` - fixture-driven item assertions.
  - Pattern: `poe_trade/ml/contract.py` - frozen dataclass contract style.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Unique items retain roll-range and variant metadata.
  - [ ] Current versus legacy/unobtainable status is explicit.
  - [ ] Exact/min/max/median roll instantiation is deterministic.
  - [ ] Variant selection does not discard source metadata.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Instantiate a current unique variant
    Tool: Bash
    Steps: Run the unique-item tests against a current 3.28 unique fixture.
    Expected: The model retains the correct roll range and variant metadata.
    Evidence: .sisyphus/evidence/phase1-task-8-uniques.md

  Scenario: Mark a legacy/unobtainable variant
    Tool: Bash
    Steps: Re-run with a legacy variant fixture.
    Expected: The model marks the variant as legacy/unobtainable without losing roll metadata.
    Evidence: .sisyphus/evidence/phase1-task-8-uniques-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/uniques.py, tests/unit/test_unique_items.py]

- [ ] 9. `poe_trade/game_ontology/flasks.py` + `poe_trade/game_ontology/jewels.py` + `poe_trade/game_ontology/cluster_jewels.py` + `poe_trade/game_ontology/timeless_jewels.py` + `tests/unit/test_flasks.py` + `tests/unit/test_jewels.py` + `tests/unit/test_cluster_jewels.py` + `tests/unit/test_timeless_jewels.py`: model flasks, regular/abyss jewels, cluster jewels, and Timeless Jewels as legality-preserving item families

  **What to do**: Implement legal models for flasks, jewels, cluster jewels, and Timeless Jewels, including 3.28 additions like Heroic Tragedy. Keep socket/radius/state constraints explicit, and preserve source metadata for later consumers.

  **Must NOT do**: Do not implement pricing, optimizer search, or PoB validation runtime. If PoB fixture data is needed, keep it in the test layer only.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: several non-gear item families interact and have many constraints.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [] | Blocked By: [6, 3]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ingestion/account_stash_harvester.py` - non-gear item normalization style.
  - Pattern: `tests/unit/test_account_stash_harvester.py` - local fixtures for item-family coverage.
  - Pattern: `schema/migrations/0034_account_stash_items.sql` - stash-backed item storage contract.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Flask, jewel, cluster, and Timeless Jewel models carry the constraints required for legality checks.
  - [ ] Cluster jewels preserve base/passive-count/notable/socket metadata.
  - [ ] Timeless Jewels preserve seed/socket/radius transformation metadata.
  - [ ] 3.28 additions (including Heroic Tragedy) are represented in fixtures and contracts.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Validate legal flask/jewel/cluster/timeless fixtures
    Tool: Bash
    Steps: Run the family-specific unit tests against legal fixtures for each item family.
    Expected: Every family validates and preserves source metadata.
    Evidence: .sisyphus/evidence/phase1-task-9-item-families.md

  Scenario: Reject an illegal family-specific fixture
    Tool: Bash
    Steps: Re-run with a bad socket/radius/passive-count/state fixture for one of the item families.
    Expected: The model rejects the fixture with a clear legality error.
    Evidence: .sisyphus/evidence/phase1-task-9-item-families-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/flasks.py, poe_trade/game_ontology/jewels.py, poe_trade/game_ontology/cluster_jewels.py, poe_trade/game_ontology/timeless_jewels.py, tests/unit/test_flasks.py, tests/unit/test_jewels.py, tests/unit/test_cluster_jewels.py, tests/unit/test_timeless_jewels.py]

- [ ] 10. `poe_trade/game_ontology/gems.py` + `poe_trade/game_ontology/gem_compatibility.py` + `tests/unit/test_gem_catalog.py` + `tests/unit/test_gem_compatibility.py`: ingest the skill gem catalog and encode support compatibility rules

  **What to do**: Model active and support gems with tags, levels, qualities, transfigured variants, Vaal variants, Exceptional Support Gems, and Imbued gem mechanics. Add compatibility rules that determine whether a support can affect an active skill by tags and restrictions.

  **Must NOT do**: Do not add skill configuration UI/API surfaces. Do not implement optimizer-facing DPS calculations.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: gem compatibility is a shared rule layer with many special cases.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: [] | Blocked By: [2]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ml/contract.py` - frozen dataclass style for canonical catalogs.
  - Pattern: `tests/unit/test_ml_v3_sql_contract.py` - exact schema/contract assertions.
  - Pattern: `tests/unit/test_market_harvester.py` - deterministic fixture semantics.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Gem catalog entries preserve all required versioned metadata.
  - [ ] Support-compatibility rules are tag- and restriction-aware.
  - [ ] Exceptional Support Gems and Imbued gem mechanics are represented.
  - [ ] Unsupported or special-case gem behavior is explicitly flagged.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Load and validate current gem catalog
    Tool: Bash
    Steps: Run the gem catalog tests against a 3.28 fixture set.
    Expected: The catalog loads and exposes the expected gem metadata.
    Evidence: .sisyphus/evidence/phase1-task-10-gems.md

  Scenario: Reject an unsupported compatibility pairing
    Tool: Bash
    Steps: Run the compatibility tests with a support/active pair that should not match.
    Expected: The compatibility layer rejects the pairing and flags the reason.
    Evidence: .sisyphus/evidence/phase1-task-10-gems-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/gems.py, poe_trade/game_ontology/gem_compatibility.py, tests/unit/test_gem_catalog.py, tests/unit/test_gem_compatibility.py]

- [ ] 11. `poe_trade/game_ontology/skill_config.py` + `poe_trade/game_ontology/config_warnings.py` + `tests/unit/test_skill_config.py` + `tests/unit/test_config_warnings.py`: define the skill configuration schema and completeness scoring for model consumers

  **What to do**: Create the canonical skill-configuration schema for stages, projectiles, overlaps, traps/mines, totems, minions, brands, ailments, poison stacks, bleed, ignite, exposure, rage, charges, warcries, and triggered skills. Add missing-config scoring and warning metadata so later phases can surface the right assumptions.

  **Must NOT do**: Do not expose warnings through the API/UI yet. Do not add build scoring or optimizer output logic.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: configuration completeness has many edge cases and special defaults.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: [] | Blocked By: [10]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/ml/contract.py` - typed contract definition style.
  - Pattern: `tests/unit/test_sync_contract.py` - stable contract assertions.
  - Pattern: `tests/unit/test_market_harvester.py` - file-local helper conventions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] The config schema captures the full Phase 1 skill-config surface.
  - [ ] Missing/important config fields lower confidence and emit warning metadata.
  - [ ] Skill-specific defaults are explicit and test-covered.
  - [ ] No API/UI exposure is required for the Phase 1 milestone.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Validate a complete skill config
    Tool: Bash
    Steps: Run the skill-config tests against a fully specified configuration fixture.
    Expected: The schema accepts the fixture and the warning score is neutral.
    Evidence: .sisyphus/evidence/phase1-task-11-config.md

  Scenario: Flag an incomplete skill config
    Tool: Bash
    Steps: Re-run with a fixture that omits an important skill assumption.
    Expected: The model records a warning and lowers confidence without inventing defaults.
    Evidence: .sisyphus/evidence/phase1-task-11-config-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/skill_config.py, poe_trade/game_ontology/config_warnings.py, tests/unit/test_skill_config.py, tests/unit/test_config_warnings.py]

- [ ] 12. `poe_trade/game_ontology/league_mechanics.py` + `poe_trade/game_ontology/mirage_features.py` + `tests/unit/test_league_mechanics.py` + `tests/unit/test_mirage_features.py`: classify league mechanics and explicitly cover the Mirage-era mechanics that affect build legality or acquisition

  **What to do**: Build a registry that classifies mechanics by impact category (direct build stat, item generation, acquisition/cost, map-only, encounter-only, legacy-only) and add metadata for 3.28 Mirage-era mechanics and related fixtures. Keep the registry explicit about unsupported or mixed-role mechanics.

  **Must NOT do**: Do not collapse mechanics into optimizer logic or price estimation. Do not add UI visibility work here.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: the registry is a cross-cutting classification layer with broad coverage requirements.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: [] | Blocked By: [2, 5, 6, 9, 10]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/config/constants.py` - stable identifiers and categories by constant.
  - Pattern: `poe_trade/ml/contract.py` - immutable contract model.
  - Pattern: `tests/unit/test_sync_contract.py` - exact registry-like assertions.
  - Pattern: `tests/unit/test_apispec_contract.py` - coverage-style contract checks.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Mechanics are classified into the intended categories and source metadata is preserved.
  - [ ] Mirage-era mechanics and 3.28 fixture data are represented explicitly.
  - [ ] Unsupported or mixed-role mechanics are flagged rather than hidden.
  - [ ] The registry can produce a coverage report for Phase 1 mechanics.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Classify supported league mechanics
    Tool: Bash
    Steps: Run the league-mechanics tests against a current 3.28 mechanic fixture set.
    Expected: Each mechanic is classified into the expected category and source metadata is retained.
    Evidence: .sisyphus/evidence/phase1-task-12-mechanics.md

  Scenario: Flag unsupported or mixed-role mechanics
    Tool: Bash
    Steps: Re-run with a mechanic fixture that is unsupported or spans multiple categories.
    Expected: The registry flags the ambiguity instead of silently classifying it.
    Evidence: .sisyphus/evidence/phase1-task-12-mechanics-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/game_ontology/league_mechanics.py, poe_trade/game_ontology/mirage_features.py, tests/unit/test_league_mechanics.py, tests/unit/test_mirage_features.py]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Planning output only; do not commit implementation code while this Phase 1 plan is being authored.
- When implementation begins later, keep commits aligned to the task waves above and avoid cross-wave mixing.

## Success Criteria
- The Phase 1 plan covers only `roller-plan.md` Phase 1 work and excludes Phases 0 and 2-10.
- Every Phase 1 task has explicit files, acceptance criteria, and QA scenarios.
- The plan preserves repo conventions and defers optimizer/pricing/UI work to later phases.
- The plan is ready for execution without additional judgment calls.
