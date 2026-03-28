# REPOSITORY GUIDE

## PURPOSE

This file gives agentic coding tools the repo-wide defaults for `poe_trade`.
Deeper `AGENTS.md` files override this one for files under their directory.

## LOCAL GUIDES

- `poe_trade/AGENTS.md` covers package code.
- `poe_trade/ingestion/AGENTS.md` covers fetch, checkpoint, and rate-limit logic.
- `schema/AGENTS.md` covers ClickHouse DDL and sanity SQL.
- `schema/migrations/AGENTS.md` covers ordered migration files.
- `tests/AGENTS.md` covers test layout and focused verification.

## RULE FILE AUDIT

- No `.cursor/rules/` directory was present in this repository snapshot.
- No `.cursorrules` file was present in this repository snapshot.
- No `.github/copilot-instructions.md` file was present in this repository snapshot.

## REPO SHAPE

- Python package: `poe_trade/`
- Tests: `tests/`
- Schema: `schema/`
- Strategy SQL assets: `poe_trade/sql/`
- Utility scripts: `scripts/`
- Docker / compose orchestration: repo root `Makefile` and compose files

## BUILD / TEST COMMANDS

- Build app services: `make build`
- Rebuild and start dev stack: `make rebuild`
- Start dev stack: `make up`
- Stop dev stack: `make down`
- Full unit tests: `.venv/bin/pytest tests/unit`
- Whole test tree: `.venv/bin/pytest tests`
- API contract subset: `make ci-api-contract`
- CLI smoke checks: `make ci-smoke-cli`
- Deterministic CI bundle: `make ci-deterministic`
- Product QA bundle: `make qa-verify-product`

## SINGLE-TEST RUNS

- Single file: `.venv/bin/pytest tests/unit/test_settings_aliases.py`
- Single test function: `.venv/bin/pytest tests/unit/test_settings_aliases.py::SettingsAliasesTests::test_cursor_dir_alias`
- Pytest node style works everywhere else too, for example:
  - `.venv/bin/pytest tests/unit/test_api_ops_routes.py::test_ops_contract_shape`
  - `.venv/bin/pytest tests/unit/test_market_harvester.py::test_success_flow_writes_rows_and_advances_checkpoint`
- Use `-k` for fast filtering when the exact node is awkward:
  - `.venv/bin/pytest tests/unit/test_api_ops_routes.py -k scanner_recommendations`

## LINT / FORMAT

- No dedicated lint target is defined in `Makefile`.
- No repo-local `ruff`, `black`, `mypy`, or `pyright` config file was found.
- Keep edits aligned with nearby code instead of reformatting unrelated files.
- If you need a quick sanity pass, prefer focused tests and the existing smoke commands.

## PYTHON STYLE

- Target Python 3.11+ and keep `from __future__ import annotations` in new modules.
- Prefer explicit type hints on public functions, classes, and dataclass fields.
- Use standard library `collections.abc` types for parameters and return types when practical.
- Keep modules small and focused; route orchestration through service wrappers.
- Use snake_case for functions, variables, and modules.
- Use PascalCase for classes and UPPER_SNAKE_CASE for constants.
- Prefer short, descriptive helper names over large monolithic functions.

## IMPORTS

- Group imports as stdlib, third-party, then local.
- Keep local imports near the bottom when they prevent cycles or heavy startup cost.
- Prefer direct imports for commonly used symbols over repeated module qualification.
- Do not add wildcard imports.
- If a file already uses a local import pattern for cycle avoidance, follow that pattern.

## FORMATTING

- Match the existing file’s wrapping style; do not force a repo-wide reflow.
- Keep blank lines between logical sections.
- Favor readable line breaks around long argument lists and SQL strings.
- Preserve compact JSON serialization where the code already uses it.
- Avoid introducing trailing whitespace or unnecessary blank lines.

## TYPES / DATA SHAPES

- Prefer concrete dataclasses for stable data contracts.
- Use `dict[str, object]` or `Mapping[str, object]` only when the shape is intentionally loose.
- Keep API payload keys stable; many tests assert exact JSON field names.
- When a function can return `None`, annotate it explicitly.
- Prefer `tuple[...]` for immutable collections exposed from settings.

## NAMING CONVENTIONS

- Settings fields mirror environment names conceptually; preserve those names.
- Keep CLI-facing identifiers stable, especially service names and console-script names.
- Use descriptive test names that read like behavior statements.
- Use `_private` helper names for module-local implementation details.
- Use one file / one concern where possible, especially for SQL migrations.

## ERROR HANDLING

- Raise `ValueError` for invalid caller input unless a domain-specific error already exists.
- Raise custom runtime errors for backend / transport failures.
- Convert low-level exceptions into repo-specific errors at module boundaries.
- Use `from None` when translating errors to avoid leaking noisy internals.
- Prefer explicit status codes and structured error payloads in API code.
- Do not swallow exceptions silently unless the surrounding code intentionally degrades.

## LOGGING AND OUTPUT

- Use `logging.getLogger(__name__)` in library code.
- Prefer structured `logging` calls over `print` inside package modules.
- CLI entry points may print user-facing summaries or tabular rows.
- Keep log messages short and operationally useful.
- Include context such as service id, league, or queue key when it helps debugging.

## CONFIGURATION

- Read environment through `poe_trade.config.settings.get_settings()` unless a lower-level helper owns parsing.
- Keep environment aliases backward-compatible.
- Add or change aliases only with tests, especially `tests/unit/test_settings_aliases.py`.
- Treat `Settings` as the canonical config object for runtime behavior.
- Do not move env parsing into random callers.

## CLI / SERVICE BOUNDARIES

- Keep argument parsing in `poe_trade.services.*` or `poe_trade.cli`.
- Keep business logic in the domain modules, not in thin wrappers.
- Preserve console-script names from `pyproject.toml`.
- Keep service startup policy out of the CLI router when a dedicated service module exists.
- Prefer small orchestration functions that delegate to domain helpers.

## SQL / MIGRATIONS

- Treat `schema/migrations/*.sql` as append-only history.
- Keep new migration files zero-padded and monotonically increasing.
- Use additive ClickHouse changes unless a staged compatibility plan exists.
- Do not reorder or rewrite shipped migration files.
- Keep sanity SQL read-only.
- Remember that the migration runner splits statements; avoid relying on multi-statement HTTP execution.

## TESTING PRACTICES

- Prefer `pytest` for new tests, even when neighboring files still use `unittest`.
- Keep doubles local, explicit, and deterministic.
- Avoid live ClickHouse or network calls in unit tests.
- Mirror behavior changes with negative-path assertions for auth, rate limits, config parsing, and backend failures.
- Use focused module paths when iterating on a change.
- Keep fixture setup minimal and close to the test that needs it.

## AREA-SPECIFIC REMINDERS

- `poe_trade/ingestion/`: preserve upstream payload fields, idempotency, and rate-limit handling.
- `poe_trade/db/`: keep ClickHouse wrappers small and translate transport failures cleanly.
- `poe_trade/api/`: return structured JSON errors and preserve CORS/auth behavior.
- `poe_trade/ml/`: keep training, serving, and contract code aligned with stored schemas.
- `schema/`: prefer additive storage evolution and descriptive migration names.
- `tests/`: use focused module tests for touched behavior first, then wider suites if needed.

## WHEN IN DOUBT

- Read the closest `AGENTS.md` before editing.
- Match the patterns already used in the touched module.
- Prefer the smallest change that preserves behavior.
