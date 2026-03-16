from __future__ import annotations

import json
from pathlib import Path
from typing import cast


ROOT = Path("poe_trade/evidence")
INDEX_NAME = "index.json"
SUMMARY_NAME = "summary.md"


def _load_json(path: Path) -> dict[str, object] | None:
    try:
        parsed = cast(object, json.loads(path.read_text(encoding="utf-8")))
        if isinstance(parsed, dict):
            return cast(dict[str, object], parsed)
        return None
    except (ValueError, OSError):
        return None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _format_strategy(description: dict[str, object]) -> list[str]:
    strategy_id = description.get("strategy_id", "unknown")
    enabled = description.get("enabled")
    requires_journal = description.get("requires_journal")
    candidate_sql = description.get("candidate_sql", "n/a")
    discover_sql = description.get("discover_sql", "n/a")
    strategy_toml = description.get("strategy_toml", "n/a")
    return [
        f"      - Canonical candidate: `{candidate_sql}`",
        f"      - Discover bridge: `{discover_sql}`",
        f"      - Strategy: `{strategy_id}` (enabled={enabled}, requires_journal={requires_journal})",
        f"      - Metadata: `{strategy_toml}`",
    ]


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    return {}


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    typed_items = cast(list[object], value)
    items = [str(item).strip() for item in typed_items]
    return sorted(item for item in items if item)


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    index_path = ROOT / INDEX_NAME
    summary_path = ROOT / SUMMARY_NAME
    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path not in {index_path, summary_path}
    )
    by_dir: dict[str, int] = {}
    for path in files:
        rel = path.relative_to(ROOT)
        parent = "." if rel.parent == Path(".") else str(rel.parent)
        by_dir[parent] = by_dir.get(parent, 0) + 1

    index = {
        "root": str(ROOT),
        "artifactCount": len(files),
        "artifacts": [
            {
                "path": str(path),
                "bytes": path.stat().st_size,
            }
            for path in files
        ],
        "byDirectory": dict(sorted(by_dir.items())),
    }
    _ = index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    seed_paths = sorted(ROOT.glob("qa/seed*.json"))
    seeds: list[tuple[Path, dict[str, object]]] = []
    for seed_path in seed_paths:
        data = _load_json(seed_path)
        if data is not None:
            seeds.append((seed_path, data))

    state_paths = sorted(ROOT.glob("qa/state/*.json"))
    state_entries: list[tuple[Path, dict[str, object]]] = []
    for state_path in state_paths:
        data = _load_json(state_path)
        if data is not None:
            state_entries.append((state_path, data))

    lines: list[str] = [
        "# Package Evidence Summary",
        "",
        "## Parity workflow",
        "",
        "- Package-local QA seeding uses `poe_trade.qa_contract` to seed gold marts and execute real scanner/backtest runs before writing `poe_trade/evidence/qa/seed.json` and `poe_trade/evidence/qa/seed-journal.json`.",
        "- Each seed captures a paired non-journal parity artifact (scanner run ID + backtest run ID + sorted key arrays + count comparison) for the enabled strategy path.",
        "- Each seed also captures a journal-gated backtest artifact with explicit status/summary evidence that shows the policy gate outcome.",
        "- Each seed writes CLI proof artifacts for `poe_trade.cli scan plan` and `poe_trade.cli research backtest` under `poe_trade/evidence/qa/cli/`.",
        "- State paths refer to `poe_trade/evidence/qa/state/auth-session.json` and `poe_trade/evidence/qa/state/faults.json`, keeping the CLI runs under a connected operator session with no active faults.",
        "- The generated summary records actual scanner recommendations, alerts, backtest summaries, ML audits, and stash data so parity proof is non-placeholder.",
        "",
        "## Seeded fixtures",
        "",
    ]

    summary_metrics = [
        ("scanner_recommendations", "scanner recommendations"),
        ("scanner_alerts", "scanner alerts"),
        ("ml_train_runs", "ML train runs"),
        ("ml_promotion_audits", "ML promotion audits"),
        ("stash_items", "stash items"),
        ("stash_tabs", "stash tabs"),
    ]

    if seeds:
        for seed_path, seed_data in seeds:
            league = str(seed_data.get("league") or "unknown")
            realm = str(seed_data.get("realm") or "unknown")
            seeded_at = str(seed_data.get("seeded_at") or "unknown time")
            summary_block = _as_dict(seed_data.get("summary"))
            metric_texts = [
                f"{summary_block[key]} {label}"
                for key, label in summary_metrics
                if key in summary_block
            ]
            metrics_description = (
                ", ".join(metric_texts) if metric_texts else "metrics pending"
            )
            lines.append(
                f"- `{_display_path(seed_path)}` seeds league `{league}` / realm `{realm}` at `{seeded_at}`; {metrics_description}."
            )
            parity = _as_dict(seed_data.get("parity_evidence"))
            strategy_paths = _as_dict(parity.get("strategy_paths"))
            for name, description in sorted(strategy_paths.items()):
                formatted = _format_strategy(_as_dict(description))
                lines.append(f"  - `{str(name)}` strategy coverage:")
                lines.extend(formatted)
            non_journal_pair = _as_dict(parity.get("enabled_non_journal_pair"))
            scanner_keys = _as_string_list(
                non_journal_pair.get("scanner_item_or_market_keys")
            )
            backtest_keys = _as_string_list(
                non_journal_pair.get("backtest_item_or_market_keys")
            )
            key_counts = _as_dict(non_journal_pair.get("key_count_comparison"))
            if non_journal_pair:
                lines.append(
                    "  - Non-journal parity pair: "
                    + f"strategy `{non_journal_pair.get('strategy_id', 'unknown')}`, "
                    + f"scanner `{non_journal_pair.get('scanner_run_id', 'unknown')}`, "
                    + f"backtest `{non_journal_pair.get('backtest_run_id', 'unknown')}`."
                )
                lines.append(
                    "    - Scanner keys: "
                    + (
                        ", ".join(f"`{key}`" for key in scanner_keys)
                        if scanner_keys
                        else "none"
                    )
                    + "."
                )
                lines.append(
                    "    - Backtest keys: "
                    + (
                        ", ".join(f"`{key}`" for key in backtest_keys)
                        if backtest_keys
                        else "none"
                    )
                    + "."
                )
                lines.append(
                    "    - Count check: "
                    + f"scanner={key_counts.get('scanner_recommendation_count', 'n/a')}, "
                    + f"backtest={key_counts.get('backtest_detail_count', 'n/a')}, "
                    + f"delta={key_counts.get('count_delta', 'n/a')}, "
                    + f"keys_match={key_counts.get('keys_match', 'n/a')}."
                )

            journal = _as_dict(parity.get("journal_gated_backtest"))
            if journal:
                lines.append(
                    "  - Journal-gated backtest: "
                    + f"strategy `{journal.get('strategy_id', 'unknown')}`, "
                    + f"run `{journal.get('backtest_run_id', 'unknown')}`, "
                    + f"status `{journal.get('status', 'unknown')}`, "
                    + f"opportunities={journal.get('opportunity_count', 'n/a')}."
                )
                lines.append(f"    - Summary: {journal.get('summary', 'n/a')}")

            cli_proof = _as_dict(parity.get("cli_proof_artifacts"))
            for proof_name, proof_payload in sorted(cli_proof.items()):
                proof = _as_dict(proof_payload)
                lines.append(
                    "  - CLI proof "
                    + f"`{proof_name}`: command `{proof.get('command', 'unknown')}`, "
                    + f"exit_code={proof.get('exit_code', 'n/a')}, "
                    + f"artifact `{proof.get('artifact_path', 'n/a')}`."
                )

            state_refs = _as_dict(parity.get("state_paths")).values()
            if state_refs:
                refs = ", ".join(f"`{str(ref)}`" for ref in state_refs)
                lines.append(f"  - State fixtures referenced: {refs}.")
            lines.append("")
    else:
        lines.append("- No seed artifacts detected.")
        lines.append("")

    lines.append("## Status context")
    lines.append("")
    if state_entries:
        for state_path, state_data in state_entries:
            name = state_path.stem
            if name == "auth-session":
                account_name = state_data.get("account_name", "unknown")
                status = state_data.get("status", "unknown")
                session = state_data.get("session_id", "unknown")
                scopes = _as_string_list(state_data.get("scope"))
                scope_text = ", ".join(scopes) if scopes else "no scopes"
                lines.append(
                    f"- `{_display_path(state_path)}` seeds session `{session}` for account `{account_name}` with status `{status}` and scopes {scope_text}."
                )
                continue
            boolean_flags = [
                f"`{key}`={'true' if value else 'false'}"
                for key, value in sorted(state_data.items())
            ]
            flags_text = ", ".join(boolean_flags)
            all_false = all(not bool(value) for value in state_data.values())
            baseline = "clean baseline" if all_false else "active faults"
            lines.append(
                f"- `{_display_path(state_path)}` records service fault toggles ({baseline}): {flags_text}."
            )
    else:
        lines.append("- No status snapshots available.")
    lines.append("")

    lines.append("## Evidence inventory")
    lines.append("")
    inventory = [
        (
            ROOT / "qa" / "seed.json",
            "canonical non-journal parity fixture that drives scanner + backtest runs while referencing the enabled bulk_essence contract",
        ),
        (
            ROOT / "qa" / "seed-journal.json",
            "journal-gated fixture that covers high_dim_jewels policy outcomes with the same canonical candidate contract",
        ),
        (
            ROOT / "qa" / "cli" / "seed-scan-plan.txt",
            "captured stdout/stderr proving `poe_trade.cli scan plan --league Mirage --limit 20` ran through the package CLI path during seed.json generation",
        ),
        (
            ROOT / "qa" / "cli" / "seed-research-backtest.txt",
            "captured stdout/stderr proving `poe_trade.cli research backtest --strategy bulk_essence --league Mirage --days 14` ran through the package CLI path during seed.json generation",
        ),
        (
            ROOT / "qa" / "cli" / "seed-journal-scan-plan.txt",
            "captured stdout/stderr proving `poe_trade.cli scan plan --league Mirage --limit 5` ran through the package CLI path during seed-journal generation",
        ),
        (
            ROOT / "qa" / "cli" / "seed-journal-research-backtest.txt",
            "captured stdout/stderr proving `poe_trade.cli research backtest --strategy high_dim_jewels --league Mirage --days 14` ran through the package CLI path during seed-journal generation",
        ),
        (
            ROOT / "qa" / "state" / "auth-session.json",
            "seeded authenticated operator session (`status=connected`) required by CLI flows",
        ),
        (
            ROOT / "qa" / "state" / "faults.json",
            "fault toggle table ensuring scanner services see no degradation during parity runs",
        ),
    ]
    for path, description in inventory:
        if path.exists():
            lines.append(f"- `{_display_path(path)}`: {description}.")
    lines.append("")

    lines.append("## Artifact list")
    lines.append("")
    for path in files:
        lines.append(f"- `{_display_path(path)}`")
    _ = summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
