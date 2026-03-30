from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from poe_trade.db.clickhouse import ClickHouseClient
from poe_trade.strategy.backtest import fetch_backtest_summary_rows, run_backtest
from poe_trade.strategy.scanner import run_scan_once

DEFAULT_CLICKHOUSE_ENDPOINT = "http://127.0.0.1:8123"
DEFAULT_LEAGUE = "Mirage"
DEFAULT_REALM = "pc"
STATE_ROOT = Path("poe_trade/evidence/qa/state")
CLI_PROOF_ROOT = Path("poe_trade/evidence/qa/cli")
FAULTS_PATH = STATE_ROOT / "faults.json"
SESSION_PATH = STATE_ROOT / "auth-session.json"
SEED_TIME_BUCKET = "2099-01-01 00:00:00"
SEED_UPDATED_AT = "2099-01-01 00:00:00.000"
BACKTEST_LOOKBACK_DAYS = 14
PREFERRED_JOURNAL_STRATEGY_ID = "high_dim_jewels"


@dataclass(frozen=True)
class SeedSummary:
    scanner_recommendations: int
    scanner_alerts: int
    stash_tabs: int
    stash_items: int
    ml_train_runs: int
    ml_promotion_audits: int


@dataclass(frozen=True)
class SeedResult:
    summary: SeedSummary
    fixtures: dict[str, object]
    parity_evidence: dict[str, object]


def main() -> int:
    parser = argparse.ArgumentParser(description="QA contract utility")
    _ = parser.add_argument(
        "--clickhouse-endpoint",
        default=DEFAULT_CLICKHOUSE_ENDPOINT,
        help="ClickHouse HTTP endpoint",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_parser = subparsers.add_parser("seed", help="Seed deterministic QA fixtures")
    _ = seed_parser.add_argument("--output", required=True, help="Evidence JSON path")

    fault_parser = subparsers.add_parser("fault", help="Apply QA fault profile")
    _ = fault_parser.add_argument(
        "--name",
        choices=(
            "scanner_degraded",
            "stash_empty",
            "api_unavailable",
            "service_action_failure",
        ),
        required=True,
    )
    _ = fault_parser.add_argument("--output", required=True, help="Evidence JSON path")

    clear_parser = subparsers.add_parser("clear-faults", help="Reset QA fault profiles")
    _ = clear_parser.add_argument("--output", required=True, help="Evidence JSON path")

    args = parser.parse_args()
    endpoint = _arg_str(args, "clickhouse_endpoint", DEFAULT_CLICKHOUSE_ENDPOINT)
    command = _arg_str(args, "command", "")
    client = ClickHouseClient.from_env(endpoint)

    if command == "seed":
        output_path = Path(_arg_str(args, "output", "qa-seed.json"))
        result = seed(client, seed_label=output_path.stem)
        write_json(
            output_path,
            {
                "seeded_at": now_iso(),
                "clickhouse_endpoint": endpoint,
                "league": DEFAULT_LEAGUE,
                "realm": DEFAULT_REALM,
                "summary": {
                    "scanner_recommendations": result.summary.scanner_recommendations,
                    "scanner_alerts": result.summary.scanner_alerts,
                    "stash_tabs": result.summary.stash_tabs,
                    "stash_items": result.summary.stash_items,
                    "ml_train_runs": result.summary.ml_train_runs,
                    "ml_promotion_audits": result.summary.ml_promotion_audits,
                    "simulated_auth_session": str(SESSION_PATH),
                },
                "fixtures": result.fixtures,
                "parity_evidence": result.parity_evidence,
            },
        )
        return 0

    if command == "fault":
        write_json(
            Path(_arg_str(args, "output", "qa-fault.json")),
            apply_fault(client, _arg_str(args, "name", "")),
        )
        return 0

    if command == "clear-faults":
        write_json(
            Path(_arg_str(args, "output", "qa-fault-clear.json")), clear_faults()
        )
        return 0

    return 1


def _arg_str(args: argparse.Namespace, name: str, default: str) -> str:
    value: object = getattr(args, name, default)
    return value if isinstance(value, str) else default


def seed(client: ClickHouseClient, *, seed_label: str = "seed") -> SeedResult:
    _reset_seed_tables(client)
    _ = client.execute(_gold_bulk_seed_sql())
    _ = client.execute(_gold_listing_seed_sql())
    _ = client.execute(_stash_seed_sql())
    _ = client.execute(_ingest_status_seed_sql())
    _ = client.execute(_ml_seed_sql())

    strategy_paths = _strategy_parity_paths()
    non_journal = cast(
        dict[str, object], strategy_paths.get("enabled_non_journal") or {}
    )
    journal_gated = cast(dict[str, object], strategy_paths.get("journal_gated") or {})

    non_journal_strategy_id = str(non_journal.get("strategy_id") or "bulk_essence")
    journal_strategy_id = str(
        journal_gated.get("strategy_id") or PREFERRED_JOURNAL_STRATEGY_ID
    )

    non_journal_backtest_run_id = run_backtest(
        client,
        strategy_id=non_journal_strategy_id,
        league=DEFAULT_LEAGUE,
        lookback_days=BACKTEST_LOOKBACK_DAYS,
    )
    scanner_run_id = run_scan_once(client, league=DEFAULT_LEAGUE)
    journal_backtest_run_id = run_backtest(
        client,
        strategy_id=journal_strategy_id,
        league=DEFAULT_LEAGUE,
        lookback_days=BACKTEST_LOOKBACK_DAYS,
    )

    non_journal_parity = _collect_non_journal_parity(
        client,
        strategy_id=non_journal_strategy_id,
        scanner_run_id=scanner_run_id,
        backtest_run_id=non_journal_backtest_run_id,
    )
    journal_parity = _collect_journal_backtest_parity(
        client,
        strategy_id=journal_strategy_id,
        backtest_run_id=journal_backtest_run_id,
    )
    is_journal_seed = "journal" in seed_label.casefold()
    backtest_strategy_id = (
        journal_strategy_id if is_journal_seed else non_journal_strategy_id
    )
    scan_limit = 5 if is_journal_seed else 20
    cli_proof = _capture_cli_proof_artifacts(
        seed_label=seed_label,
        backtest_strategy_id=backtest_strategy_id,
        scan_limit=scan_limit,
    )

    scanner_alert_ids = _query_string_column(
        client,
        (
            "SELECT alert_id FROM poe_trade.scanner_alert_log "
            + f"WHERE scanner_run_id = '{_escape_sql(scanner_run_id)}' "
            + "ORDER BY alert_id FORMAT JSONEachRow"
        ),
        "alert_id",
    )
    scanner_strategy_ids = _query_string_column(
        client,
        (
            "SELECT DISTINCT strategy_id FROM poe_trade.scanner_recommendations "
            + f"WHERE scanner_run_id = '{_escape_sql(scanner_run_id)}' "
            + "ORDER BY strategy_id FORMAT JSONEachRow"
        ),
        "strategy_id",
    )
    scanner_recommendation_count = _query_int_value(
        client,
        (
            "SELECT count() AS count FROM poe_trade.scanner_recommendations "
            + f"WHERE scanner_run_id = '{_escape_sql(scanner_run_id)}' "
            + "FORMAT JSONEachRow"
        ),
        "count",
    )

    write_json(
        SESSION_PATH,
        {
            "account_name": "qa-exile",
            "status": "connected",
            "scope": ["account:profile", "account:stashes"],
            "session_id": "qa-session-mirage",
            "expires_at": "2099-01-01T00:00:00Z",
            "seeded_at": now_iso(),
        },
    )
    if not FAULTS_PATH.exists():
        write_json(FAULTS_PATH, default_faults())

    summary = SeedSummary(
        scanner_recommendations=scanner_recommendation_count,
        scanner_alerts=len(scanner_alert_ids),
        stash_tabs=2,
        stash_items=3,
        ml_train_runs=1,
        ml_promotion_audits=1,
    )

    return SeedResult(
        summary=summary,
        fixtures={
            "scanner": {
                "scanner_run_ids": [scanner_run_id],
                "alert_ids": scanner_alert_ids,
                "strategy_ids": scanner_strategy_ids,
            },
            "stash": {
                "snapshot_ids": ["qa-snapshot-1", "qa-snapshot-2"],
                "next_change_ids": ["qa-next-1", "qa-next-2"],
            },
            "ml": {
                "run_ids": ["qa-ml-run-1"],
                "promotion_candidate_run_ids": ["qa-ml-run-1"],
            },
            "backtest": {
                "run_ids": [non_journal_backtest_run_id, journal_backtest_run_id],
                "strategy_ids": [non_journal_strategy_id, journal_strategy_id],
            },
        },
        parity_evidence={
            "seeded_snapshot": {
                "time_bucket": SEED_TIME_BUCKET,
                "league": DEFAULT_LEAGUE,
                "realm": DEFAULT_REALM,
                "tables": [
                    "poe_trade.gold_bulk_premium_hour",
                    "poe_trade.gold_listing_ref_hour",
                ],
            },
            "strategy_paths": strategy_paths,
            "state_paths": {
                "faults_json": str(FAULTS_PATH),
                "auth_session_json": str(SESSION_PATH),
            },
            "enabled_non_journal_pair": non_journal_parity,
            "journal_gated_backtest": journal_parity,
            "cli_proof_artifacts": cli_proof,
        },
    )


def _capture_cli_proof_artifacts(
    *, seed_label: str, backtest_strategy_id: str, scan_limit: int
) -> dict[str, object]:
    sanitized_label = "".join(
        character
        for character in seed_label
        if character.isalnum() or character in {"-", "_"}
    ).strip("-_")
    if not sanitized_label:
        sanitized_label = "seed"

    scan_plan_command = [
        sys.executable,
        "-m",
        "poe_trade.cli",
        "scan",
        "plan",
        "--league",
        DEFAULT_LEAGUE,
        "--limit",
        str(scan_limit),
    ]
    research_backtest_command = [
        sys.executable,
        "-m",
        "poe_trade.cli",
        "research",
        "backtest",
        "--strategy",
        backtest_strategy_id,
        "--league",
        DEFAULT_LEAGUE,
        "--days",
        str(BACKTEST_LOOKBACK_DAYS),
    ]
    artifacts: dict[str, object] = {
        "scan_plan": _run_cli_proof_command(
            command=scan_plan_command,
            artifact_path=CLI_PROOF_ROOT / f"{sanitized_label}-scan-plan.txt",
        ),
        "research_backtest": _run_cli_proof_command(
            command=research_backtest_command,
            artifact_path=CLI_PROOF_ROOT / f"{sanitized_label}-research-backtest.txt",
        ),
    }
    return artifacts


def _run_cli_proof_command(
    *, command: list[str], artifact_path: Path
) -> dict[str, object]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    command_text = " ".join(command)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    payload_lines = [
        f"command: {command_text}",
        f"exit_code: {completed.returncode}",
        "stdout:",
        stdout if stdout else "<empty>",
        "stderr:",
        stderr if stderr else "<empty>",
    ]
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    _ = artifact_path.write_text("\n".join(payload_lines) + "\n", encoding="utf-8")

    if completed.returncode != 0:
        raise RuntimeError(f"CLI proof command failed: {command_text}")

    return {
        "command": command_text,
        "artifact_path": str(artifact_path),
        "exit_code": completed.returncode,
    }


def apply_fault(client: ClickHouseClient, fault_name: str) -> dict[str, object]:
    faults = read_faults()
    for key in faults:
        faults[key] = False
    faults[fault_name] = True

    side_effects: dict[str, object] = {}
    if fault_name == "stash_empty":
        _ = client.execute(
            "TRUNCATE TABLE IF EXISTS poe_trade.raw_account_stash_snapshot"
        )
        side_effects["stash_rows"] = 0
    if fault_name == "scanner_degraded":
        query = (
            "INSERT INTO poe_trade.poe_ingest_status "
            "(queue_key, feed_kind, contract_version, league, realm, source, last_cursor, next_change_id, last_ingest_at, request_rate, error_count, stalled_since, last_error, status) VALUES "
            "('scanner:worker','scanner',1,'Mirage','pc','scanner_worker','qa-cursor','qa-next',toDateTime64('2026-01-01 00:00:00',3,'UTC'),0.0,5,toDateTime64('2026-01-01 00:00:00',3,'UTC'),'forced_qa_fault','degraded')"
        )
        _ = client.execute(query)
        side_effects["scanner_status"] = "degraded"

    write_json(FAULTS_PATH, faults)
    return {
        "fault_applied": fault_name,
        "faults": faults,
        "side_effects": side_effects,
        "recorded_at": now_iso(),
    }


def clear_faults() -> dict[str, object]:
    faults = default_faults()
    write_json(FAULTS_PATH, faults)
    return {
        "fault_applied": None,
        "faults": faults,
        "recorded_at": now_iso(),
    }


def default_faults() -> dict[str, bool]:
    return {
        "scanner_degraded": False,
        "stash_empty": False,
        "api_unavailable": False,
        "service_action_failure": False,
    }


def read_faults() -> dict[str, bool]:
    if not FAULTS_PATH.exists():
        return default_faults()
    payload_obj = cast(object, json.loads(FAULTS_PATH.read_text(encoding="utf-8")))
    if not isinstance(payload_obj, dict):
        return default_faults()
    payload = cast(dict[object, object], payload_obj)
    parsed = default_faults()
    for key in parsed:
        parsed[key] = bool(payload.get(key, False))
    return parsed


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _reset_seed_tables(client: ClickHouseClient) -> None:
    for table in (
        "poe_trade.gold_bulk_premium_hour",
        "poe_trade.gold_listing_ref_hour",
        "poe_trade.raw_account_stash_snapshot",
        "poe_trade.poe_ingest_status",
        "poe_trade.scanner_recommendations",
        "poe_trade.scanner_alert_log",
        "poe_trade.research_backtest_runs",
        "poe_trade.research_backtest_summary",
        "poe_trade.research_backtest_detail",
        "poe_trade.ml_train_runs",
        "poe_trade.ml_promotion_audit_v1",
    ):
        _ = client.execute(f"TRUNCATE TABLE IF EXISTS {table}")


def _gold_bulk_seed_sql() -> str:
    return (
        "INSERT INTO poe_trade.gold_bulk_premium_hour "
        "(time_bucket, realm, league, category, bulk_threshold, bulk_listing_count, small_listing_count, median_bulk_price_amount, median_small_price_amount, updated_at) VALUES "
        f"(toDateTime64('{SEED_TIME_BUCKET}',0,'UTC'),'pc','Mirage','essence',20,60,90,1.5,3.0,toDateTime64('{SEED_UPDATED_AT}',3,'UTC'))"
    )


def _gold_listing_seed_sql() -> str:
    return (
        "INSERT INTO poe_trade.gold_listing_ref_hour "
        "(time_bucket, realm, league, category, base_type, price_currency, listing_count, median_price_amount, updated_at) VALUES "
        f"(toDateTime64('{SEED_TIME_BUCKET}',0,'UTC'),'pc','Mirage','cluster_jewel','Malachite Cluster Jewel','chaos',140,700.0,toDateTime64('{SEED_UPDATED_AT}',3,'UTC'))"
    )


def _collect_non_journal_parity(
    client: ClickHouseClient,
    *,
    strategy_id: str,
    scanner_run_id: str,
    backtest_run_id: str,
) -> dict[str, object]:
    scanner_keys = _query_string_column(
        client,
        (
            "SELECT item_or_market_key FROM poe_trade.scanner_recommendations "
            + f"WHERE scanner_run_id = '{_escape_sql(scanner_run_id)}' "
            + f"AND strategy_id = '{_escape_sql(strategy_id)}' "
            + "ORDER BY item_or_market_key FORMAT JSONEachRow"
        ),
        "item_or_market_key",
    )
    backtest_keys = _query_string_column(
        client,
        (
            "SELECT item_or_market_key FROM poe_trade.research_backtest_detail "
            + f"WHERE run_id = '{_escape_sql(backtest_run_id)}' "
            + f"AND strategy_id = '{_escape_sql(strategy_id)}' "
            + "ORDER BY item_or_market_key FORMAT JSONEachRow"
        ),
        "item_or_market_key",
    )
    summary_rows = fetch_backtest_summary_rows(client, run_id=backtest_run_id)
    summary_row = summary_rows[0] if summary_rows else {}
    summary_status = str(summary_row.get("status") or "unknown")
    opportunity_count = int(summary_row.get("opportunity_count") or 0)

    scanner_count = len(scanner_keys)
    backtest_count = len(backtest_keys)
    return {
        "strategy_id": strategy_id,
        "scanner_run_id": scanner_run_id,
        "backtest_run_id": backtest_run_id,
        "scanner_item_or_market_keys": scanner_keys,
        "backtest_item_or_market_keys": backtest_keys,
        "scanner_recommendation_count": scanner_count,
        "backtest_opportunity_count": opportunity_count,
        "key_count_comparison": {
            "scanner_recommendation_count": scanner_count,
            "backtest_detail_count": backtest_count,
            "count_delta": scanner_count - backtest_count,
            "keys_match": scanner_keys == backtest_keys,
        },
        "backtest_summary_status": summary_status,
        "backtest_summary_text": str(summary_row.get("summary") or ""),
    }


def _collect_journal_backtest_parity(
    client: ClickHouseClient,
    *,
    strategy_id: str,
    backtest_run_id: str,
) -> dict[str, object]:
    summary_rows = fetch_backtest_summary_rows(client, run_id=backtest_run_id)
    summary_row = summary_rows[0] if summary_rows else {}
    return {
        "strategy_id": strategy_id,
        "backtest_run_id": backtest_run_id,
        "status": str(summary_row.get("status") or "unknown"),
        "summary": str(summary_row.get("summary") or ""),
        "opportunity_count": int(summary_row.get("opportunity_count") or 0),
        "evidence": {
            "requires_journal": True,
            "source_table": "poe_trade.gold_listing_ref_hour",
            "seeded_time_bucket": SEED_TIME_BUCKET,
        },
    }


def _query_string_column(
    client: ClickHouseClient,
    sql: str,
    column: str,
) -> list[str]:
    rows = _parse_json_rows(client.execute(sql))
    values = {
        str(row.get(column)).strip()
        for row in rows
        if str(row.get(column) or "").strip()
    }
    return sorted(values)


def _query_int_value(
    client: ClickHouseClient,
    sql: str,
    column: str,
    *,
    default: int = 0,
) -> int:
    rows = _parse_json_rows(client.execute(sql))
    if not rows:
        return default
    return _as_int(rows[0].get(column), default=default)


def _parse_json_rows(payload: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in payload.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        parsed = cast(object, json.loads(cleaned))
        if isinstance(parsed, dict):
            rows.append(cast(dict[str, object], parsed))
    return rows


def _escape_sql(value: str) -> str:
    return value.replace("'", "''")


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _stash_seed_sql() -> str:
    payload_currency = json.dumps(
        {
            "tab": {"n": "Currency", "type": "currency"},
            "payload": {
                "items": [
                    {
                        "id": "qa-item-1",
                        "name": "Chaos Orb",
                        "typeLine": "Chaos Orb",
                        "x": 0,
                        "y": 0,
                        "w": 1,
                        "h": 1,
                        "itemClass": "Currency",
                        "frameType": 0,
                        "chaosValue": 1.0,
                        "note": "~price 1 chaos",
                    },
                    {
                        "id": "qa-item-2",
                        "name": "Divine Orb",
                        "typeLine": "Divine Orb",
                        "x": 1,
                        "y": 0,
                        "w": 1,
                        "h": 1,
                        "itemClass": "Currency",
                        "frameType": 0,
                        "chaosValue": 220.0,
                        "note": "~b/o 220 chaos",
                    },
                ]
            },
        }
    ).replace("'", "\\'")
    payload_maps = json.dumps(
        {
            "tab": {"n": "Maps", "type": "map"},
            "payload": {
                "items": [
                    {
                        "id": "qa-item-3",
                        "name": "Cemetery Map",
                        "typeLine": "Cemetery Map",
                        "x": 2,
                        "y": 0,
                        "w": 1,
                        "h": 1,
                        "itemClass": "Maps",
                        "frameType": 1,
                        "chaosValue": 9.0,
                        "note": "~price 8 chaos",
                    }
                ]
            },
        }
    ).replace("'", "\\'")
    return (
        "INSERT INTO poe_trade.raw_account_stash_snapshot "
        "(snapshot_id, captured_at, realm, league, tab_id, next_change_id, payload_json) VALUES "
        f"('qa-snapshot-1',toDateTime64('2026-01-01 00:00:00',3,'UTC'),'pc','Mirage','currency','qa-next-1','{payload_currency}'),"
        f"('qa-snapshot-2',toDateTime64('2026-01-01 00:00:00',3,'UTC'),'pc','Mirage','maps','qa-next-2','{payload_maps}')"
    )


def _ingest_status_seed_sql() -> str:
    return (
        "INSERT INTO poe_trade.poe_ingest_status "
        "(queue_key, feed_kind, contract_version, league, realm, source, last_cursor, next_change_id, last_ingest_at, request_rate, error_count, stalled_since, last_error, status) VALUES "
        "('psapi:pc','psapi',1,'Mirage','pc','market_harvester','qa-cursor-1','qa-next-1',now64(3),1.2,0,NULL,'','running')"
    )


def _ml_seed_sql() -> str:
    return (
        "INSERT INTO poe_trade.ml_train_runs "
        "(run_id, league, stage, current_route, routes_done, routes_total, rows_processed, eta_seconds, chosen_backend, worker_count, memory_budget_gb, active_model_version, status, resume_token, started_at, updated_at, stop_reason, tuning_config_id, eval_run_id) VALUES "
        "('qa-ml-run-1','Mirage','promotion','saleability',5,5,1500,NULL,'lightgbm',4,8.0,'qa-model-v1','completed','qa-resume-1',toDateTime64('2026-01-01 00:00:00',3,'UTC'),toDateTime64('2026-01-01 00:05:00',3,'UTC'),'stopped_no_improvement','qa-tuning-1','qa-eval-1');"
        "INSERT INTO poe_trade.ml_promotion_audit_v1 "
        "(league, candidate_run_id, incumbent_run_id, candidate_model_version, incumbent_model_version, verdict, avg_mdape_candidate, avg_mdape_incumbent, coverage_candidate, coverage_incumbent, stop_reason, recorded_at) VALUES "
        "('Mirage','qa-ml-run-1','qa-ml-run-prev','qa-model-v1','qa-model-v0','promote',0.14,0.18,0.87,0.82,'stopped_no_improvement',toDateTime64('2026-01-01 00:05:00',3,'UTC'))"
    )


def _strategy_parity_paths() -> dict[str, object]:
    strategies_root = Path("strategies")
    entries: list[dict[str, object]] = []

    for strategy_path in sorted(strategies_root.glob("*/strategy.toml")):
        payload_obj = cast(
            object, tomllib.loads(strategy_path.read_text(encoding="utf-8"))
        )
        if not isinstance(payload_obj, dict):
            continue
        payload = cast(dict[object, object], payload_obj)
        params_obj = payload.get("params")
        params: dict[str, object] = {}
        if isinstance(params_obj, dict):
            params = cast(dict[str, object], params_obj)
        strategy_id = str(payload.get("id") or strategy_path.parent.name)
        enabled = bool(payload.get("enabled", False))
        requires_journal = bool(
            payload.get("requires_journal", params.get("requires_journal", False))
        )
        entries.append(
            {
                "strategy_id": strategy_id,
                "enabled": enabled,
                "requires_journal": requires_journal,
                "strategy_toml": str(strategy_path),
                "candidate_sql": f"poe_trade/sql/strategy/{strategy_id}/candidate.sql",
                "discover_sql": f"poe_trade/sql/strategy/{strategy_id}/discover.sql",
            }
        )

    enabled_non_journal = next(
        (
            entry
            for entry in entries
            if bool(entry["enabled"]) and not bool(entry["requires_journal"])
        ),
        None,
    )
    preferred_journal = next(
        (
            entry
            for entry in entries
            if (
                str(entry.get("strategy_id")) == PREFERRED_JOURNAL_STRATEGY_ID
                and bool(entry["requires_journal"])
            )
        ),
        None,
    )
    journal_gated = preferred_journal or next(
        (entry for entry in entries if bool(entry["requires_journal"])),
        None,
    )

    return {
        "enabled_non_journal": enabled_non_journal,
        "journal_gated": journal_gated,
    }


if __name__ == "__main__":
    raise SystemExit(main())
