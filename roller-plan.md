# PoE-Goblin Build Optimizer - Verified Agentic Implementation Plan

Review date: 2026-04-25  
Target game: Path of Exile 1, v3.28.x / Mirage league  
Target delivery mode: test-driven, agent-coded, modular service implementation

## 1. Scope, caveats, and verification status

This document replaces a generic "research result" with a stricter implementation plan that is suitable for LLM agents. It is intentionally critical. The target is not a single machine-learning model that somehow "learns Path of Exile". The target is a deterministic, versioned build-optimization platform with machine learning used only where it is helpful: candidate ranking, search heuristics, similarity, price prediction, and archetype recommendation.

I could not inspect the connected repository in this run. The file/search connector reported no available sources, and the prior deep-research report was not exposed as text. Therefore, repository-specific work is described as integration contracts around the three features you said already exist: public stash scanning, account stash scanning, and the end-user web UI.

Verified public baseline:

- PoE 3.28 is Path of Exile: Mirage. The official 3.28.0 patch notes list the Mirage Challenge League, the new Scion Reliquarian ascendancy, Exceptional Support Gems, Coins that imbue level 20 gems with support effects, 10 new Runegrafts, 13 new unique items, endgame and passive-tree changes, and removal of Harbinger as a core league.
- The latest official 3.28 patch result found during this review is 3.28.0g, published in April 2026, with fixes for asynchronous trade, Mirage bugs, Sirus behavior outside Eye of the Storm, Infinite Hunger behavior, map description updates, and more.
- Path of Building Community is the practical calculation oracle. Its own README says it supports comprehensive offence and defence calculations, but also says it supports "most" passives and item modifiers, not literally every possible modifier. Unsupported modifiers are shown in red in PoB. That matters: the project must treat PoB as an oracle and track unsupported/differing mechanics explicitly.
- Current PoB release information found during this review includes v2.65.0 with fixes for cluster jewel crashes, Imbued gems, Imbued trigger supports, hidden gems, and buff application. The optimizer must therefore sync PoB frequently and run regression tests after each sync.
- GGG's official developer docs require OAuth 2.1 for most APIs, dynamic rate-limit handling, identifiable User-Agent headers, official scopes, and compliance with their API policies. Official docs also say that requests for access to undocumented internal APIs or game resources are denied, and reverse-engineering endpoints outside official docs violates their Terms of Use.
- Official API reference currently covers account stashes, account characters, league accounts, public stashes via `service:psapi`, and Currency Exchange via `service:cxapi`. Public stash results have a documented 5-minute delay. Currency Exchange data is hourly/historical and does not expose the current hour.
- RePoE fork currently exposes PoE 3.28.0.7 data and includes JSON for stats, mods, base items, cluster jewels, gem data, crafting bench options, fossils, essences, item classes, tags, stat translations, and more. It is a strong tool-development data source, but it is still a community/exported source and must be cross-checked against PoB and official patch data.
- The passive tree can be represented as JSON containing nodes, groups, assets, character data, connections, class IDs, ascendancy data, and related metadata. The GGG `skilltree-export` repository exists, but the implementation must reject any tree source whose version does not match the active game version.
- Tattoos, Runegrafts, Timeless Jewels, cluster jewels, Imbued Gems, Exceptional Support Gems, Reliquarian, 3.28 Mirage mechanics, and league-specific acquisition/cost effects must be modeled as versioned mechanics, not hard-coded one-off exceptions.

Primary sources used are listed at the end of this document.

## 2. Critical corrections to the initial idea

The following points should be treated as non-negotiable corrections before any code is written.

1. Do not build this as one monolithic ML model. PoE mechanics are rule-based, patch-sensitive, and full of exact edge cases. A model can rank, recommend, cluster, and approximate. It must not be the source of truth for item legality, skill calculations, tree validity, or currency cost.

2. Do not enumerate every possible rare item. The rare item space is effectively unbounded once item level, base type, influences, crafted mods, fractured mods, synth implicits, eldritch implicits, veiled mods, corruption states, enchantments, fossils, essences, recombination-style systems, league-specific changes, legacy states, and mod roll ranges are considered. The correct approach is a legality engine plus constrained candidate generation plus market/stash candidate retrieval.

3. Do not blindly port PoB every day into a fast language. That is brittle and not TDD-friendly. Use PoB as a version-pinned oracle first. Build a fast evaluator only for search pruning, caching, approximate scoring, and eventually selected calculation subsets. Any ported logic must be covered by golden-master tests against the current PoB version.

4. Do not depend on undocumented trade endpoints. Use official OAuth APIs, public stash stream, Currency Exchange API, user-provided account data, and permitted third-party public economy datasets where their terms allow it. Any unofficial trade search integration must be behind a policy gate and replaceable.

5. DPS and EHP are not single universal numbers. They depend on PoB configuration: enemy type, ailment assumptions, charges, flasks, buffs, exposure, curse effect, uptime, map mods, conditional effects, minion conditions, triggered skills, and player behavior. Every optimization request must include or default a canonical `BuildConfiguration`.

6. "Tanky to Glass Cannon" is a multi-objective optimization preference, not a simple scalar. The system must produce a Pareto frontier and explain trade-offs.

7. Cost is both a hard constraint and an objective. A build may be invalid if it exceeds budget. Among valid builds, lower cost can still be preferred.

8. Existing stash items are not just a data feed. They are owned candidates with zero acquisition cost but non-zero opportunity cost. The system should distinguish "owned and equipped", "owned and unused", "can be crafted from owned base", and "must be bought".

9. "All league mechanics" must be categorized. Some mechanics directly affect build stats, some only affect acquisition/crafting, some only affect maps or economy, and some are legacy/permanent-league only. Trying to put all of them into the same calculator module is a design error.

10. Agentic coding requires small, testable stories. No agent should receive a vague task like "implement item optimizer". Each story below has concrete tasks and subtasks; every task begins with tests.

## 3. Target architecture

The target architecture is a set of versioned services and libraries. The names are implementation names, not final product names.

### 3.1 Services and libraries

- `source-registry`: Stores every source version, URL, checksum, fetch time, parser version, schema version, and trust level.
- `game-data-ingestor`: Pulls and validates RePoE/PyPoE exports, official tree exports when current, PoB data files, official API metadata, and manually maintained overrides.
- `game-ontology`: Strongly typed data model for stats, mods, mod groups, base items, item classes, skill gems, passive nodes, masteries, tattoos, runegrafts, jewels, cluster jewels, timeless jewels, flasks, item states, and league mechanics.
- `build-ir`: Internal build representation. This must not be PoB XML directly, but it must round-trip to and from PoB.
- `pob-oracle`: Version-pinned PoB worker service. Runs PoB calculation in isolated workers, returns normalized metrics, and stores calculation traces.
- `fast-evaluator`: Approximate high-throughput scorer for candidate pruning. It is never allowed to be the final source of truth unless a metric is explicitly certified by golden tests.
- `candidate-generator`: Generates valid tree, item, gem, flask, jewel, tattoo, runegraft, and configuration candidates from constraints.
- `optimizer`: Multi-objective search engine. Produces Pareto frontiers, not just one build.
- `price-service`: Currency conversion, item pricing, rare-item comparable search, liquidity, confidence, historical price trend, and budget feasibility.
- `stash-adapter`: Integration boundary to the existing public/account stash scanners. Converts scanned items into the internal item model.
- `build-corpus-service`: Optional ML/corpus system for build archetypes, ladder data, user-submitted PoBs, and generated successful builds.
- `api-gateway`: Backend contract for the existing Web UI.
- `explainability-service`: Human-readable explanation of why each item/tree/gem change was proposed.
- `agent-ci`: CI, fixture, regression, and agent-task orchestration.

### 3.2 Recommended language split

Use the existing repository's language stack where it already exists. For new modules:

- Rust is recommended for optimizer, fast evaluator, graph algorithms, item legality checks, and high-throughput candidate scoring.
- TypeScript is recommended for API contracts, Web UI integration, schema definitions, and service orchestration if the current UI/backend already uses it.
- Python is acceptable for offline experiments, ML notebooks, and data science prototyping, but production calculation and optimization should not depend on notebook code.
- Lua/LuaJIT or a containerized PoB runtime should be used for the initial PoB oracle. Do not port first; verify first.

### 3.3 Core data contracts

Minimum contracts:

- `SourceVersion`: source name, semantic version, game version, fetch timestamp, checksum, parser version, trust level.
- `GameVersion`: major/minor/patch/hotfix, league, realm, ruthless flag, standard/legacy flag.
- `BuildSpec`: class, ascendancy, league, level, bandit choice, pantheon, tree, ascendancy tree, items, sockets, gems, flasks, jewels, tattoos, runegrafts, cluster trees, timeless jewels, anoints, configuration.
- `BuildConfiguration`: enemy profile, boss preset, charges, flasks, buffs, ailment assumptions, skill selection, map modifiers, uptime assumptions, custom toggles.
- `OptimizationRequest`: hard constraints, soft preferences, budget, edit limits, locked items, owned-items mode, search depth, output count, explanation verbosity.
- `OptimizationResult`: candidate build, metrics, cost, confidence, diff, reasons, assumptions, PoB validation status, reproducibility hash.
- `ItemCandidate`: internal item representation, source, price, ownership, legal states, equip slot, mod breakdown, parsed stats, acquisition confidence.
- `MetricVector`: Hit DPS, Average DPS, Full DPS, DoT DPS, EHP, max hit by damage type, recovery, avoidance, ailment mitigation, reservation, movement, cost, confidence.

## 4. Optimization model

### 4.1 Hard constraints

Hard constraints must be enforced before scoring:

- Game version and league.
- Class and ascendancy.
- Character level and available passive points.
- Budget and currency ownership.
- Required skill, weapon type, archetype, or excluded mechanics if provided.
- Locked items, locked gems, locked sockets, locked tree regions.
- Passive tree edit distance for existing-build optimization.
- Legal item generation rules.
- One-of constraints such as one Timeless Jewel with Historic limitation, tattoo limits, runegraft uniqueness, flask slot count, item slot conflicts, cluster jewel placement, and gem support compatibility.

### 4.2 Objective vector

The optimizer should compute a vector, not just one score:

- `hit_dps`
- `average_dps`
- `full_dps`
- `dot_dps`
- `ehp`
- `max_hit_physical`
- `max_hit_fire`
- `max_hit_cold`
- `max_hit_lightning`
- `max_hit_chaos`
- `recovery_per_second`
- `avoidance_score`
- `ailment_mitigation_score`
- `cost_divine_equivalent`
- `owned_item_fraction`
- `confidence`

The Tanky-to-Glass-Cannon slider maps to weights, but the system still returns Pareto alternatives:

- `0.0` = Tanky: max hit, EHP, recovery, ailment mitigation, and budget reliability dominate.
- `0.5` = Balanced: DPS and defences weighted similarly.
- `1.0` = Glass Cannon: DPS dominates, but hard defence floors may still apply.

### 4.3 Search strategy

Use staged search:

1. Candidate seeding from archetypes, skill tags, class/ascendancy synergies, existing build, owned stash, and market availability.
2. Cheap legality filtering using game ontology.
3. Fast approximate scoring using cached deltas and surrogate models.
4. Batch PoB oracle evaluation for the top candidates.
5. Local search around validated winners.
6. Pareto frontier extraction.
7. Explanation and cost validation.

Recommended algorithms:

- Graph shortest path and k-shortest paths for tree travel.
- Local search / simulated annealing for limited tree adjustments.
- Evolutionary multi-objective search such as NSGA-II for full random build generation.
- Bayesian optimization or learned ranking for candidate prioritization.
- Constraint programming for socket/link/gem assignment.
- Beam search for item-slot replacement.
- Specialized exhaustive/heuristic search for Timeless Jewel seeds and cluster jewel layouts.

## 5. Test-driven and agentic coding rules

Every story must follow this rule sequence:

1. Write the failing test first.
2. Add or update fixtures.
3. Implement the smallest passing code.
4. Add property tests or golden tests where the domain is combinatorial.
5. Add telemetry or trace output for externally visible behavior.
6. Run the story-level CI target.
7. Produce a short agent completion note with changed files, tests, and known limitations.

No agent may change source-ingestion schemas, optimizer scoring, and UI contracts in the same story. Cross-module changes require a parent integration story.

Minimum test layers:

- Unit tests for parsers, item legality, tree graph, constraints, score normalization.
- Snapshot tests for current 3.28 data ingestion.
- Contract tests for scanner adapters and UI API.
- Golden-master tests comparing PoB oracle results against expected PoB outputs.
- Property-based tests for generated item legality and tree paths.
- Regression tests for every PoB sync.
- Performance tests for candidate throughput.
- End-to-end tests for the three user workflows: random constrained build, existing build optimization, and stash upgrade detection.

## 6. Phased implementation backlog

The hierarchy below is deliberately agent-friendly. Each task has subtasks. Unless explicitly stated otherwise, every task starts with a failing test and ends with CI passing.

---

# Phase 0 - Governance, source authority, and agent coding foundation

## Epic P0-E1 - Source authority and compliance

### User Story P0-E1-S1 - Source registry

As a system maintainer, I need every external source to be versioned and checksummed so that no optimizer result is generated from stale or mixed PoE data.

Tasks:

- Task P0-E1-S1-T1: Create `SourceVersion` schema.
  - Subtask: Write a schema test for required fields: source name, game version, fetched-at, checksum, parser version, trust level.
  - Subtask: Implement the schema in the shared domain package.
  - Subtask: Add fixtures for PoB, RePoE, official patch notes, official API docs, and passive tree data.
  - Subtask: Add validation that rejects missing checksums.

- Task P0-E1-S1-T2: Implement source freshness gate.
  - Subtask: Write a failing test where 3.27 data is rejected for a 3.28 optimization request.
  - Subtask: Add `GameVersion` comparison and league matching logic.
  - Subtask: Add an override mode for archived builds with explicit user confirmation.
  - Subtask: Emit a structured warning when source dates differ.

- Task P0-E1-S1-T3: Implement source trust policy.
  - Subtask: Define trust levels: official, official-derived, PoB, community-export, third-party economy, manual override.
  - Subtask: Add tests that official patch data outranks community wiki data when they conflict.
  - Subtask: Add policy metadata for sources that must not be used as calculation truth.
  - Subtask: Add audit logs for every source used in a build result.

### User Story P0-E1-S2 - API and Terms compliance guardrails

As a platform owner, I need API usage to follow GGG policies and rate limits so that the project does not risk access revocation.

Tasks:

- Task P0-E1-S2-T1: Create API policy module.
  - Subtask: Write tests for allowed scopes: `account:stashes`, `account:characters`, `account:league_accounts`, `service:psapi`, `service:cxapi`.
  - Subtask: Implement policy checks before any API client can be instantiated.
  - Subtask: Require identifiable User-Agent configuration in tests.
  - Subtask: Fail CI if a service attempts to use an undocumented endpoint without a policy exception.

- Task P0-E1-S2-T2: Implement dynamic rate-limit handling contract.
  - Subtask: Add fixture responses with `X-Rate-Limit-*` and `Retry-After` headers.
  - Subtask: Write tests for backoff, queueing, and retry cancellation.
  - Subtask: Implement shared rate-limit parser.
  - Subtask: Expose rate-limit metrics to observability.

- Task P0-E1-S2-T3: Add third-party data policy registry.
  - Subtask: Add tests that mark poe.ninja/RePoE/wiki sources as replaceable and non-authoritative for exact calculations.
  - Subtask: Store terms URL, allowed usage, cache TTL, and attribution requirements.
  - Subtask: Add build-result attribution text.
  - Subtask: Add kill-switch support per third-party source.

### User Story P0-E1-S3 - Patch synchronization readiness

As a maintainer, I need the system to detect when PoE, PoB, or data exports change so that optimizations are not silently wrong.

Tasks:

- Task P0-E1-S3-T1: Implement version drift detector.
  - Subtask: Write tests for game patch change, PoB release change, RePoE export change, and API reference change.
  - Subtask: Implement source polling metadata.
  - Subtask: Generate `PatchDriftEvent` records.
  - Subtask: Block high-confidence optimization output when drift is unresolved.

- Task P0-E1-S3-T2: Implement patch review queue.
  - Subtask: Add a test that a new PoB release creates a regression-run job.
  - Subtask: Store changed source diffs and affected mechanics.
  - Subtask: Create status states: pending, testing, accepted, quarantined.
  - Subtask: Expose status to API/UI.

## Epic P0-E2 - Agentic coding framework

### User Story P0-E2-S1 - Agent task contract

As a lead developer, I need every LLM-agent task to have explicit inputs, outputs, tests, and boundaries.

Tasks:

- Task P0-E2-S1-T1: Create task template.
  - Subtask: Include story ID, files allowed, files forbidden, required tests, fixtures, acceptance criteria, rollback plan.
  - Subtask: Add a sample task for a parser story.
  - Subtask: Add a sample task for an optimizer story.
  - Subtask: Add a review checklist for human approval.

- Task P0-E2-S1-T2: Add branch and PR conventions.
  - Subtask: Define branch names by story ID.
  - Subtask: Define PR title and description format.
  - Subtask: Require test evidence in PR body.
  - Subtask: Add a CI check that validates story IDs.

### User Story P0-E2-S2 - Test harness skeleton

As an agent, I need a stable test harness before implementing domain logic.

Tasks:

- Task P0-E2-S2-T1: Create test directories and fixture conventions.
  - Subtask: Add `unit`, `contract`, `integration`, `golden`, `property`, `performance`, and `e2e` directories.
  - Subtask: Define fixture naming: game version, source version, scenario, expected metrics.
  - Subtask: Add a failing smoke test for missing fixture metadata.
  - Subtask: Implement fixture validator.

- Task P0-E2-S2-T2: Add deterministic random seed utilities.
  - Subtask: Write tests for reproducible candidate generation.
  - Subtask: Implement seed propagation through request, optimizer, and result.
  - Subtask: Add result reproducibility hash.
  - Subtask: Store seed and source versions in output.

## Epic P0-E3 - Product metric and request definition

### User Story P0-E3-S1 - Canonical optimization request

As a user, I need to express required class/ascendancy, budget, DPS/EHP preference, and edit limits in one request.

Tasks:

- Task P0-E3-S1-T1: Define `OptimizationRequest`.
  - Subtask: Add tests for required class and ascendancy fields.
  - Subtask: Add budget fields in chaos/divine/native currency with conversion metadata.
  - Subtask: Add Tanky-to-Glass-Cannon slider and explicit objective weights.
  - Subtask: Add locked item, locked skill, and tree edit-limit fields.

- Task P0-E3-S1-T2: Validate hard constraints.
  - Subtask: Test invalid class/ascendancy combinations.
  - Subtask: Test negative budget and impossible edit limits.
  - Subtask: Test unavailable league or unsupported game version.
  - Subtask: Return machine-readable validation errors.

### User Story P0-E3-S2 - Metric normalization

As an optimizer, I need normalized DPS/EHP/cost metrics so that different builds can be compared consistently.

Tasks:

- Task P0-E3-S2-T1: Define `MetricVector`.
  - Subtask: Add tests for hit DPS, average DPS, full DPS, DoT DPS, EHP, max hit, recovery, avoidance, cost, confidence.
  - Subtask: Implement null/unsupported metric handling.
  - Subtask: Add unit conversion for chaos/divine equivalents.
  - Subtask: Add confidence metadata per metric.

- Task P0-E3-S2-T2: Define default configuration presets.
  - Subtask: Add tests for `Guardian/Pinnacle`, `Mapping`, `Uber`, and `Custom` presets.
  - Subtask: Encode enemy resistances, ailment assumptions, flask uptime, charges, and conditional toggles.
  - Subtask: Allow user overrides.
  - Subtask: Store configuration in every PoB oracle request.

---

# Phase 1 - Game data ingestion and ontology

## Epic P1-E1 - RePoE/PyPoE data ingestion

### User Story P1-E1-S1 - Ingest current game data

As a data maintainer, I need current 3.28 game data ingested into stable schemas.

Tasks:

- Task P1-E1-S1-T1: Pull RePoE 3.28 export.
  - Subtask: Write test that rejects a non-3.28 export.
  - Subtask: Fetch or load `stats`, `mods`, `base_items`, `item_classes`, `tags`, `stat_translations`, `gems`, `cluster_jewels`, `crafting_bench_options`, `essences`, and `fossils`.
  - Subtask: Store checksums for every file.
  - Subtask: Persist source metadata.

- Task P1-E1-S1-T2: Add schema validation.
  - Subtask: Write failing tests with missing stat IDs and invalid mod references.
  - Subtask: Generate typed schemas.
  - Subtask: Validate references between mods, stats, tags, and item classes.
  - Subtask: Produce a data-quality report.

### User Story P1-E1-S2 - Stat and modifier ontology

As a calculator, I need stats and modifiers represented in a normalized form.

Tasks:

- Task P1-E1-S2-T1: Implement stat model.
  - Subtask: Test stat ID parsing, local/global flag, alias handling, and translation lookup.
  - Subtask: Implement `StatDefinition` and `StatValueRange`.
  - Subtask: Add text rendering and reverse lookup.
  - Subtask: Add unsupported stat registry.

- Task P1-E1-S2-T2: Implement modifier model.
  - Subtask: Test mod domain, generation type, prefix/suffix, tier, level, group, tags, spawn weights, and roll ranges.
  - Subtask: Implement `ModifierDefinition`.
  - Subtask: Add mod exclusivity checks by group.
  - Subtask: Add fixtures for explicit, implicit, crafted, fractured, essence, fossil, veiled, eldritch, enchant, and corrupted mods.

### User Story P1-E1-S3 - Stat translation and item text parsing basis

As an item parser, I need to map human mod lines to stat IDs.

Tasks:

- Task P1-E1-S3-T1: Implement stat translation engine.
  - Subtask: Add tests for simple numeric, range, signed, percentage, and conditional lines.
  - Subtask: Implement translation pattern compiler.
  - Subtask: Add reverse matching from item text to stat IDs.
  - Subtask: Report ambiguous matches.

- Task P1-E1-S3-T2: Implement parser drift tests.
  - Subtask: Add fixture lines from 3.28 patch mechanics.
  - Subtask: Add failing test for unknown line.
  - Subtask: Store unknown-line counts by source version.
  - Subtask: Fail CI if unknown-line count exceeds threshold.

## Epic P1-E2 - Passive tree, ascendancy, masteries, tattoos, and runegrafts

### User Story P1-E2-S1 - Passive tree graph

As an optimizer, I need a versioned graph of the 3.28 passive tree.

Tasks:

- Task P1-E2-S1-T1: Load passive tree JSON.
  - Subtask: Add tests for nodes, groups, root, class data, edges, orbit data, jewel sockets, masteries, keystones, and notables.
  - Subtask: Implement graph loader.
  - Subtask: Reject tree data whose version does not match the active `GameVersion`.
  - Subtask: Store checksum and source metadata.

- Task P1-E2-S1-T2: Implement pathing algorithms.
  - Subtask: Test class start pathing for all base classes.
  - Subtask: Implement shortest path and k-shortest valid paths.
  - Subtask: Account for Scion start behavior.
  - Subtask: Add edit-distance calculation between two trees.

### User Story P1-E2-S2 - Ascendancy model

As a build generator, I need class and ascendancy constraints enforced exactly.

Tasks:

- Task P1-E2-S2-T1: Model base classes and ascendancies.
  - Subtask: Test class-to-ascendancy mappings.
  - Subtask: Include Scion and the 3.28 Reliquarian.
  - Subtask: Model ascendancy passive point limits.
  - Subtask: Reject impossible ascendancy allocations.

- Task P1-E2-S2-T2: Model special ascendancy mechanics.
  - Subtask: Add tests for Forbidden Flame/Flesh exclusions where relevant.
  - Subtask: Add Reliquarian league-rotating notable metadata.
  - Subtask: Add support for legacy/standard variants.
  - Subtask: Record unsupported nodes in coverage report.

### User Story P1-E2-S3 - Masteries, Tattoos, and Runegrafts

As a tree optimizer, I need mastery modifications, tattoos, and runegrafts represented as legal transformations.

Tasks:

- Task P1-E2-S3-T1: Implement mastery allocation model.
  - Subtask: Test mastery availability after connected notable allocation.
  - Subtask: Test one mastery option per category where applicable.
  - Subtask: Implement mastery selection constraints.
  - Subtask: Add PoB round-trip fixture.

- Task P1-E2-S3-T2: Implement tattoo model.
  - Subtask: Test tattoo application only to eligible allocated passives.
  - Subtask: Enforce 50 tattoo limit.
  - Subtask: Support replacement and removal state.
  - Subtask: Add edge-case tests for Timeless Jewel override interactions.

- Task P1-E2-S3-T3: Implement runegraft model.
  - Subtask: Test runegraft application to allocated mastery passives.
  - Subtask: Enforce only one of each runegraft type.
  - Subtask: Include 3.28 new runegrafts in source-backed fixtures.
  - Subtask: Add PoB oracle validation for at least one runegrafted build.

## Epic P1-E3 - Item possibility model

### User Story P1-E3-S1 - Base items and item states

As a candidate generator, I need every item to have a base, class, slot, tags, requirements, and legal state flags.

Tasks:

- Task P1-E3-S1-T1: Implement base item model.
  - Subtask: Test item class, tags, level requirement, attribute requirement, dimensions, domain, and equip slot.
  - Subtask: Implement `BaseItemDefinition`.
  - Subtask: Add fixtures for weapons, armour, jewellery, jewels, flasks, maps, gems, and currency-like build items.
  - Subtask: Add item class compatibility filters.

- Task P1-E3-S1-T2: Implement item state flags.
  - Subtask: Test rarity, identified, corrupted, mirrored, split, fractured, synthesized, influenced, eldritch, veiled, enchanted, crafted, quality, sockets, links.
  - Subtask: Implement state transitions and constraints.
  - Subtask: Reject illegal combinations.
  - Subtask: Add legacy/permanent-league state support.

### User Story P1-E3-S2 - Affix legality engine

As an item generator, I need to know which affixes can legally exist on an item.

Tasks:

- Task P1-E3-S2-T1: Implement mod applicability.
  - Subtask: Test base tags, item class, item level, domain, generation type, and influence restrictions.
  - Subtask: Implement `canApplyMod(base, state, mod)`.
  - Subtask: Add mod group exclusivity tests.
  - Subtask: Add maximum prefix/suffix count tests.

- Task P1-E3-S2-T2: Implement rare item candidate generator.
  - Subtask: Test deterministic generation with seed.
  - Subtask: Generate by slot, desired stat vector, item level, and budget range.
  - Subtask: Avoid enumerating full rare item space.
  - Subtask: Emit legality proof for each generated rare.

- Task P1-E3-S2-T3: Implement crafted and league-specific modifiers.
  - Subtask: Add tests for crafting bench, essence, fossil, veiled, delve, temple, elder/shaper/conqueror, eldritch, synthesized, fractured, enchant, corruption implicit, and special 3.28 modifiers.
  - Subtask: Encode acquisition/source metadata.
  - Subtask: Encode cost estimator hooks.
  - Subtask: Add unsupported mechanic flags for anything missing.

### User Story P1-E3-S3 - Unique item and variant model

As a build generator, I need uniques with roll ranges, variants, legacy states, and current obtainability.

Tasks:

- Task P1-E3-S3-T1: Ingest unique item data.
  - Subtask: Pull PoB unique data and RePoE unique references.
  - Subtask: Add tests for current 3.28 new uniques.
  - Subtask: Model roll ranges and variant IDs.
  - Subtask: Mark unobtainable and legacy variants.

- Task P1-E3-S3-T2: Implement unique item instantiation.
  - Subtask: Test min-roll, max-roll, median-roll, and exact-roll instances.
  - Subtask: Implement variant selection.
  - Subtask: Add price lookup keys.
  - Subtask: Add PoB import/export fixture.

### User Story P1-E3-S4 - Flasks, jewels, cluster jewels, and Timeless Jewels

As a build optimizer, I need non-gear slots represented exactly because they heavily affect DPS/EHP.

Tasks:

- Task P1-E3-S4-T1: Implement flask model.
  - Subtask: Test base flask, charges, duration, quality, enchant, prefix, suffix, unique flasks, and conditional uptime.
  - Subtask: Implement automated use assumptions separately from item data.
  - Subtask: Add cost hooks.
  - Subtask: Add PoB oracle fixture with flasks enabled/disabled.

- Task P1-E3-S4-T2: Implement regular and abyss jewel model.
  - Subtask: Test jewel base types, corruption, implicits, abyss jewel classes, and socket restrictions.
  - Subtask: Add mod legality by jewel type.
  - Subtask: Implement Watcher's Eye-style multi-mod uniques.
  - Subtask: Add price lookup keys.

- Task P1-E3-S4-T3: Implement cluster jewel model.
  - Subtask: Test large/medium/small cluster bases, passives count, enchant, item level, notables, jewel sockets, and node ordering.
  - Subtask: Implement cluster subgraph expansion.
  - Subtask: Validate cluster import/export against PoB.
  - Subtask: Add optimizer candidate generation by notable set.

- Task P1-E3-S4-T4: Implement Timeless Jewel model.
  - Subtask: Test Historic limitation and socket radius.
  - Subtask: Include all current Timeless Jewels, including 3.28 Heroic Tragedy.
  - Subtask: Represent seed, conqueror/name, transformed keystones/notables/small passives.
  - Subtask: Use PoB as oracle for transformations until independently certified.

## Epic P1-E4 - Skills, gems, supports, and configurations

### User Story P1-E4-S1 - Skill gem catalog

As a build generator, I need active and support gems with tags, levels, qualities, transfigured variants, and 3.28 additions.

Tasks:

- Task P1-E4-S1-T1: Ingest active and support gems.
  - Subtask: Test gem tags, attributes, level requirement, quality stats, variants, Vaal versions, transfigured versions.
  - Subtask: Include 3.28 Exceptional Support Gems and Imbued gem mechanics.
  - Subtask: Store source version and unsupported flags.
  - Subtask: Add fixture for a current 3.28 gem setup.

- Task P1-E4-S1-T2: Implement gem compatibility.
  - Subtask: Test support can/cannot support active skill by tags and restrictions.
  - Subtask: Test item-granted supports.
  - Subtask: Test trigger support behavior as config-dependent.
  - Subtask: Add PoB oracle comparison for linked skills.

### User Story P1-E4-S2 - Skill configuration variables

As a calculator, I need skill-specific configuration inputs to avoid misleading DPS.

Tasks:

- Task P1-E4-S2-T1: Define skill config schema.
  - Subtask: Test stages, projectiles, overlaps, traps/mines/totems, minions, brands, ailments, poison stacks, bleed, ignite, exposure, rage, charges, warcries, and triggered skills.
  - Subtask: Implement generic and skill-specific config fields.
  - Subtask: Set safe defaults per preset.
  - Subtask: Record assumptions in result explanations.

- Task P1-E4-S2-T2: Add config completeness scoring.
  - Subtask: Test missing important config reduces confidence.
  - Subtask: Add warnings for skill archetypes that need manual config.
  - Subtask: Persist config warning metadata.
  - Subtask: Display warnings via API.

## Epic P1-E5 - League mechanics registry

### User Story P1-E5-S1 - Mechanic classification

As an architect, I need league mechanics classified by how they affect builds.

Tasks:

- Task P1-E5-S1-T1: Create `LeagueMechanic` registry.
  - Subtask: Test categories: direct build stat, item generation, acquisition/cost, map-only, encounter-only, legacy-only.
  - Subtask: Implement registry schema.
  - Subtask: Add 3.28 Mirage, Keepers of the Flame core changes, tattoos, runegrafts, timeless jewels, cluster jewels, eldritch, heist, delve, betrayal, harvest, essence, fossils, expedition, blight, delirium, legion, ritual, ultimatum, sanctum, necropolis-style/corpse if available in current data, and standard legacy flags.
  - Subtask: Add unsupported coverage report.

- Task P1-E5-S1-T2: Link mechanics to systems.
  - Subtask: Test that a mechanic can attach to item generation, tree modification, price estimation, or config.
  - Subtask: Implement mechanic-to-module mapping.
  - Subtask: Add source metadata per mechanic.
  - Subtask: Add UI visibility metadata.

### User Story P1-E5-S2 - Mirage 3.28 mechanics baseline

As a current-league optimizer, I need 3.28 mechanics represented where they affect builds and costs.

Tasks:

- Task P1-E5-S2-T1: Add Mirage feature flags.
  - Subtask: Add fixtures for Exceptional Support Gems, Imbued Gems, new Runegrafts, Heroic Tragedy, Reliquarian, and 3.28 unique items.
  - Subtask: Connect each feature to item/tree/gem/cost modules.
  - Subtask: Add source-backed descriptions.
  - Subtask: Fail if 3.28 request runs with feature flags missing.

---

# Phase 2 - Build representation, import/export, and parsing

## Epic P2-E1 - Build intermediate representation

### User Story P2-E1-S1 - Build IR schema

As a service, I need a complete internal build representation that is independent of UI and PoB serialization.

Tasks:

- Task P2-E1-S1-T1: Define `BuildSpec`.
  - Subtask: Test required sections: character, tree, ascendancy, items, sockets, gems, flasks, jewels, tattoos, runegrafts, bandits, pantheon, configuration, league.
  - Subtask: Implement typed schema.
  - Subtask: Add JSON serialization.
  - Subtask: Add deterministic canonicalization for hashing.

- Task P2-E1-S1-T2: Define build diff model.
  - Subtask: Test item replacement, tree node added/removed, gem change, flask change, config change, and cost change.
  - Subtask: Implement `BuildDiff`.
  - Subtask: Add human-readable summary generation.
  - Subtask: Add machine-readable patch format.

### User Story P2-E1-S2 - Build validation

As an optimizer, I need invalid builds rejected before PoB evaluation.

Tasks:

- Task P2-E1-S2-T1: Implement structural validation.
  - Subtask: Test missing items, invalid slots, duplicate flasks, impossible sockets, unsupported class, impossible ascendancy.
  - Subtask: Implement validation rules.
  - Subtask: Add clear error messages.
  - Subtask: Expose validation via API.

- Task P2-E1-S2-T2: Implement legality validation.
  - Subtask: Test passive point limits, level requirements, item requirements, gem requirements, attribute requirements, and league-only items.
  - Subtask: Implement legality engine integration.
  - Subtask: Add warnings for user-overridden legacy states.
  - Subtask: Add validation confidence score.

## Epic P2-E2 - PoB import/export

### User Story P2-E2-S1 - Import PoB builds

As a user, I need to import existing PoB builds for optimization.

Tasks:

- Task P2-E2-S1-T1: Implement PoB code decoder.
  - Subtask: Add fixtures for compressed PoB codes and XML.
  - Subtask: Test decoding and XML extraction.
  - Subtask: Implement parser adapter.
  - Subtask: Reject unsupported PoB versions with clear errors.

- Task P2-E2-S1-T2: Map PoB XML to Build IR.
  - Subtask: Test character, tree, skills, items, flasks, jewels, configs, and notes mapping.
  - Subtask: Implement mapping layer.
  - Subtask: Store original PoB code for traceability.
  - Subtask: Add unknown-field preservation.

### User Story P2-E2-S2 - Export to PoB

As a user, I need optimized candidates exportable back to PoB.

Tasks:

- Task P2-E2-S2-T1: Implement Build IR to PoB XML.
  - Subtask: Add round-trip tests for imported builds.
  - Subtask: Serialize tree, skills, items, flasks, config, jewels, tattoos, runegrafts.
  - Subtask: Preserve notes and source metadata where possible.
  - Subtask: Validate exported build in PoB oracle.

- Task P2-E2-S2-T2: Implement share code generation.
  - Subtask: Test compression and encoding.
  - Subtask: Generate PoB-compatible code.
  - Subtask: Add artifact download endpoint.
  - Subtask: Add e2e test from request to exported PoB.

## Epic P2-E3 - Account and stash item normalization

### User Story P2-E3-S1 - Stash scanner adapter contract

As the optimizer, I need items from the existing stash scanners normalized into the same item model as generated/market items.

Tasks:

- Task P2-E3-S1-T1: Define scanner adapter input.
  - Subtask: Create contract tests using sample public stash and account stash payloads.
  - Subtask: Include item ID, league, tab, location, raw text/mod arrays, item properties, icon, price notes, and owner.
  - Subtask: Implement adapter interface.
  - Subtask: Mark source as owned/public/listed.

- Task P2-E3-S1-T2: Normalize item payloads.
  - Subtask: Test rares, uniques, flasks, jewels, cluster jewels, gems, maps, currency, and stackables.
  - Subtask: Parse raw mods into internal stat IDs.
  - Subtask: Store raw payload for reprocessing.
  - Subtask: Add unknown-mod reporting.

### User Story P2-E3-S2 - Item fingerprinting

As a stash upgrade detector, I need stable fingerprints for deduplication and matching.

Tasks:

- Task P2-E3-S2-T1: Implement item fingerprints.
  - Subtask: Test exact item ID, stable content hash, trade-comparable hash, and build-equivalence hash.
  - Subtask: Include base, item level, state flags, mod IDs, roll values, sockets, quality, corruption, and variant.
  - Subtask: Exclude volatile tab position for content hashes.
  - Subtask: Add deduplication tests.

- Task P2-E3-S2-T2: Track ownership changes.
  - Subtask: Test item moved tabs, item sold, item modified, item newly acquired.
  - Subtask: Implement inventory state timeline.
  - Subtask: Add event output for background optimization.
  - Subtask: Add storage indexes.

## Epic P2-E4 - Build comparability and configs

### User Story P2-E4-S1 - Comparable build contexts

As a user, I need before/after comparisons to use the same assumptions.

Tasks:

- Task P2-E4-S1-T1: Implement config locking.
  - Subtask: Test that optimizer cannot compare builds with different enemy/flask/charge assumptions unless marked.
  - Subtask: Carry configuration through all evaluations.
  - Subtask: Add config diff warnings.
  - Subtask: Expose config in output.

- Task P2-E4-S1-T2: Implement skill selection rules.
  - Subtask: Test active skill selection, full DPS skill group, minion skill, aura-only builds, and triggered skills.
  - Subtask: Add explicit skill target in request.
  - Subtask: Fall back to PoB selected main skill.
  - Subtask: Warn when multiple plausible main skills exist.

---

# Phase 3 - Calculation engine and PoB oracle

## Epic P3-E1 - PoB oracle service

### User Story P3-E1-S1 - Version-pinned PoB execution

As a calculator, I need to run the current PoB code as a deterministic oracle.

Tasks:

- Task P3-E1-S1-T1: Create PoB runtime container.
  - Subtask: Add test that container reports PoB version and git commit.
  - Subtask: Build Lua/LuaJIT runtime or PoB-compatible runtime.
  - Subtask: Mount source read-only.
  - Subtask: Expose health check.

- Task P3-E1-S1-T2: Implement oracle request/response.
  - Subtask: Test request with Build IR and config.
  - Subtask: Convert Build IR to PoB input.
  - Subtask: Execute calculation.
  - Subtask: Return normalized `MetricVector` plus raw PoB output.

- Task P3-E1-S1-T3: Implement isolation and timeouts.
  - Subtask: Test malformed build input.
  - Subtask: Add worker timeout.
  - Subtask: Add memory limit.
  - Subtask: Add retry and quarantine behavior.

### User Story P3-E1-S2 - PoB sync automation

As a maintainer, I need to sync PoB frequently without silently breaking calculations.

Tasks:

- Task P3-E1-S2-T1: Add PoB source poller.
  - Subtask: Test new release detection.
  - Subtask: Fetch release metadata and commit hash.
  - Subtask: Store source version.
  - Subtask: Trigger golden regression suite.

- Task P3-E1-S2-T2: Add PoB sync gate.
  - Subtask: Test that failed golden tests keep old PoB active.
  - Subtask: Implement active/candidate PoB version slots.
  - Subtask: Report changed metrics beyond tolerance.
  - Subtask: Require manual or automated acceptance.

## Epic P3-E2 - Golden-master calculation tests

### User Story P3-E2-S1 - Fixture builds

As a test suite, I need representative builds that cover major mechanics.

Tasks:

- Task P3-E2-S1-T1: Create fixture catalog.
  - Subtask: Add builds for life attack, ES spell, minion, DoT, poison, ignite, bleed, trap/mine, totem, ward, flask-heavy, aura stack, trigger, cluster jewel, Timeless Jewel, tattoos, runegrafts, Imbued Gems, Exceptional Supports, Reliquarian.
  - Subtask: Store PoB code, expected metrics, source versions, and config.
  - Subtask: Add fixture metadata validator.
  - Subtask: Add per-fixture tolerance.

- Task P3-E2-S1-T2: Create metric diff reporter.
  - Subtask: Test exact match, within tolerance, outside tolerance, missing metric.
  - Subtask: Implement metric diff output.
  - Subtask: Classify by severity.
  - Subtask: Store history per PoB version.

### User Story P3-E2-S2 - Calculation coverage tracking

As a maintainer, I need to know which mechanics are covered by tests.

Tasks:

- Task P3-E2-S2-T1: Implement mechanic-to-fixture mapping.
  - Subtask: Test every direct-build-stat mechanic has at least one fixture.
  - Subtask: Link fixtures to mechanic registry.
  - Subtask: Generate coverage report.
  - Subtask: Fail CI for uncovered critical mechanics.

## Epic P3-E3 - Fast evaluator

### User Story P3-E3-S1 - Fast approximate scorer

As an optimizer, I need a cheap scorer for pruning millions of invalid or weak candidates before PoB evaluation.

Tasks:

- Task P3-E3-S1-T1: Implement stat aggregation subset.
  - Subtask: Start with attributes, life, ES, armour, evasion, resistances, suppression, generic damage, attack/cast speed, crit, gem levels.
  - Subtask: Write golden tests against PoB for simple builds.
  - Subtask: Mark metrics as approximate.
  - Subtask: Add max allowed error thresholds per metric.

- Task P3-E3-S1-T2: Implement delta evaluator.
  - Subtask: Test single item replacement delta.
  - Subtask: Test passive node add/remove delta.
  - Subtask: Cache per-component stat contributions.
  - Subtask: Fall back to PoB for unsupported deltas.

### User Story P3-E3-S2 - Certification of fast metrics

As a product owner, I need to know which fast metrics are safe to show.

Tasks:

- Task P3-E3-S2-T1: Add metric certification registry.
  - Subtask: Define states: uncertified, approximate, certified-for-filtering, certified-for-display.
  - Subtask: Test uncertified metric cannot be final output.
  - Subtask: Promote metrics only after golden tests pass.
  - Subtask: Show certification in debug output.

## Epic P3-E4 - Parallel evaluation and caching

### User Story P3-E4-S1 - Build hash and cache

As an evaluator, I need to avoid recalculating identical builds.

Tasks:

- Task P3-E4-S1-T1: Implement evaluation hash.
  - Subtask: Test hash includes Build IR, configuration, source versions, PoB version, and metric selection.
  - Subtask: Implement canonical serialization.
  - Subtask: Store cache entries.
  - Subtask: Invalidate on source drift.

- Task P3-E4-S1-T2: Implement batch evaluation.
  - Subtask: Test ordered and unordered batch response.
  - Subtask: Add worker pool.
  - Subtask: Add priority queue for interactive requests.
  - Subtask: Add cancellation for obsolete candidates.

---

# Phase 4 - Pricing, currency, and stash integration

## Epic P4-E1 - Official API integration

### User Story P4-E1-S1 - OAuth-backed account API client

As a user, I need the system to use my account data only with proper authorization.

Tasks:

- Task P4-E1-S1-T1: Implement OAuth token storage contract.
  - Subtask: Test token encrypted-at-rest.
  - Subtask: Test scope-specific access.
  - Subtask: Implement token refresh handling.
  - Subtask: Add revocation flow.

- Task P4-E1-S1-T2: Implement account stash and character fetch adapters.
  - Subtask: Write contract tests with recorded official API payloads.
  - Subtask: Fetch stash list, stash contents, character inventory, and league account data.
  - Subtask: Respect rate limits.
  - Subtask: Emit scanner events into stash adapter.

### User Story P4-E1-S2 - Public stash and currency exchange contracts

As a pricing service, I need official market-adjacent feeds handled with documented delay and rate limits.

Tasks:

- Task P4-E1-S2-T1: Integrate public stash stream contract.
  - Subtask: Test `next_change_id` pagination.
  - Subtask: Account for documented 5-minute delay.
  - Subtask: Store listing events.
  - Subtask: Deduplicate relisted items.

- Task P4-E1-S2-T2: Integrate Currency Exchange history.
  - Subtask: Test hourly timestamp pagination.
  - Subtask: Store currency pair ratios, volume, high/low stock, and confidence.
  - Subtask: Prevent requests for unavailable current-hour data.
  - Subtask: Use exchange data for chaos/divine conversion when available.

## Epic P4-E2 - Price estimation

### User Story P4-E2-S1 - Currency and commodity pricing

As a build cost estimator, I need reliable currency and commodity prices.

Tasks:

- Task P4-E2-S1-T1: Implement price timeseries.
  - Subtask: Test hourly and daily aggregation.
  - Subtask: Merge Currency Exchange, public listings, and permitted third-party datasets.
  - Subtask: Store liquidity and sample count.
  - Subtask: Emit confidence intervals.

- Task P4-E2-S1-T2: Implement divine equivalent conversion.
  - Subtask: Test chaos-to-divine, divine-to-chaos, and unavailable pair fallback.
  - Subtask: Use most recent reliable rate with timestamp.
  - Subtask: Add volatility warning.
  - Subtask: Store conversion source in build result.

### User Story P4-E2-S2 - Unique and fixed-item pricing

As a user, I need cost estimates for uniques, gems, flasks, maps, and other fixed identities.

Tasks:

- Task P4-E2-S2-T1: Implement fixed-item price lookup.
  - Subtask: Test unique base, variant, roll-sensitive and corruption-sensitive pricing.
  - Subtask: Match gems by level, quality, corruption, transfigured/imbued/exceptional status.
  - Subtask: Match flasks by unique/base and enchant.
  - Subtask: Return median, low, high, listing count, and confidence.

- Task P4-E2-S2-T2: Implement roll sensitivity.
  - Subtask: Add tests for uniques with high-value roll ranges.
  - Subtask: Bucket by roll quality.
  - Subtask: Use exact search when listing count is sufficient.
  - Subtask: Fall back to coarse price when insufficient.

### User Story P4-E2-S3 - Rare item comparable pricing

As a user, I need realistic prices for rare items without pretending exact prediction is certain.

Tasks:

- Task P4-E2-S3-T1: Implement rare-item feature vector.
  - Subtask: Test extraction of base, item level, influences, fractured/synth/eldritch state, key stats, open prefixes/suffixes, crafted mods, resist total, life/ES, DPS, gem levels.
  - Subtask: Normalize stats by slot and archetype.
  - Subtask: Add sparse feature encoding.
  - Subtask: Store explanation features.

- Task P4-E2-S3-T2: Implement comparable search estimator.
  - Subtask: Test exact-stat, weighted-stat, and relaxed-stat comparable queries.
  - Subtask: Use public listings or permitted search source.
  - Subtask: Estimate price by quantile, not single listing.
  - Subtask: Return confidence and liquidity warning.

- Task P4-E2-S3-T3: Implement learned rare price model.
  - Subtask: Build training dataset only from allowed data.
  - Subtask: Test train/validation split by time to avoid leakage.
  - Subtask: Predict price bands, not exact price.
  - Subtask: Calibrate confidence against recent sold/listing proxies where available.

## Epic P4-E3 - Build cost and budget feasibility

### User Story P4-E3-S1 - Build cost estimator

As a user, I need the estimated total cost of a build.

Tasks:

- Task P4-E3-S1-T1: Implement cost aggregation.
  - Subtask: Test sum by slot and category.
  - Subtask: Distinguish owned, buy, craft, unknown, and optional items.
  - Subtask: Convert to divine equivalent.
  - Subtask: Include confidence bands.

- Task P4-E3-S1-T2: Implement budget check.
  - Subtask: Test under-budget, over-budget, zero-budget, owned-only, and unknown-price cases.
  - Subtask: Enforce hard budget constraint.
  - Subtask: Penalize low-confidence price estimates.
  - Subtask: Explain budget failures.

### User Story P4-E3-S2 - Acquisition planner

As a user, I need to know which items to buy, craft, or use from stash.

Tasks:

- Task P4-E3-S2-T1: Create acquisition classification.
  - Subtask: Test owned, owned-craftable, buy-exact, buy-comparable, craft-from-scratch, skip.
  - Subtask: Implement classification logic.
  - Subtask: Add links/queries where policy permits.
  - Subtask: Show confidence and expected cost.

- Task P4-E3-S2-T2: Add zero-currency mode.
  - Subtask: Test owned-only optimization.
  - Subtask: Allow vendor/crafting-bench-only changes when no trade budget exists.
  - Subtask: Estimate opportunity cost separately.
  - Subtask: Explain why unowned upgrades were excluded.

## Epic P4-E4 - Owned stash upgrade detection

### User Story P4-E4-S1 - Background item scorer

As a user, I need the system to detect when a stash item improves any saved build.

Tasks:

- Task P4-E4-S1-T1: Implement candidate prefilter.
  - Subtask: Test slot compatibility, attribute requirements, gem/support relevance, damage archetype relevance, defensive relevance, and budget/ownership rules.
  - Subtask: Generate top candidate replacements per build and slot.
  - Subtask: Exclude items already equipped unless comparing roll variants.
  - Subtask: Queue only plausible upgrades for PoB evaluation.

- Task P4-E4-S1-T2: Implement PoB-validated upgrade check.
  - Subtask: Test item replacement with same config.
  - Subtask: Compute metric deltas.
  - Subtask: Apply user preference weights.
  - Subtask: Store upgrade notifications with diff and confidence.

### User Story P4-E4-S2 - Continuous stash watch

As a user, I need upgrade detection to happen after scanner updates without blocking the UI.

Tasks:

- Task P4-E4-S2-T1: Implement stash event queue.
  - Subtask: Test new item, modified item, removed item, and sold item events.
  - Subtask: Debounce frequent stash updates.
  - Subtask: Prioritize saved builds and active characters.
  - Subtask: Add idempotency keys.

- Task P4-E4-S2-T2: Implement notification API.
  - Subtask: Test unread/read/dismissed notification states.
  - Subtask: Include build name, item, metric delta, reason, and exportable PoB diff.
  - Subtask: Add severity thresholds.
  - Subtask: Add user preference controls.

---

# Phase 5 - Optimization engines

## Epic P5-E1 - Objective function and Pareto frontier

### User Story P5-E1-S1 - Multi-objective scoring

As a user, I need the optimizer to balance DPS, EHP, and cost according to my preference.

Tasks:

- Task P5-E1-S1-T1: Implement objective weights.
  - Subtask: Test Tanky/Balanced/Glass Cannon presets.
  - Subtask: Convert slider to metric weights.
  - Subtask: Add hard floors for unacceptable defences if user sets them.
  - Subtask: Store score components.

- Task P5-E1-S1-T2: Implement Pareto extraction.
  - Subtask: Test dominance relationships across DPS/EHP/cost.
  - Subtask: Extract non-dominated candidates.
  - Subtask: Cluster near-duplicate candidates.
  - Subtask: Return top N diverse results.

### User Story P5-E1-S2 - Explanation of trade-offs

As a user, I need to understand why a candidate was chosen.

Tasks:

- Task P5-E1-S2-T1: Implement score breakdown.
  - Subtask: Test per-metric contribution output.
  - Subtask: Show before/after deltas.
  - Subtask: Show cost impact.
  - Subtask: Show assumptions and confidence.

- Task P5-E1-S2-T2: Implement alternative comparison.
  - Subtask: Test comparing tanky vs balanced vs glass options.
  - Subtask: Explain what was sacrificed.
  - Subtask: Add "why not higher DPS" and "why not tankier" reasons.
  - Subtask: Surface hard constraints that blocked improvements.

## Epic P5-E2 - Passive tree optimizer

### User Story P5-E2-S1 - Tree path generator

As a build generator, I need valid passive tree paths for a class and target mechanic.

Tasks:

- Task P5-E2-S1-T1: Generate target node paths.
  - Subtask: Test target notable/keystone paths from each class start.
  - Subtask: Use k-shortest paths with cost penalties.
  - Subtask: Account for jewel sockets and cluster sockets.
  - Subtask: Reject disconnected illegal paths.

- Task P5-E2-S1-T2: Add passive point budget.
  - Subtask: Test level-based point limits and quest/bandit variants.
  - Subtask: Enforce max points.
  - Subtask: Reserve points for cluster jewels if needed.
  - Subtask: Return partial path when full path impossible.

### User Story P5-E2-S2 - Existing tree edit optimizer

As a user with an existing build, I need controlled tree changes.

Tasks:

- Task P5-E2-S2-T1: Implement tree edit distance.
  - Subtask: Test added, removed, swapped, and re-routed nodes.
  - Subtask: Count refund cost and gold/regret equivalent where supported.
  - Subtask: Respect max edit limit from request.
  - Subtask: Explain changed clusters.

- Task P5-E2-S2-T2: Implement local tree search.
  - Subtask: Test add/remove/swap neighborhood generation.
  - Subtask: Use fast evaluator for pruning.
  - Subtask: PoB-evaluate top candidates.
  - Subtask: Return legal diffs only.

### User Story P5-E2-S3 - Tree transformations

As a tree optimizer, I need to optimize tattoos, runegrafts, and jewel radius effects.

Tasks:

- Task P5-E2-S3-T1: Optimize tattoo placement.
  - Subtask: Test eligible node discovery.
  - Subtask: Generate tattoo candidates by archetype.
  - Subtask: Enforce 50 limit.
  - Subtask: PoB-validate best candidates.

- Task P5-E2-S3-T2: Optimize runegrafts.
  - Subtask: Test mastery eligibility.
  - Subtask: Generate runegraft options from current 3.28 catalog.
  - Subtask: Enforce one-of-type constraints.
  - Subtask: Include cost and acquisition metadata.

## Epic P5-E3 - Item optimizer

### User Story P5-E3-S1 - Slot replacement optimizer

As a user, I need item upgrades by slot.

Tasks:

- Task P5-E3-S1-T1: Generate slot candidate pools.
  - Subtask: Test weapon, offhand, helmet, body, gloves, boots, belt, amulet, rings, jewels, flasks.
  - Subtask: Include owned stash candidates, market candidates, generated rare templates, and uniques.
  - Subtask: Filter by budget and legality.
  - Subtask: Preserve locked slots.

- Task P5-E3-S1-T2: Evaluate replacement candidates.
  - Subtask: Test single-slot replacement.
  - Subtask: Score with fast evaluator.
  - Subtask: PoB-validate top candidates.
  - Subtask: Return metric deltas and explanations.

### User Story P5-E3-S2 - Multi-slot optimizer

As a user, I need item combinations optimized together because upgrades interact.

Tasks:

- Task P5-E3-S2-T1: Implement beam search over slots.
  - Subtask: Test interactions: resist cap, attributes, reservation, gem levels, ailment avoidance, set-like uniques.
  - Subtask: Keep diverse candidates.
  - Subtask: Respect total budget.
  - Subtask: PoB-evaluate final beam.

- Task P5-E3-S2-T2: Implement dependency resolver.
  - Subtask: Test item A requires attribute from item B.
  - Subtask: Test resistance balancing across slots.
  - Subtask: Test unique limit and slot conflicts.
  - Subtask: Explain combination dependencies.

### User Story P5-E3-S3 - Craft-aware optimizer

As a user, I need upgrades that include realistic crafted items when buying exact items is too expensive.

Tasks:

- Task P5-E3-S3-T1: Generate craft templates.
  - Subtask: Test essence, fossil, bench craft, eldritch implicit, fractured base, and cluster craft templates.
  - Subtask: Estimate expected cost from source data and market prices.
  - Subtask: Mark high-variance crafts.
  - Subtask: Provide alternative buy/craft recommendations.

- Task P5-E3-S3-T2: Validate craft outputs.
  - Subtask: Ensure generated craft result is legal.
  - Subtask: Ensure expected mod set can exist together.
  - Subtask: Add price confidence.
  - Subtask: Add PoB evaluation for template median and high-roll variants.

## Epic P5-E4 - Jewel, cluster, and Timeless optimizer

### User Story P5-E4-S1 - Cluster jewel optimizer

As a build optimizer, I need cluster jewels optimized by notables and passive count.

Tasks:

- Task P5-E4-S1-T1: Generate cluster candidates.
  - Subtask: Test base type, item level, passives count, notables, sockets.
  - Subtask: Generate candidates from stash, market, and legal templates.
  - Subtask: Estimate price.
  - Subtask: Expand subgraph into tree candidate.

- Task P5-E4-S1-T2: Evaluate cluster layouts.
  - Subtask: Test pathing cost inside cluster.
  - Subtask: Optimize notable allocation order.
  - Subtask: Include jewel sockets in downstream candidate generation.
  - Subtask: PoB-validate final clusters.

### User Story P5-E4-S2 - Timeless Jewel seed search

As a user, I need Timeless Jewels evaluated by seed and socket.

Tasks:

- Task P5-E4-S2-T1: Implement seed candidate discovery.
  - Subtask: Test known seed fixture.
  - Subtask: Generate seeds from owned stash, market listings, and full seed search where feasible.
  - Subtask: Include 3.28 Heroic Tragedy.
  - Subtask: Cache seed/socket transformations.

- Task P5-E4-S2-T2: Implement transformation scoring.
  - Subtask: Use PoB oracle for transformations initially.
  - Subtask: Score node deltas inside radius.
  - Subtask: Respect tattoo override and cluster limitations.
  - Subtask: Return seed, socket, changed nodes, and acquisition cost.

## Epic P5-E5 - Full constrained build generator

### User Story P5-E5-S1 - Random but constrained build generation

As a user, I need a random build that respects class, ascendancy, budget, DPS/EHP preferences, and league legality.

Tasks:

- Task P5-E5-S1-T1: Implement archetype seed generator.
  - Subtask: Test class/ascendancy hard requirements.
  - Subtask: Generate skill archetypes by tags and ascendancy synergy.
  - Subtask: Include random seed for reproducibility.
  - Subtask: Reject archetypes with no legal skill/item path.

- Task P5-E5-S1-T2: Implement full candidate assembly.
  - Subtask: Generate tree, ascendancy, skills, items, flasks, jewels, tattoos, runegrafts, and config.
  - Subtask: Enforce budget and legal constraints.
  - Subtask: Use staged evaluation.
  - Subtask: Return diverse candidates.

- Task P5-E5-S1-T3: Implement randomness controls.
  - Subtask: Test reproducible random build by seed.
  - Subtask: Add weirdness/novelty slider.
  - Subtask: Prevent obviously non-functional combinations.
  - Subtask: Store generation path for explanation.

### User Story P5-E5-S2 - Build viability gates

As a user, I need generated builds to be playable, not just technically high-scoring.

Tasks:

- Task P5-E5-S2-T1: Add baseline viability checks.
  - Subtask: Test capped resistances, required attributes, main skill usable, mana/reservation feasibility, flask availability, minimum movement, minimum recovery.
  - Subtask: Add configurable floors.
  - Subtask: Reject candidates that only work under unrealistic conditions.
  - Subtask: Explain rejection reasons.

- Task P5-E5-S2-T2: Add content-target presets.
  - Subtask: Test campaign, early maps, red maps, pinnacle, uber, simulacrum/deep delve-style presets if supported.
  - Subtask: Set target minimums by preset.
  - Subtask: Allow user override.
  - Subtask: Show confidence.

## Epic P5-E6 - Existing build optimizer

### User Story P5-E6-S1 - Damage optimization mode

As a user, I need an existing build optimized for damage within a tree edit limit and budget.

Tasks:

- Task P5-E6-S1-T1: Implement damage candidate search.
  - Subtask: Lock user-specified items and skills.
  - Subtask: Generate tree, gem, item, jewel, flask upgrades.
  - Subtask: Respect max tree edits.
  - Subtask: Optimize hit/average/full DPS according to request.

- Task P5-E6-S1-T2: Validate before/after in PoB.
  - Subtask: Use identical configuration.
  - Subtask: Compare metrics.
  - Subtask: Return build diff.
  - Subtask: Explain cost and trade-offs.

### User Story P5-E6-S2 - Tankiness optimization mode

As a user, I need an existing build optimized for survivability within a tree edit limit and budget.

Tasks:

- Task P5-E6-S2-T1: Implement defensive candidate search.
  - Subtask: Generate life/ES/armour/evasion/suppression/block/max-res/ailment/recovery upgrades.
  - Subtask: Preserve minimum DPS floor if user sets it.
  - Subtask: Respect max tree edits and budget.
  - Subtask: Include owned items first.

- Task P5-E6-S2-T2: Validate defensive improvements.
  - Subtask: Compare EHP, max hit by damage type, recovery, and avoidance.
  - Subtask: Warn if PoB config hides a defensive weakness.
  - Subtask: Return alternatives with different DPS losses.
  - Subtask: Explain exact changes.

## Epic P5-E7 - Owned-stash optimizer

### User Story P5-E7-S1 - Zero-budget upgrade mode

As a user with no currency, I need the best upgrades using only owned items.

Tasks:

- Task P5-E7-S1-T1: Generate owned-only candidates.
  - Subtask: Use account stash and character inventory.
  - Subtask: Include socket/link feasibility.
  - Subtask: Include cheap bench crafts only if configured.
  - Subtask: Reject any trade-required item.

- Task P5-E7-S1-T2: Rank owned upgrades.
  - Subtask: Evaluate per-slot and multi-slot combinations.
  - Subtask: Use PoB for final validation.
  - Subtask: Explain why an owned item is an upgrade.
  - Subtask: Add equip checklist.

---

# Phase 6 - Machine learning and build intelligence

## Epic P6-E1 - Build corpus

### User Story P6-E1-S1 - Corpus ingestion

As an ML system, I need a clean corpus of builds that can be used for ranking and archetype discovery.

Tasks:

- Task P6-E1-S1-T1: Define allowed corpus sources.
  - Subtask: Test source policy for user-submitted builds, saved builds, public ladder/build sites where terms allow, and generated builds.
  - Subtask: Store consent/permission metadata.
  - Subtask: Remove private account identifiers unless needed by user.
  - Subtask: Add deletion support.

- Task P6-E1-S1-T2: Normalize builds into features.
  - Subtask: Extract class, ascendancy, skills, supports, tree nodes, items, stat vectors, costs, and PoB metrics.
  - Subtask: Deduplicate near-identical builds.
  - Subtask: Store time and league.
  - Subtask: Add quality filters.

### User Story P6-E1-S2 - Archetype library

As a generator, I need build archetypes to seed realistic candidates.

Tasks:

- Task P6-E1-S2-T1: Cluster builds by archetype.
  - Subtask: Test clustering by main skill, ascendancy, damage type, defence style, item core, and tree region.
  - Subtask: Create archetype summaries.
  - Subtask: Store popularity and price trend.
  - Subtask: Mark stale archetypes after patches.

- Task P6-E1-S2-T2: Generate archetype constraints.
  - Subtask: Convert clusters into soft templates.
  - Subtask: Identify required uniques or mechanics.
  - Subtask: Identify flexible slots.
  - Subtask: Feed templates to candidate generator.

## Epic P6-E2 - Surrogate models and learned ranking

### User Story P6-E2-S1 - Candidate ranking model

As an optimizer, I need a learned ranker to reduce expensive PoB calls.

Tasks:

- Task P6-E2-S1-T1: Train ranking model.
  - Subtask: Use PoB-validated candidates as labels.
  - Subtask: Split by time and archetype.
  - Subtask: Predict relative improvement probability.
  - Subtask: Track false negatives carefully.

- Task P6-E2-S1-T2: Integrate ranker safely.
  - Subtask: Use model only for ordering, not legality.
  - Subtask: Add fallback when confidence is low.
  - Subtask: Monitor ranker impact on discovered Pareto candidates.
  - Subtask: Disable ranker automatically after patch drift.

### User Story P6-E2-S2 - Price prediction model

As a pricing service, I need rare-item price bands when comparable search is weak.

Tasks:

- Task P6-E2-S2-T1: Train rare price estimator.
  - Subtask: Use allowed listing history only.
  - Subtask: Predict price band and confidence.
  - Subtask: Calibrate by league age and item slot.
  - Subtask: Track high-error categories.

- Task P6-E2-S2-T2: Integrate price model.
  - Subtask: Use model as fallback or supplement to comparable search.
  - Subtask: Never present learned price as exact.
  - Subtask: Include confidence and data age.
  - Subtask: Add user-facing warnings.

## Epic P6-E3 - Recommendation and novelty

### User Story P6-E3-S1 - Similar-build recommendations

As a user, I need suggestions based on builds similar to mine.

Tasks:

- Task P6-E3-S1-T1: Build similarity index.
  - Subtask: Encode tree, skills, items, ascendancy, metrics, and budget.
  - Subtask: Test nearest-neighbor retrieval.
  - Subtask: Filter by league and patch.
  - Subtask: Explain similarities.

- Task P6-E3-S1-T2: Use similar builds for upgrades.
  - Subtask: Identify common item/tree/gem differences.
  - Subtask: Convert differences into legal candidates.
  - Subtask: Price and PoB-validate suggestions.
  - Subtask: Show popularity vs novelty trade-off.

### User Story P6-E3-S2 - Novel build generation

As a user, I need random builds that are not all current meta clones.

Tasks:

- Task P6-E3-S2-T1: Implement novelty scoring.
  - Subtask: Measure distance from common archetypes.
  - Subtask: Penalize impossible/weird-but-bad combinations.
  - Subtask: Add user novelty slider.
  - Subtask: Keep all hard constraints.

- Task P6-E3-S2-T2: Validate novel builds.
  - Subtask: Require PoB metrics above minimum floors.
  - Subtask: Add confidence warnings for unsupported/rare mechanics.
  - Subtask: Return at least one safer alternative.
  - Subtask: Store novelty explanation.

---

# Phase 7 - Backend API and Web UI integration

## Epic P7-E1 - API contracts

### User Story P7-E1-S1 - Optimization API

As the existing Web UI, I need stable endpoints to request build generation and optimization.

Tasks:

- Task P7-E1-S1-T1: Define REST/GraphQL contracts.
  - Subtask: Add request/response schema tests.
  - Subtask: Implement create optimization request endpoint.
  - Subtask: Implement status endpoint.
  - Subtask: Implement result endpoint.

- Task P7-E1-S1-T2: Add asynchronous job support.
  - Subtask: Test queued, running, completed, failed, cancelled states.
  - Subtask: Add progress phases.
  - Subtask: Support cancellation.
  - Subtask: Persist intermediate candidates where useful.

### User Story P7-E1-S2 - Build import/export API

As the UI, I need to import and export PoB/build data.

Tasks:

- Task P7-E1-S2-T1: Implement import endpoint.
  - Subtask: Accept PoB code, character reference, or saved build ID.
  - Subtask: Validate and normalize.
  - Subtask: Return parsed summary.
  - Subtask: Store build with source metadata.

- Task P7-E1-S2-T2: Implement export endpoint.
  - Subtask: Return PoB code.
  - Subtask: Return build diff.
  - Subtask: Return shopping/crafting checklist.
  - Subtask: Return source/citation metadata.

## Epic P7-E2 - User workflows

### User Story P7-E2-S1 - Random constrained build workflow

As a user, I need to create a new build from constraints.

Tasks:

- Task P7-E2-S1-T1: Implement UI form contract.
  - Subtask: Fields: game version, league, class, ascendancy, level, budget, slider, skill preference, owned-only toggle, output count.
  - Subtask: Validate hard requirements client and server side.
  - Subtask: Show assumptions.
  - Subtask: Submit job.

- Task P7-E2-S1-T2: Render results.
  - Subtask: Show Pareto cards.
  - Subtask: Show DPS/EHP/cost/confidence.
  - Subtask: Show top changes and assumptions.
  - Subtask: Provide PoB export.

### User Story P7-E2-S2 - Existing build optimization workflow

As a user, I need to upload a build and optimize it.

Tasks:

- Task P7-E2-S2-T1: Implement import flow.
  - Subtask: Accept PoB code and account character.
  - Subtask: Show parsed current metrics.
  - Subtask: Let user lock items/tree/gems.
  - Subtask: Let user set tree edit limit and budget.

- Task P7-E2-S2-T2: Render diff results.
  - Subtask: Show before/after metrics.
  - Subtask: Show tree diff.
  - Subtask: Show item/gem/flask changes.
  - Subtask: Show buy/use-owned/craft checklist.

### User Story P7-E2-S3 - Stash upgrade workflow

As a user, I need background recommendations from my stash.

Tasks:

- Task P7-E2-S3-T1: Implement saved build watcher UI.
  - Subtask: Let user enable/disable monitoring per build.
  - Subtask: Show last scan and source versions.
  - Subtask: Show notifications.
  - Subtask: Provide dismiss/snooze settings.

- Task P7-E2-S3-T2: Implement item detail explanation.
  - Subtask: Show why the stash item improves the build.
  - Subtask: Show metric deltas.
  - Subtask: Show item location.
  - Subtask: Provide PoB export with item equipped.

## Epic P7-E3 - Trust and explainability

### User Story P7-E3-S1 - Source and confidence display

As a user, I need to know why the result should be trusted.

Tasks:

- Task P7-E3-S1-T1: Show source versions.
  - Subtask: Display PoE version, PoB version, RePoE version, price data timestamp.
  - Subtask: Show stale-source warnings.
  - Subtask: Show unsupported mechanic warnings.
  - Subtask: Link to source policy.

- Task P7-E3-S1-T2: Show confidence.
  - Subtask: Confidence by calculation, price, item availability, and config completeness.
  - Subtask: Color-code low confidence.
  - Subtask: Add tooltip explanations.
  - Subtask: Include confidence in exported report.

---

# Phase 8 - Quality, benchmarking, and regression

## Epic P8-E1 - Test pyramid completion

### User Story P8-E1-S1 - Unit and property tests

As a development lead, I need broad unit/property coverage over combinatorial mechanics.

Tasks:

- Task P8-E1-S1-T1: Add property tests for item legality.
  - Subtask: Randomly generate legal and illegal item states.
  - Subtask: Assert legal generator never creates impossible combinations.
  - Subtask: Assert validator rejects injected illegal combinations.
  - Subtask: Store seed on failure.

- Task P8-E1-S1-T2: Add property tests for tree paths.
  - Subtask: Generate random target sets.
  - Subtask: Assert connectedness and point limits.
  - Subtask: Assert edit distance is symmetric where appropriate.
  - Subtask: Store failing tree path seed.

### User Story P8-E1-S2 - Integration and e2e tests

As a release manager, I need complete workflow tests.

Tasks:

- Task P8-E1-S2-T1: E2E random build test.
  - Subtask: Submit constrained random build request.
  - Subtask: Wait for result.
  - Subtask: Validate PoB export.
  - Subtask: Assert class/ascendancy/budget constraints.

- Task P8-E1-S2-T2: E2E existing build optimization test.
  - Subtask: Import PoB fixture.
  - Subtask: Optimize for tankiness with tree edit limit.
  - Subtask: Validate metrics improved or explain impossible.
  - Subtask: Validate diff respects edit limit.

- Task P8-E1-S2-T3: E2E stash upgrade test.
  - Subtask: Feed account stash fixture.
  - Subtask: Trigger background scoring.
  - Subtask: Validate notification.
  - Subtask: Validate exported PoB with upgrade.

## Epic P8-E2 - Performance and scale

### User Story P8-E2-S1 - Candidate throughput benchmark

As an optimizer, I need to search enough candidates within interactive limits.

Tasks:

- Task P8-E2-S1-T1: Benchmark candidate generation.
  - Subtask: Measure items/sec, trees/sec, gem setups/sec.
  - Subtask: Add baseline thresholds.
  - Subtask: Track regressions.
  - Subtask: Add flamegraph support.

- Task P8-E2-S1-T2: Benchmark PoB oracle throughput.
  - Subtask: Measure cold start and warm eval time.
  - Subtask: Test parallel workers.
  - Subtask: Test cache hit rate.
  - Subtask: Set queue limits.

### User Story P8-E2-S2 - Memory and storage bounds

As an operator, I need predictable resource usage.

Tasks:

- Task P8-E2-S2-T1: Add cache sizing tests.
  - Subtask: Test LRU eviction.
  - Subtask: Test source-version invalidation.
  - Subtask: Test large stash accounts.
  - Subtask: Add storage metrics.

## Epic P8-E3 - Patch regression

### User Story P8-E3-S1 - Patch-day protocol

As a maintainer, I need a repeatable patch-day process.

Tasks:

- Task P8-E3-S1-T1: Create patch-day checklist.
  - Subtask: Fetch official patch notes.
  - Subtask: Fetch PoB release/candidate branch.
  - Subtask: Fetch current data exports.
  - Subtask: Run source drift report.

- Task P8-E3-S1-T2: Run regression suite.
  - Subtask: Run golden fixtures.
  - Subtask: Run parser unknown-line report.
  - Subtask: Run price source sanity checks.
  - Subtask: Publish compatibility status.

### User Story P8-E3-S2 - Mechanics coverage regression

As a maintainer, I need new mechanics to become explicit backlog items.

Tasks:

- Task P8-E3-S2-T1: Detect new stats/mods/items/gems.
  - Subtask: Diff data export against previous version.
  - Subtask: Group changes by mechanic.
  - Subtask: Create backlog stubs.
  - Subtask: Mark affected modules.

- Task P8-E3-S2-T2: Quarantine unsupported mechanics.
  - Subtask: If a new mechanic lacks parser/calculator support, tag affected builds as low confidence.
  - Subtask: Prevent final recommendations that rely on unsupported mechanic unless user allows experimental.
  - Subtask: Show warnings.
  - Subtask: Add tests once implemented.

---

# Phase 9 - Operations, observability, and agent orchestration

## Epic P9-E1 - Scheduled jobs

### User Story P9-E1-S1 - Data sync schedules

As an operator, I need scheduled sync jobs for data, PoB, pricing, and stashes.

Tasks:

- Task P9-E1-S1-T1: Implement scheduler.
  - Subtask: Schedule PoB release checks daily or more often during patch windows.
  - Subtask: Schedule RePoE/data checks daily.
  - Subtask: Schedule pricing updates according to source policy.
  - Subtask: Schedule account stash refresh according to user settings and rate limits.

- Task P9-E1-S1-T2: Add job status API.
  - Subtask: Show last run, next run, status, errors.
  - Subtask: Store logs.
  - Subtask: Add retry controls.
  - Subtask: Add kill-switches.

## Epic P9-E2 - Observability

### User Story P9-E2-S1 - Metrics and traces

As an operator, I need to understand optimizer behavior and failures.

Tasks:

- Task P9-E2-S1-T1: Add service metrics.
  - Subtask: Track API latency, queue depth, PoB eval time, cache hit rate, candidate counts, error rates.
  - Subtask: Track price confidence and stale-source counts.
  - Subtask: Track optimizer success/failure by request type.
  - Subtask: Add dashboards.

- Task P9-E2-S1-T2: Add trace IDs.
  - Subtask: Propagate trace ID from UI request through optimizer, PoB, pricing, and stash adapter.
  - Subtask: Include trace ID in result debug output.
  - Subtask: Add log correlation.
  - Subtask: Add user-safe support bundle export.

## Epic P9-E3 - Agentic implementation operations

### User Story P9-E3-S1 - Agent backlog execution

As a technical lead, I need agents to implement stories without corrupting adjacent modules.

Tasks:

- Task P9-E3-S1-T1: Generate per-story task files.
  - Subtask: Include context, allowed files, dependencies, tests to create, acceptance criteria.
  - Subtask: Include source references where needed.
  - Subtask: Include rollback instructions.
  - Subtask: Include review checklist.

- Task P9-E3-S1-T2: Add automatic story verification.
  - Subtask: CI maps changed files to story boundaries.
  - Subtask: CI checks required tests exist.
  - Subtask: CI runs affected test suites.
  - Subtask: CI blocks unapproved cross-module edits.

### User Story P9-E3-S2 - Human review gates

As the owner, I need high-risk modules reviewed carefully.

Tasks:

- Task P9-E3-S2-T1: Mark high-risk stories.
  - Subtask: High-risk: API compliance, PoB sync, pricing, calculation metrics, optimization scoring, OAuth/token handling.
  - Subtask: Require human approval for release.
  - Subtask: Require source citation in PR.
  - Subtask: Require regression evidence.

## Epic P9-E4 - Documentation and runbooks

### User Story P9-E4-S1 - Developer documentation

As a developer/agent, I need enough docs to extend mechanics safely.

Tasks:

- Task P9-E4-S1-T1: Write mechanics extension guide.
  - Subtask: Explain adding a new item mechanic.
  - Subtask: Explain adding a new tree mechanic.
  - Subtask: Explain adding a new skill config.
  - Subtask: Explain adding golden fixtures.

- Task P9-E4-S1-T2: Write data source guide.
  - Subtask: Explain source trust levels.
  - Subtask: Explain patch-day workflow.
  - Subtask: Explain source drift handling.
  - Subtask: Explain API policy constraints.

### User Story P9-E4-S2 - User-facing documentation

As a user, I need to understand recommendations and limitations.

Tasks:

- Task P9-E4-S2-T1: Write user guide for build generation.
  - Subtask: Explain class/ascendancy hard requirements.
  - Subtask: Explain budget and owned-only mode.
  - Subtask: Explain Tanky-to-Glass-Cannon slider.
  - Subtask: Explain PoB assumptions.

- Task P9-E4-S2-T2: Write user guide for optimization.
  - Subtask: Explain tree edit limits.
  - Subtask: Explain why cost estimates have confidence bands.
  - Subtask: Explain stash upgrade notifications.
  - Subtask: Explain exporting to PoB.

---

# Phase 10 - MVP sequencing

## Epic P10-E1 - MVP 1: Correctness-first optimizer core

### User Story P10-E1-S1 - Deliver first useful build improvement loop

As an early user, I need to import a build, evaluate it, and get a few verified improvements.

Tasks:

- Task P10-E1-S1-T1: MVP import/evaluate/export.
  - Subtask: Implement PoB import.
  - Subtask: Implement PoB oracle evaluation.
  - Subtask: Implement Build IR export.
  - Subtask: Add e2e test.

- Task P10-E1-S1-T2: MVP item replacement.
  - Subtask: Use owned stash candidates and fixed unique/gem prices.
  - Subtask: Evaluate single-slot replacements.
  - Subtask: Respect budget.
  - Subtask: Return explainable diff.

- Task P10-E1-S1-T3: MVP limited tree optimization.
  - Subtask: Support edit distance up to a small fixed number.
  - Subtask: Optimize a preselected set of nearby nodes.
  - Subtask: PoB-validate final tree diff.
  - Subtask: Export PoB.

## Epic P10-E2 - MVP 2: Budget-aware generation

### User Story P10-E2-S1 - Generate constrained builds

As a user, I need random constrained builds that are validated by PoB and priced.

Tasks:

- Task P10-E2-S1-T1: Generate from archetype templates.
  - Subtask: Build template library from verified fixtures.
  - Subtask: Generate class/ascendancy-legal candidates.
  - Subtask: Add simple item candidate pools.
  - Subtask: PoB-validate and price.

- Task P10-E2-S1-T2: Add Pareto output.
  - Subtask: Return Tanky/Balanced/Glass options.
  - Subtask: Show cost/confidence.
  - Subtask: Export all candidates.
  - Subtask: Add UI contract.

## Epic P10-E3 - MVP 3: Continuous stash intelligence

### User Story P10-E3-S1 - Background upgrade detection

As a user, I need stash items checked against saved builds.

Tasks:

- Task P10-E3-S1-T1: Implement background scorer.
  - Subtask: Use scanner adapter events.
  - Subtask: Prefilter candidates.
  - Subtask: PoB-validate plausible upgrades.
  - Subtask: Notify user.

- Task P10-E3-S1-T2: Add saved-build monitoring UI.
  - Subtask: Enable/disable per build.
  - Subtask: Show notifications.
  - Subtask: Export diff.
  - Subtask: Add e2e test.

## 7. Risk register

| Risk | Severity | Reason | Mitigation |
|---|---:|---|---|
| PoB drift | High | PoB updates often and fixes current mechanics quickly | Version-pinned oracle, candidate/active versions, golden regression before promotion |
| Rare item pricing inaccuracy | High | Comparable listings can be sparse/manipulated | Price bands, liquidity confidence, multiple sources, no exact claims |
| API access/rate limits | High | GGG rate limits are dynamic and access can be revoked | Official scopes only, dynamic headers, queues, User-Agent, kill-switches |
| Unsupported mechanics | High | PoE adds/changes mechanics every league | Mechanic registry, coverage reports, warnings, quarantine |
| Full build search space explosion | High | Tree/items/gems/jewels create huge combinations | Staged search, heuristics, ML ranker, PoB only for top candidates |
| Misleading DPS/EHP | High | Config-dependent metrics | Canonical config presets, visible assumptions, confidence scoring |
| Agent overreach | Medium | LLM agents may change unrelated modules | Story boundaries, CI file guards, required tests, human gates |
| Repository integration uncertainty | Medium | Existing repo was not inspectable here | Integration contracts first, adapter tests, defer implementation coupling |
| Legal/ToS risk | High | Undocumented endpoints/game-file interaction may violate policies | Source policy registry, official APIs, no in-game automation, policy review |

## 8. Source-backed implementation decisions

- Use PoB as a calculation oracle first. PoB publicly describes comprehensive offence and defence calculations, import/export, item planning, trade search, and automatic updating, but it does not claim perfect coverage of every modifier. It explicitly distinguishes supported and unsupported modifiers.
- Use official API docs as the compliance boundary. Official docs emphasize OAuth, rate limits, User-Agent requirements, and restrictions on undocumented resources.
- Use RePoE/PyPoE-style exports as data ingestion input, but not as the only source of truth for calculations.
- Use the passive tree JSON model and reject stale tree data.
- Use ML as an acceleration and recommendation layer, never as the truth layer.

## 9. Agent task template

Each story assigned to an agent should be written like this:

```yaml
story_id: P1-E3-S2
title: Affix legality engine
objective: Implement legal modifier applicability for current 3.28 item candidates.
allowed_files:
  - packages/game-ontology/**
  - packages/test-fixtures/items/**
forbidden_files:
  - packages/pob-oracle/**
  - packages/optimizer/**
inputs:
  - RePoE mods/base_items/tags fixtures
  - SourceVersion schema
required_tests:
  - unit: mod applicability by base tag and item class
  - property: generated rare items are legal
  - snapshot: current 3.28 mod fixture loads
acceptance_criteria:
  - invalid influence/base combinations are rejected
  - prefix/suffix limits are enforced
  - mod group exclusivity is enforced
  - all test suites pass
notes:
  - do not implement pricing in this story
  - do not add PoB evaluation in this story
```

## 10. Reference sources

1. Official Path of Exile 3.28.0 patch notes: https://www.pathofexile.com/forum/view-thread/3913392
2. Official Path of Exile 3.28.0g patch notes: https://www.pathofexile.com/forum/view-thread/3928888
3. Official Path of Exile Developer Docs: https://www.pathofexile.com/developer/docs
4. Official Path of Exile API Reference: https://www.pathofexile.com/developer/docs/reference
5. Official Path of Exile OAuth / Authorization docs: https://www.pathofexile.com/developer/docs/authorization
6. PathOfBuildingCommunity / PathOfBuilding repository: https://github.com/PathOfBuildingCommunity/PathOfBuilding
7. PathOfBuildingCommunity / PathOfBuilding v2.65.0 release information: https://newreleases.io/project/github/PathOfBuildingCommunity/PathOfBuilding/release/v2.65.0
8. RePoE fork data export landing page: https://repoe-fork.github.io/
9. RePoE 3.28.0.7 export listing: https://repoe-fork.github.io/stat_translations/
10. GGG passive skill tree export repository: https://github.com/grindinggear/skilltree-export
11. PoE Wiki - Passive Skill Tree JSON: https://www.poewiki.net/wiki/Passive_Skill_Tree_JSON
12. PoE Wiki - Passive skill mechanics including tattoos/runegrafts: https://www.poewiki.net/wiki/Passive_skill
13. PoE Wiki - Tattoo: https://www.poewiki.net/wiki/Tattoo
14. PoE Wiki - Runegraft: https://www.poewiki.net/wiki/Runegraft
15. PoE Wiki - Timeless Jewel: https://www.poewiki.net/wiki/Timeless_Jewel
16. PoE Wiki - Heroic Tragedy: https://www.poewiki.net/wiki/Heroic_Tragedy
17. poe.ninja Path of Building configuration FAQ: https://poe.ninja/faq/pob-configuration

