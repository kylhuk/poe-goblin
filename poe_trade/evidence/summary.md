# Package Evidence Summary

## Parity workflow

- Package-local QA seeding uses `poe_trade.qa_contract` to seed gold marts and execute real scanner/backtest runs before writing `poe_trade/evidence/qa/seed.json` and `poe_trade/evidence/qa/seed-journal.json`.
- Each seed captures a paired non-journal parity artifact (scanner run ID + backtest run ID + sorted key arrays + count comparison) for the enabled strategy path.
- Each seed also captures a journal-gated backtest artifact with explicit status/summary evidence that shows the policy gate outcome.
- Each seed writes CLI proof artifacts for `poe_trade.cli scan plan` and `poe_trade.cli research backtest` under `poe_trade/evidence/qa/cli/`.
- State paths refer to `poe_trade/evidence/qa/state/auth-session.json` and `poe_trade/evidence/qa/state/faults.json`, keeping the CLI runs under a connected operator session with no active faults.
- The generated summary records actual scanner recommendations, alerts, backtest summaries, ML audits, and stash data so parity proof is non-placeholder.

## Seeded fixtures

- `poe_trade/evidence/qa/seed-journal.json` seeds league `Mirage` / realm `pc` at `2026-03-15T15:23:32.339127Z`; 1 scanner recommendations, 2 scanner alerts, 1 ML train runs, 1 ML promotion audits, 3 stash items, 2 stash tabs.
  - `enabled_non_journal` strategy coverage:
      - Canonical candidate: `poe_trade/sql/strategy/bulk_essence/candidate.sql`
      - Discover bridge: `poe_trade/sql/strategy/bulk_essence/discover.sql`
      - Strategy: `bulk_essence` (enabled=True, requires_journal=False)
      - Metadata: `strategies/bulk_essence/strategy.toml`
  - `journal_gated` strategy coverage:
      - Canonical candidate: `poe_trade/sql/strategy/high_dim_jewels/candidate.sql`
      - Discover bridge: `poe_trade/sql/strategy/high_dim_jewels/discover.sql`
      - Strategy: `high_dim_jewels` (enabled=False, requires_journal=True)
      - Metadata: `strategies/high_dim_jewels/strategy.toml`
  - Non-journal parity pair: strategy `bulk_essence`, scanner `aeb045461cfe4bdeb43f1ba8f338a84e`, backtest `f261cf2ca9fe4f05b53219457e3ba83c`.
    - Scanner keys: `essence:bulk`.
    - Backtest keys: `essence:bulk`.
    - Count check: scanner=1, backtest=1, delta=0, keys_match=True.
  - Journal-gated backtest: strategy `high_dim_jewels`, run `b660fe7b45e14a3cb72217067931c4ff`, status `no_opportunities`, opportunities=0.
    - Summary: source data exists but all candidates require journal state
  - CLI proof `research_backtest`: command `/home/hal9000/docker/poe_trade/.venv/bin/python -m poe_trade.cli research backtest --strategy high_dim_jewels --league Mirage --days 14`, exit_code=0, artifact `poe_trade/evidence/qa/cli/seed-journal-research-backtest.txt`.
  - CLI proof `scan_plan`: command `/home/hal9000/docker/poe_trade/.venv/bin/python -m poe_trade.cli scan plan --league Mirage --limit 5`, exit_code=0, artifact `poe_trade/evidence/qa/cli/seed-journal-scan-plan.txt`.
  - State fixtures referenced: `poe_trade/evidence/qa/state/auth-session.json`, `poe_trade/evidence/qa/state/faults.json`.

- `poe_trade/evidence/qa/seed.json` seeds league `Mirage` / realm `pc` at `2026-03-15T15:23:27.836856Z`; 1 scanner recommendations, 2 scanner alerts, 1 ML train runs, 1 ML promotion audits, 3 stash items, 2 stash tabs.
  - `enabled_non_journal` strategy coverage:
      - Canonical candidate: `poe_trade/sql/strategy/bulk_essence/candidate.sql`
      - Discover bridge: `poe_trade/sql/strategy/bulk_essence/discover.sql`
      - Strategy: `bulk_essence` (enabled=True, requires_journal=False)
      - Metadata: `strategies/bulk_essence/strategy.toml`
  - `journal_gated` strategy coverage:
      - Canonical candidate: `poe_trade/sql/strategy/high_dim_jewels/candidate.sql`
      - Discover bridge: `poe_trade/sql/strategy/high_dim_jewels/discover.sql`
      - Strategy: `high_dim_jewels` (enabled=False, requires_journal=True)
      - Metadata: `strategies/high_dim_jewels/strategy.toml`
  - Non-journal parity pair: strategy `bulk_essence`, scanner `2447d088560744209f67db8bcc615f6f`, backtest `bbf23461b38f47568df9e22e84031e44`.
    - Scanner keys: `essence:bulk`.
    - Backtest keys: `essence:bulk`.
    - Count check: scanner=1, backtest=1, delta=0, keys_match=True.
  - Journal-gated backtest: strategy `high_dim_jewels`, run `fbbd47e2637645489c9d8977ff724052`, status `no_opportunities`, opportunities=0.
    - Summary: source data exists but all candidates require journal state
  - CLI proof `research_backtest`: command `/home/hal9000/docker/poe_trade/.venv/bin/python -m poe_trade.cli research backtest --strategy bulk_essence --league Mirage --days 14`, exit_code=0, artifact `poe_trade/evidence/qa/cli/seed-research-backtest.txt`.
  - CLI proof `scan_plan`: command `/home/hal9000/docker/poe_trade/.venv/bin/python -m poe_trade.cli scan plan --league Mirage --limit 20`, exit_code=0, artifact `poe_trade/evidence/qa/cli/seed-scan-plan.txt`.
  - State fixtures referenced: `poe_trade/evidence/qa/state/auth-session.json`, `poe_trade/evidence/qa/state/faults.json`.

## Status context

- `poe_trade/evidence/qa/state/auth-session.json` seeds session `qa-session-mirage` for account `qa-exile` with status `connected` and scopes account:profile, account:stashes.
- `poe_trade/evidence/qa/state/faults.json` records service fault toggles (clean baseline): `api_unavailable`=false, `scanner_degraded`=false, `service_action_failure`=false, `stash_empty`=false.

## Evidence inventory

- `poe_trade/evidence/qa/seed.json`: canonical non-journal parity fixture that drives scanner + backtest runs while referencing the enabled bulk_essence contract.
- `poe_trade/evidence/qa/seed-journal.json`: journal-gated fixture that covers high_dim_jewels policy outcomes with the same canonical candidate contract.
- `poe_trade/evidence/qa/cli/seed-scan-plan.txt`: captured stdout/stderr proving `poe_trade.cli scan plan --league Mirage --limit 20` ran through the package CLI path during seed.json generation.
- `poe_trade/evidence/qa/cli/seed-research-backtest.txt`: captured stdout/stderr proving `poe_trade.cli research backtest --strategy bulk_essence --league Mirage --days 14` ran through the package CLI path during seed.json generation.
- `poe_trade/evidence/qa/cli/seed-journal-scan-plan.txt`: captured stdout/stderr proving `poe_trade.cli scan plan --league Mirage --limit 5` ran through the package CLI path during seed-journal generation.
- `poe_trade/evidence/qa/cli/seed-journal-research-backtest.txt`: captured stdout/stderr proving `poe_trade.cli research backtest --strategy high_dim_jewels --league Mirage --days 14` ran through the package CLI path during seed-journal generation.
- `poe_trade/evidence/qa/state/auth-session.json`: seeded authenticated operator session (`status=connected`) required by CLI flows.
- `poe_trade/evidence/qa/state/faults.json`: fault toggle table ensuring scanner services see no degradation during parity runs.

## Artifact list

- `poe_trade/evidence/qa/cli/seed-journal-research-backtest.txt`
- `poe_trade/evidence/qa/cli/seed-journal-scan-plan.txt`
- `poe_trade/evidence/qa/cli/seed-research-backtest.txt`
- `poe_trade/evidence/qa/cli/seed-scan-plan.txt`
- `poe_trade/evidence/qa/seed-journal.json`
- `poe_trade/evidence/qa/seed.json`
- `poe_trade/evidence/qa/state/auth-session.json`
- `poe_trade/evidence/qa/state/faults.json`
