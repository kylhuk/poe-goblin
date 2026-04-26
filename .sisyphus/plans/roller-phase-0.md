# PoE-Goblin Build Optimizer - Phase 0 Governance & Foundations

## TL;DR
> **Summary**: Implement only the Phase 0 foundation from `roller-plan.md`: source authority, compliance guardrails, agent-task contracts, deterministic test harnessing, and canonical request/metric definitions.
> **Deliverables**: source registry + trust policy, freshness/drift gates, API/rate-limit policy, agent task template + branch/PR conventions, deterministic fixture/seeding contract, `OptimizationRequest`, `BuildConfiguration`, and `MetricVector` schemas.
> **Effort**: Medium
> **Parallel**: YES - 3 waves
> **Critical Path**: Source registry -> freshness gate -> trust policy -> request/config/metric contracts -> drift review queue

## Context
### Original Request
Create a Sisyphus plan that focuses only on Phase 0 of `roller-plan.md`.

### Interview Summary
- Repo already has strong contract/gate patterns: `.machine/runtime/schemas/*.json`, `poe_trade/qa_contract.py`, `poe_trade/ml/contract.py`, `poe_trade/strategy/registry.py`, `poe_trade/db/migrations.py`, `poe_trade/ingestion/rate_limit.py`.
- Test gates exist for unit, API contract, CLI smoke, deterministic CI, and product QA; frontend QA is CI-configured but not fully inspectable in this snapshot.
- No shipped code was found for `SourceVersion`, `GameVersion`, `OptimizationRequest`, `MetricVector`, or `PatchDriftEvent`, so the plan must treat them as new foundation artifacts.

### Metis Review (gaps addressed)
- Keep the plan as a governance/specification deliverable only.
- Do not drift into later phases, training, UI work, or optimization execution.
- Make every new artifact explicit: owner, shape, validation, tests, and evidence path.
- Reuse existing repo naming for contract/gate/registry/test files and `.sisyphus/evidence/*` proofs.

## Work Objectives
### Core Objective
Establish the non-negotiable foundation that later optimizer phases depend on: authoritative source tracking, compliance policy, drift detection, agent-task discipline, reproducible QA, and canonical optimization request/metric contracts.

### Deliverables
- Versioned source registry with checksum and trust metadata.
- Freshness gate and source-trust policy.
- API policy and shared rate-limit handling contract.
- Third-party data policy registry with attribution/kill-switch metadata.
- Patch drift detector and review queue.
- Agent task template plus branch/PR conventions.
- Deterministic test harness and seed propagation utilities.
- Canonical `OptimizationRequest`, `BuildConfiguration`, and `MetricVector` contracts.

### Definition of Done (verifiable conditions with commands)
- Targeted story tests pass for every Phase 0 task.
- `.venv/bin/pytest tests/unit` passes.
- `make ci-api-contract` passes for contract-touching work.
- `make ci-deterministic` passes for seeded/evidence-bearing work.
- Any task that touches repo-wide contracts has a named evidence file under `.sisyphus/evidence/`.

### Must Have
- Tests-first implementation for every story.
- Explicit scope fences: Phase 0 only.
- Deterministic evidence and reproducible seeds where applicable.
- Exact failure behavior for invalid version, policy, or contract inputs.

### Must NOT Have
- No Phase 1+ ingestion, optimization, pricing, or UI work.
- No undocumented API endpoints or reverse-engineered integrations.
- No monolithic ML model as source of truth.
- No silent acceptance of version drift or policy violations.
- No frontend expansion beyond what the current snapshot can evidence.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: **TDD (RED-GREEN-REFACTOR)** for each task; story completion requires tests before code.
- QA policy: every task includes one happy-path and one failure-path agent scenario.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`
- Command ladder: targeted pytest node -> `.venv/bin/pytest tests/unit` -> `make ci-api-contract` (when contracts change) -> `make ci-deterministic` (when seeds/evidence change).

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave where dependencies allow.

**Wave 1: Foundations and shared contracts**
- P0-E1-S1-T1 Source registry schema
- P0-E1-S2-T1 API policy module
- P0-E1-S2-T2 Dynamic rate-limit contract
- P0-E2-S1-T1 Agent task template
- P0-E2-S1-T2 Branch and PR conventions
- P0-E2-S2-T1 Test harness skeleton

**Wave 2: Policy gates and drift control**
- P0-E1-S1-T2 Source freshness gate
- P0-E1-S1-T3 Source trust policy
- P0-E1-S2-T3 Third-party data policy registry
- P0-E1-S3-T1 Version drift detector
- P0-E1-S3-T2 Patch review queue
- P0-E2-S2-T2 Deterministic seed utilities

**Wave 3: Request/configuration contracts**
- P0-E3-S1-T1 OptimizationRequest schema
- P0-E3-S1-T2 Hard-constraint validation
- P0-E3-S2-T1 MetricVector schema
- P0-E3-S2-T2 Default configuration presets

### Dependency Matrix (full, all tasks)
- **1** `Source registry schema` -> no blockers.
- **2** `Source freshness gate` -> blocked by **1**.
- **3** `Source trust policy` -> blocked by **1**.
- **4** `API policy module` -> no blockers; can run with **1**.
- **5** `Dynamic rate-limit contract` -> blocked by **4**.
- **6** `Third-party data policy registry` -> blocked by **4** and **5**.
- **7** `Version drift detector` -> blocked by **1**, **2**, **3**, **6**.
- **8** `Patch review queue` -> blocked by **7**.
- **9** `Agent task template` -> no blockers.
- **10** `Branch and PR conventions` -> blocked by **9**.
- **11** `Test harness skeleton` -> no blockers.
- **12** `Deterministic seed utilities` -> blocked by **11**.
- **13** `OptimizationRequest schema` -> no blockers.
- **14** `Hard-constraint validation` -> blocked by **13**.
- **15** `MetricVector schema` -> no blockers.
- **16** `Default configuration presets` -> blocked by **15**.

### Agent Dispatch Summary
- Wave 1 -> 6 tasks -> categories: `quick`, `deep`, `unspecified-high`
- Wave 2 -> 6 tasks -> categories: `deep`, `unspecified-high`, `quick`
- Wave 3 -> 4 tasks -> categories: `deep`, `quick`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Source registry schema

  **What to do**: Create a versioned source registry artifact for `SourceVersion` plus the companion `GameVersion` record used by freshness checks. Require source name, game version, fetched-at, checksum, parser version, trust level, and canonical source URI; add validation for missing or empty checksums and stable IDs.
  **Must NOT do**: Do not ingest live sources or wire polling/cutover behavior yet.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: new foundation schema with downstream policy impact.
  - Skills: `[]` - Reason: no extra skill pack needed.
  - Omitted: `quick` - Reason: this is not a trivial single-file patch.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 3, 7 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/db/migrations.py` - checksum/versioned artifact handling.
  - Pattern: `tests/unit/test_migrations.py` - deterministic version and checksum assertions.
  - Pattern: `poe_trade/strategy/registry.py` - canonical registry metadata pattern.
  - Pattern: `tests/unit/test_strategy_registry.py` - registry contract tests.
  - Pattern: `.machine/runtime/schemas/acceptance_gate.schema.json` - evidence-rich gate shape.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `tests/unit/test_source_registry.py` exists and fails before implementation.
  - [ ] Registry rejects records without checksums.
  - [ ] Source version records preserve source name, game version, parser version, trust level, and timestamp.
  - [ ] Game version comparisons are deterministic and serialized.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Valid source record passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_source_registry.py -q`
    Expected: All assertions pass and the record round-trips.
    Evidence: .sisyphus/evidence/task-1-source-registry.txt

  Scenario: Missing checksum is rejected
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_source_registry.py -q -k checksum`
    Expected: Test asserts a validation error for empty/missing checksum.
    Evidence: .sisyphus/evidence/task-1-source-registry-error.txt
  ```

  **Commit**: YES | Message: `feat(source-registry): add versioned source manifest` | Files: `poe_trade/source_registry.py`, `tests/unit/test_source_registry.py`

- [ ] 2. Source freshness gate

  **What to do**: Add a freshness gate that rejects mismatched game versions/leagues and supports explicit archived-build override only with confirmation. Emit a structured warning when source dates differ or when a source is out of the active game window.
  **Must NOT do**: Do not auto-fall through stale sources or silently normalize version mismatches.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: gate logic depends on source/version semantics.
  - Skills: `[]` - Reason: standard repository patterns are sufficient.
  - Omitted: `quick` - Reason: multiple failure paths and explicit override behavior.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7 | Blocked By: 1

  **References**:
  - Pattern: `poe_trade/config/settings.py` - explicit runtime configuration pattern.
  - Pattern: `poe_trade/ingestion/rate_limit.py` - structured policy and header-driven behavior.
  - Pattern: `tests/unit/test_rate_limit.py` - negative-path header fixtures.
  - Pattern: `poe_trade/db/migrations.py` - strict version ordering semantics.

  **Acceptance Criteria**:
  - [ ] 3.27 source data is rejected for a 3.28 request by default.
  - [ ] Archived-build override requires explicit opt-in.
  - [ ] Structured warning is emitted when source date or game version differs.
  - [ ] The gate is covered by deterministic unit tests.

  **QA Scenarios**:
  ```
  Scenario: Matching source version passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_source_freshness.py -q`
    Expected: Active 3.28 source passes without warnings.
    Evidence: .sisyphus/evidence/task-2-freshness-pass.txt

  Scenario: Wrong league is rejected
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_source_freshness.py -q -k wrong_league`
    Expected: Validation failure asserts the mismatch.
    Evidence: .sisyphus/evidence/task-2-freshness-fail.txt
  ```

  **Commit**: YES | Message: `feat(source-freshness): reject stale game data` | Files: `poe_trade/source_freshness.py`, `tests/unit/test_source_freshness.py`

- [ ] 3. Source trust policy

  **What to do**: Define authoritative trust levels and conflict resolution rules so official sources outrank community exports, and non-authoritative sources are annotated in build results and audit logs.
  **Must NOT do**: Do not let community-export or manual overrides become calculation truth without explicit policy metadata.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: policy hierarchy and audit trail design.
  - Skills: `[]` - Reason: no special tooling required.
  - Omitted: `quick` - Reason: policy conflicts need more than a trivial edit.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 8 | Blocked By: 1

  **References**:
  - Pattern: `poe_trade/qa_contract.py` - reproducible policy/evidence state capture.
  - Pattern: `poe_trade/ml/contract.py` - frozen contract metadata model.
  - Pattern: `.machine/runtime/schemas/review_gate.schema.json` - severity-aware review output.
  - Pattern: `.machine/runtime/schemas/proof_audit.schema.json` - explicit gap categories.

  **Acceptance Criteria**:
  - [ ] Official sources outrank community exports on conflicts.
  - [ ] Sources marked non-authoritative cannot silently drive exact calculations.
  - [ ] Every build result carries source-use audit metadata.
  - [ ] Conflict tests cover manual override and replaceable-source cases.

  **QA Scenarios**:
  ```
  Scenario: Official data wins
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_source_policy.py -q`
    Expected: Conflict resolution prefers official source metadata.
    Evidence: .sisyphus/evidence/task-3-trust-policy-pass.txt

  Scenario: Community export is blocked as truth
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_source_policy.py -q -k non_authoritative`
    Expected: Test asserts policy rejection or downgrade.
    Evidence: .sisyphus/evidence/task-3-trust-policy-fail.txt
  ```

  **Commit**: YES | Message: `feat(source-policy): add authoritative source hierarchy` | Files: `poe_trade/source_policy.py`, `tests/unit/test_source_policy.py`

- [ ] 4. API policy module

  **What to do**: Gate API client creation behind allowed scopes, enforce identifiable User-Agent configuration, and block undocumented endpoint use unless a policy exception exists.
  **Must NOT do**: Do not add endpoint-specific business logic here; keep this as a policy boundary.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: policy enforcement across clients.
  - Skills: `[]` - Reason: repo patterns already cover rate/policy style.
  - Omitted: `quick` - Reason: cross-client guardrails are not trivial.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/ingestion/AGENTS.md` - scope, retry-after, and policy guidance.
  - Pattern: `poe_trade/config/constants.py` - user-agent and scope defaults.
  - Pattern: `poe_trade/config/settings.py` - environment-driven policy knobs.

  **Acceptance Criteria**:
  - [ ] Allowed scopes are explicitly enumerated and tested.
  - [ ] Missing User-Agent is a hard failure.
  - [ ] Undocumented endpoints are blocked by default.
  - [ ] The policy boundary is testable without live network calls.

  **QA Scenarios**:
  ```
  Scenario: Allowed scope passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_policy.py -q`
    Expected: Client creation succeeds with allowed scopes.
    Evidence: .sisyphus/evidence/task-4-api-policy-pass.txt

  Scenario: Undocumented endpoint fails
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_policy.py -q -k undocumented`
    Expected: Explicit policy failure is asserted.
    Evidence: .sisyphus/evidence/task-4-api-policy-fail.txt
  ```

  **Commit**: YES | Message: `feat(api-policy): gate API clients by scope` | Files: `poe_trade/api_policy.py`, `tests/unit/test_api_policy.py`

- [ ] 5. Dynamic rate-limit contract

  **What to do**: Standardize rate-limit parsing/backoff behavior for all API-facing clients using the existing shared contract style. Preserve `Retry-After` semantics, queueing, and cancellation behavior.
  **Must NOT do**: Do not hardcode per-endpoint sleeps or bypass shared headers.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: extend the existing contract with focused coverage.
  - Skills: `[]` - Reason: no special tooling needed.
  - Omitted: `deep` - Reason: the core pattern already exists in-repo.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6 | Blocked By: 4

  **References**:
  - Pattern: `poe_trade/ingestion/rate_limit.py` - shared limiter and parser contract.
  - Pattern: `tests/unit/test_rate_limit.py` - header fixtures and negative-path behavior.
  - Pattern: `poe_trade/ingestion/AGENTS.md` - retry/backoff guidance.

  **Acceptance Criteria**:
  - [ ] `Retry-After` and rate-limit headers are parsed deterministically.
  - [ ] Backoff behavior is covered by tests.
  - [ ] Cancellation/retry behavior is deterministic under fixture inputs.
  - [ ] The contract is reusable by future clients.

  **QA Scenarios**:
  ```
  Scenario: Retry-after parsing works
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_rate_limit.py -q`
    Expected: Parsing/backoff assertions pass.
    Evidence: .sisyphus/evidence/task-5-rate-limit-pass.txt

  Scenario: Invalid headers are rejected
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_rate_limit.py -q -k invalid`
    Expected: Test covers fallback/rejection behavior.
    Evidence: .sisyphus/evidence/task-5-rate-limit-fail.txt
  ```

  **Commit**: YES | Message: `feat(rate-limits): standardize backoff parsing` | Files: `poe_trade/ingestion/rate_limit.py`, `tests/unit/test_rate_limit.py`

- [ ] 6. Third-party data policy registry

  **What to do**: Add a replaceable-source registry for third-party economy/community datasets with terms URL, allowed usage, cache TTL, attribution requirements, confidence, and kill-switch metadata.
  **Must NOT do**: Do not promote third-party data to calculation truth or embed site-specific scrapers.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: policy metadata and compliance guardrails.
  - Skills: `[]` - Reason: existing config/registry patterns suffice.
  - Omitted: `quick` - Reason: this touches policy, caching, and build output.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 8 | Blocked By: 4, 5

  **References**:
  - Pattern: `poe_trade/config/constants.py` - policy/config defaults.
  - Pattern: `poe_trade/ingestion/rate_limit.py` - shared limits and pacing.
  - Pattern: `.machine/runtime/schemas/proof_audit.schema.json` - gap/audit classification.

  **Acceptance Criteria**:
  - [ ] Registry records include terms, usage limits, TTL, attribution, and kill-switch fields.
  - [ ] Replaceable sources are clearly marked non-authoritative.
  - [ ] Build results can surface attribution text.
  - [ ] Source-specific kill-switch behavior is test-covered.

  **QA Scenarios**:
  ```
  Scenario: Replaceable source is accepted with metadata
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_third_party_policy.py -q`
    Expected: Registry accepts allowed metadata and marks source replaceable.
    Evidence: .sisyphus/evidence/task-6-third-party-policy-pass.txt

  Scenario: Missing terms URL is rejected
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_third_party_policy.py -q -k terms`
    Expected: Validation error is asserted.
    Evidence: .sisyphus/evidence/task-6-third-party-policy-fail.txt
  ```

  **Commit**: YES | Message: `feat(third-party-policy): add replaceable source registry` | Files: `poe_trade/third_party_policy.py`, `tests/unit/test_third_party_policy.py`

- [ ] 7. Version drift detector

  **What to do**: Define the drift-event contract and gate status for game patch, PoB release, RePoE export, and API reference changes; emit `PatchDriftEvent` records and mark unresolved drift as blocked for downstream consumers.
  **Must NOT do**: Do not auto-accept drift or silently update source baselines.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: drift policy spans multiple source authorities.
  - Skills: `[]` - Reason: the repo already has drift/gate patterns.
  - Omitted: `quick` - Reason: multiple source types and blocking behavior.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8 | Blocked By: 1, 2, 3, 6

  **References**:
  - Pattern: `scripts/evaluate_cutover_gate.py` - structured drift gate.
  - Pattern: `scripts/final_release_gate.py` - multi-input release recommendation.
  - Pattern: `poe_trade/ml/v3/eval.py` - parity/release rejection pattern.
  - Pattern: `tests/test_price_check_comparables.py` - deterministic contract checks.

  **Acceptance Criteria**:
  - [ ] Each of the four drift types yields a distinct event contract.
  - [ ] Unresolved drift is marked blocked for downstream evaluation.
  - [ ] Event payload includes source version, affected mechanics, and status.
  - [ ] Drift events are reproducible under fixture inputs.

  **QA Scenarios**:
  ```
  Scenario: New PoB release emits drift event
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_patch_drift.py -q`
    Expected: Event is emitted and flagged pending review.
    Evidence: .sisyphus/evidence/task-7-drift-pass.txt

  Scenario: Unresolved drift blocks output
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_patch_drift.py -q -k unresolved`
    Expected: Blocked status is asserted.
    Evidence: .sisyphus/evidence/task-7-drift-fail.txt
  ```

  **Commit**: YES | Message: `feat(drift): block outputs on unresolved source changes` | Files: `poe_trade/patch_drift.py`, `tests/unit/test_patch_drift.py`

- [ ] 8. Patch review queue

  **What to do**: Define the drift-review queue contract for drifted sources with states `pending`, `testing`, `accepted`, and `quarantined`, plus changed-source diffs and affected-mechanics summaries.
  **Must NOT do**: Do not bypass the queue by auto-promoting new releases.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: queue state machine and release gating.
  - Skills: `[]` - Reason: standard contracts and tests are enough.
  - Omitted: `quick` - Reason: stateful promotion logic is not trivial.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: none | Blocked By: 7

  **References**:
  - Pattern: `poe_trade/db/migrations.py` - applied/pending style status model.
  - Pattern: `scripts/final_release_gate.py` - status aggregation.
  - Pattern: `.machine/runtime/schemas/review_gate.schema.json` - review output contract.

  **Acceptance Criteria**:
  - [ ] A new PoB release creates a regression-run job.
  - [ ] Queue states are explicit and serializable.
  - [ ] Changed-source diffs are stored with affected mechanics.
  - [ ] API visibility reflects queue status.

  **QA Scenarios**:
  ```
  Scenario: New release enters testing state
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_patch_review_queue.py -q`
    Expected: State transitions from pending to testing are asserted.
    Evidence: .sisyphus/evidence/task-8-review-queue-pass.txt

  Scenario: Quarantine blocks promotion
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_patch_review_queue.py -q -k quarantine`
    Expected: Quarantined state prevents acceptance.
    Evidence: .sisyphus/evidence/task-8-review-queue-fail.txt
  ```

  **Commit**: YES | Message: `feat(drift-queue): add source review states` | Files: `poe_trade/patch_review_queue.py`, `tests/unit/test_patch_review_queue.py`

- [ ] 9. Agent task template

  **What to do**: Create a reusable task template that includes story ID, allowed/forbidden files, required tests, fixtures, acceptance criteria, and rollback plan; provide sample parser and optimizer stories as examples.
  **Must NOT do**: Do not leave branching or verification decisions implicit.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this is a process artifact with repo-wide impact.
  - Skills: `[]` - Reason: no extra toolchain needed.
  - Omitted: `quick` - Reason: template quality must be deliberate.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 10 | Blocked By: none

  **References**:
  - Pattern: `.machine/runtime/schemas/question_gate.schema.json` - structured question prompts.
  - Pattern: `.machine/runtime/schemas/acceptance_gate.schema.json` - explicit per-requirement evidence.
  - Pattern: `.sisyphus/plans/stash-endpoint-harmonization.md` - best existing plan structure.

  **Acceptance Criteria**:
  - [ ] Template includes story ID, files allowed, files forbidden, required tests, fixtures, acceptance criteria, rollback plan.
  - [ ] At least two sample tasks are included.
  - [ ] The template can be validated mechanically.
  - [ ] Human approval review checklist is present.

  **QA Scenarios**:
  ```
  Scenario: Parser sample task is renderable
    Tool: Bash
    Steps: Run the template validation test suite.
    Expected: Template parses and renders without missing fields.
    Evidence: .sisyphus/evidence/task-9-template-pass.txt

  Scenario: Missing required section fails validation
    Tool: Bash
    Steps: Run the template validator against a stripped sample.
    Expected: Validation error names the missing section.
    Evidence: .sisyphus/evidence/task-9-template-fail.txt
  ```

  **Commit**: YES | Message: `docs(agent): add explicit task template` | Files: `.sisyphus/templates/agent-task.md`, `tests/unit/test_agent_task_template.py`

- [ ] 10. Branch and PR conventions

  **What to do**: Define branch naming by story ID, PR title/description format, required test evidence in PR bodies, and a CI check that validates story IDs and evidence references.
  **Must NOT do**: Do not allow story work to land without test evidence.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: repository workflow conventions affect all later work.
  - Skills: `[]` - Reason: no special coding skill required.
  - Omitted: `quick` - Reason: workflow rules need clear enforcement.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: none | Blocked By: 9

  **References**:
  - Pattern: `.github/workflows/python-ci.yml` - CI gate location.
  - Pattern: `scripts/final_release_gate.py` - release gating convention.
  - Pattern: `.sisyphus/evidence/task-3-ops-refactor.md` - compact evidence note style.

  **Acceptance Criteria**:
  - [ ] Branch naming format is documented and validated.
  - [ ] PR title/description format includes story ID and evidence.
  - [ ] CI rejects malformed story IDs.
  - [ ] Evidence reference is required in PR body.

  **QA Scenarios**:
  ```
  Scenario: Valid story ID passes
    Tool: Bash
    Steps: Run branch/PR convention tests.
    Expected: Story ID format is accepted and evidence is located.
    Evidence: .sisyphus/evidence/task-10-pr-conventions-pass.txt

  Scenario: Invalid story ID fails CI check
    Tool: Bash
    Steps: Run the validator against an invalid PR template.
    Expected: CI-style validation failure.
    Evidence: .sisyphus/evidence/task-10-pr-conventions-fail.txt
  ```

  **Commit**: YES | Message: `docs(ci): standardize branch and pr conventions` | Files: `docs/branch-pr-conventions.md`, `tests/unit/test_branch_pr_conventions.py`

- [ ] 11. Test harness skeleton

  **What to do**: Add the Phase 0 test-harness structure and fixture naming rules for `unit`, `contract`, `integration`, `golden`, `property`, `performance`, and `e2e`, plus a fixture validator that rejects missing metadata.
  **Must NOT do**: Do not introduce live-service tests or shared mutable fixtures.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: test layout and fixture discipline are foundational.
  - Skills: `[]` - Reason: repo conventions already define pytest style.
  - Omitted: `quick` - Reason: this spans multiple test surfaces.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 12 | Blocked By: none

  **References**:
  - Pattern: `tests/AGENTS.md` - deterministic, local-fixture, no-live-service guidance.
  - Pattern: `tests/unit/test_verify_ml_deterministic_pack.py` - fixture validation style.
  - Pattern: `tests/unit/test_docker_dev_stack.py` - broader integration-test pattern.

  **Acceptance Criteria**:
  - [ ] Test directory conventions are created and documented.
  - [ ] Fixture naming includes game version, source version, scenario, and expected metrics.
  - [ ] Missing fixture metadata fails fast.
  - [ ] Validator is covered by unit tests.

  **QA Scenarios**:
  ```
  Scenario: Valid fixture metadata passes
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_fixture_validator.py -q`
    Expected: Validator accepts complete metadata.
    Evidence: .sisyphus/evidence/task-11-fixture-validator-pass.txt

  Scenario: Missing metadata fails
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_fixture_validator.py -q -k missing_metadata`
    Expected: Fast failure identifies the missing field.
    Evidence: .sisyphus/evidence/task-11-fixture-validator-fail.txt
  ```

  **Commit**: YES | Message: `test(harness): add fixture conventions and validator` | Files: `tests/contract/.gitkeep`, `tests/integration/.gitkeep`, `tests/golden/.gitkeep`, `tests/property/.gitkeep`, `tests/performance/.gitkeep`, `tests/e2e/.gitkeep`, `tests/unit/test_fixture_validator.py`

- [ ] 12. Deterministic seed utilities

  **What to do**: Propagate deterministic seeds through request, optimizer, and result objects; add a reproducibility hash and persist seed/source versions in output artifacts.
  **Must NOT do**: Do not derive seeds implicitly from wall-clock time.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: this is a focused deterministic-harness extension.
  - Skills: `[]` - Reason: existing QA contract patterns are enough.
  - Omitted: `deep` - Reason: the domain pattern is already established.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: none | Blocked By: 11

  **References**:
  - Pattern: `poe_trade/qa_contract.py` - seed constants and reproducible QA state.
  - Pattern: `poe_trade/evidence/summary.md` - evidence and parity artifact guidance.
  - Pattern: `scripts/verify_ml_deterministic_pack.py` - deterministic artifact pack checking.
  - Pattern: `tests/unit/test_verify_ml_deterministic_pack.py` - exact seed/evidence tests.

  **Acceptance Criteria**:
  - [ ] Same seed produces the same reproducibility hash.
  - [ ] Seed and source versions are persisted in result output.
  - [ ] Randomness flows through request -> optimizer -> result.
  - [ ] Determinism is verified in unit tests.

  **QA Scenarios**:
  ```
  Scenario: Seeded output is reproducible
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_seed_contract.py -q`
    Expected: Identical seed yields identical hash/output.
    Evidence: .sisyphus/evidence/task-12-seed-pass.txt

  Scenario: Unseeded path is rejected or explicitly marked
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_seed_contract.py -q -k unseeded`
    Expected: Test asserts the failure or explicit non-determinism flag.
    Evidence: .sisyphus/evidence/task-12-seed-fail.txt
  ```

  **Commit**: YES | Message: `feat(qa): propagate deterministic seeds` | Files: `poe_trade/qa_contract.py`, `tests/unit/test_seed_contract.py`

- [ ] 13. OptimizationRequest schema

  **What to do**: Define the canonical optimization request with class, ascendancy, league, level, bandit, pantheon, budget, weight slider, objective weights, locked items/gems/tree regions, and owned-items mode.
  **Must NOT do**: Do not collapse cost, budget, and configuration into one ambiguous field.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: canonical request shape drives all later execution.
  - Skills: `[]` - Reason: existing contract patterns are enough.
  - Omitted: `quick` - Reason: multi-field contract design needs thorough validation.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 14 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/ml/contract.py` - frozen contract metadata style.
  - Pattern: `tests/unit/test_ml_v3_sql_contract.py` - schema freezing and field-order discipline.
  - Pattern: `poe_trade/config/settings.py` - budget/config input style.

  **Acceptance Criteria**:
  - [ ] Required fields include class, ascendancy, league, level, and budget.
  - [ ] Budget supports chaos, divine, and native currency inputs with conversion metadata.
  - [ ] Tanky-to-Glass-Cannon slider and objective weights are explicit.
  - [ ] Locked items, locked gems, and edit limits are represented.

  **QA Scenarios**:
  ```
  Scenario: Valid request passes schema validation
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_optimization_request.py -q`
    Expected: Canonical request serializes and validates.
    Evidence: .sisyphus/evidence/task-13-request-pass.txt

  Scenario: Missing class fails validation
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_optimization_request.py -q -k missing_class`
    Expected: Machine-readable validation error is asserted.
    Evidence: .sisyphus/evidence/task-13-request-fail.txt
  ```

  **Commit**: YES | Message: `feat(request): define canonical optimization request` | Files: `poe_trade/optimization/request.py`, `tests/unit/test_optimization_request.py`

- [ ] 14. Hard-constraint validation

  **What to do**: Validate class/ascendancy compatibility, negative budget, impossible edit limits, unsupported league, and unsupported game version before any later scoring or evaluation.
  **Must NOT do**: Do not degrade hard failures into warnings.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: validation rules must be exact and exhaustive.
  - Skills: `[]` - Reason: contract checks are standard.
  - Omitted: `quick` - Reason: multiple invalid states require careful coverage.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: none | Blocked By: 13

  **References**:
  - Pattern: `poe_trade/qa_contract.py` - structured failure summaries.
  - Pattern: `poe_trade/ml/contract.py` - canonical contract validation style.
  - Pattern: `tests/unit/test_settings_aliases.py` - explicit validation and aliasing checks.

  **Acceptance Criteria**:
  - [ ] Invalid class/ascendancy combinations are rejected.
  - [ ] Negative budgets and impossible edit limits are rejected.
  - [ ] Unsupported league or game version returns machine-readable errors.
  - [ ] Validation is isolated from scoring.

  **QA Scenarios**:
  ```
  Scenario: Invalid ascendancy fails
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_optimization_validation.py -q`
    Expected: Validation error names the incompatible ascendancy.
    Evidence: .sisyphus/evidence/task-14-validation-pass.txt

  Scenario: Negative budget is rejected
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_optimization_validation.py -q -k negative_budget`
    Expected: Rejection is explicit and machine-readable.
    Evidence: .sisyphus/evidence/task-14-validation-fail.txt
  ```

  **Commit**: YES | Message: `feat(validation): enforce hard optimization constraints` | Files: `poe_trade/optimization/validation.py`, `tests/unit/test_optimization_validation.py`

- [ ] 15. MetricVector schema

  **What to do**: Define the canonical metric vector with DPS, EHP, max-hit, recovery, avoidance, ailment mitigation, cost, and confidence dimensions; support null/unsupported metrics and per-metric confidence metadata.
  **Must NOT do**: Do not compress the vector into a single score or hide unsupported metrics.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: the comparison surface for all later optimization depends on this contract.
  - Skills: `[]` - Reason: existing contract patterns are sufficient.
  - Omitted: `quick` - Reason: metric semantics need explicit coverage.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 16 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/ml/contract.py` - frozen metrics/benchmark contract style.
  - Pattern: `tests/unit/test_ml_v3_sql_contract.py` - metric field freezing.
  - Pattern: `scripts/evaluate_cutover_gate.py` - metric comparison and evidence structure.
  - Pattern: `scripts/final_release_gate.py` - release recommendation over metric checks.

  **Acceptance Criteria**:
  - [ ] Metric vector includes hit DPS, average DPS, full DPS, DoT DPS, EHP, max-hit by damage type, recovery, avoidance, mitigation, cost, and confidence.
  - [ ] Unsupported metric values are represented explicitly.
  - [ ] Currency conversion uses divine-equivalent metadata.
  - [ ] Metric confidence is tracked per dimension.

  **QA Scenarios**:
  ```
  Scenario: Complete metric vector validates
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_metric_vector.py -q`
    Expected: All required dimensions serialize and compare deterministically.
    Evidence: .sisyphus/evidence/task-15-metric-vector-pass.txt

  Scenario: Missing dimension is rejected
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_metric_vector.py -q -k missing_dimension`
    Expected: Validation error is explicit.
    Evidence: .sisyphus/evidence/task-15-metric-vector-fail.txt
  ```

  **Commit**: YES | Message: `feat(metrics): define canonical metric vector` | Files: `poe_trade/optimization/metrics.py`, `tests/unit/test_metric_vector.py`

- [ ] 16. Default configuration presets

  **What to do**: Define the `BuildConfiguration` contract with enemy profile, boss preset, charges, flasks, buffs, ailment assumptions, skill selection, map modifiers, uptime assumptions, and custom toggles; add the `Guardian/Pinnacle`, `Mapping`, `Uber`, and `Custom` presets with user overrides.
  **Must NOT do**: Do not leave the default assumptions implicit or hidden in evaluator code.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: configuration semantics affect all downstream scoring.
  - Skills: `[]` - Reason: contract-based config modeling is standard.
  - Omitted: `quick` - Reason: multiple presets and overrides need careful validation.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: none | Blocked By: 15

  **References**:
  - Pattern: `poe_trade/qa_contract.py` - canonical seed/config state shape.
  - Pattern: `poe_trade/ml/v3/eval.py` - configuration-sensitive evaluation behavior.
  - Pattern: `poe_trade/config/settings.py` - explicit user-facing defaults.

  **Acceptance Criteria**:
  - [ ] All four presets exist and are test-covered.
  - [ ] Enemy resistances, ailment assumptions, flask uptime, charges, and toggles are encoded.
  - [ ] User overrides are allowed and persisted.
  - [ ] Every PoB-oracle-bound request carries explicit configuration.

  **QA Scenarios**:
  ```
  Scenario: Guardian/Pinnacle preset loads
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_build_configuration.py -q`
    Expected: Preset serializes with expected defaults.
    Evidence: .sisyphus/evidence/task-16-config-pass.txt

  Scenario: Override changes a preset field
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_build_configuration.py -q -k override`
    Expected: Override wins over preset default.
    Evidence: .sisyphus/evidence/task-16-config-fail.txt
  ```

  **Commit**: YES | Message: `feat(config): add canonical build presets` | Files: `poe_trade/optimization/configuration.py`, `tests/unit/test_build_configuration.py`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> Do NOT auto-proceed after verification. Wait for the user's explicit approval before marking work complete.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ Playwright if UI is touched later)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit once per story, not per subtask.
- Keep contract changes isolated from policy/test-harness changes when practical.
- Never bundle Phase 0 work with Phase 1+ implementation.
- Use concise Conventional Commit messages tied to the story scope.

## Success Criteria
- Phase 0 artifacts exist and are test-covered.
- Source authority, policy, and drift decisions are explicit and machine-checkable.
- The plan remains strictly Phase 0; later phases stay out of scope.
- Every task has a named evidence artifact and at least one failure-path QA scenario.
