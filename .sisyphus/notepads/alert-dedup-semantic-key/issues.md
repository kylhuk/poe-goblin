# Issues
- `tests/unit/test_strategy_{registry,scanner}.py` now assert `semantic_key`/`AS SEMANTIC_KEY`, so the targeted pytest run fails everywhere until the shared SQL assets emit that column/alias.
- Candidate/backtest identity drift is already present in seven item-based packs, so Tasks 2 and 3 must update both SQL surfaces together or backtest parity will remain broken.
- Targeted pytest still fails outside this task scope because `cx_market_making` candidate/backtest SQL does not emit `semantic_key` yet (`tests/unit/test_strategy_registry.py::test_all_backtest_sql_files_use_shared_contract_columns` and `tests/unit/test_strategy_registry.py::test_candidate_sql_files_use_explicit_scanner_columns`).
- `lsp_diagnostics` cannot validate changed `.sql` files in this environment because no SQL LSP server is configured.
- Re-running the command still fails with "No LSP server configured for extension: .sql", so these diagnostics remain blocked until someone defines a SQL-capable LSP server.
- No new task-local blocker surfaced, but this task only verified `tests/unit/test_strategy_policy.py`; broader scanner/backtest semantic-key parity remains deferred to later tasks.
- Task instructions conflict: the task requires appending notepad entries while also listing `poe_trade/strategy/scanner.py` and `tests/unit/test_strategy_scanner.py` as the only modified files.
- Running `lsp_diagnostics` on `tests/unit/test_strategy_backtest.py` still emits the long-standing warnings about unannotated helpers; closing those would be out of scope for this semantic-key regression work.
- Recent `lsp_diagnostics` on the modified modules now surface the same longstanding `Any`/string-concat noise in `poe_trade/strategy/backtest.py` plus the private helper usage warning in `tests/unit/test_strategy_scanner.py`; no new issues were introduced.
