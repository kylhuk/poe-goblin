from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from poe_trade.db.clickhouse import ClickHouseClient

DEFAULT_CLICKHOUSE_ENDPOINT = "http://127.0.0.1:18123"
DEFAULT_LEAGUE = "Mirage"
DEFAULT_REALM = "pc"
STATE_ROOT = Path(".sisyphus/state/qa")
FAULTS_PATH = STATE_ROOT / "faults.json"
SESSION_PATH = STATE_ROOT / "auth-session.json"


@dataclass(frozen=True)
class SeedSummary:
    scanner_recommendations: int
    scanner_alerts: int
    stash_tabs: int
    stash_items: int
    ml_train_runs: int
    ml_promotion_audits: int


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
        summary = seed(client)
        write_json(
            Path(_arg_str(args, "output", "qa-seed.json")),
            {
                "seeded_at": now_iso(),
                "clickhouse_endpoint": endpoint,
                "league": DEFAULT_LEAGUE,
                "realm": DEFAULT_REALM,
                "summary": {
                    "scanner_recommendations": summary.scanner_recommendations,
                    "scanner_alerts": summary.scanner_alerts,
                    "stash_tabs": summary.stash_tabs,
                    "stash_items": summary.stash_items,
                    "ml_train_runs": summary.ml_train_runs,
                    "ml_promotion_audits": summary.ml_promotion_audits,
                    "simulated_auth_session": str(SESSION_PATH),
                },
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


def seed(client: ClickHouseClient) -> SeedSummary:
    _reset_seed_tables(client)
    _ = client.execute(_scanner_seed_sql())
    _ = client.execute(_stash_seed_sql())
    _ = client.execute(_ingest_status_seed_sql())
    _ = client.execute(_ml_seed_sql())

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

    return SeedSummary(
        scanner_recommendations=2,
        scanner_alerts=2,
        stash_tabs=2,
        stash_items=3,
        ml_train_runs=1,
        ml_promotion_audits=1,
    )


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
        "poe_trade.scanner_recommendations",
        "poe_trade.scanner_alert_log",
        "poe_trade.raw_account_stash_snapshot",
        "poe_trade.poe_ingest_status",
        "poe_trade.ml_train_runs",
        "poe_trade.ml_promotion_audit_v1",
    ):
        _ = client.execute(f"TRUNCATE TABLE IF EXISTS {table}")


def _scanner_seed_sql() -> str:
    return (
        "INSERT INTO poe_trade.scanner_recommendations "
        "(scanner_run_id, strategy_id, league, item_or_market_key, why_it_fired, buy_plan, max_buy, transform_plan, exit_plan, execution_venue, expected_profit_chaos, expected_roi, expected_hold_time, confidence, evidence_snapshot, recorded_at) VALUES "
        "('qa-scan-1','bulk_essence','Mirage','Screaming Essence of Greed','spread>10%','buy <= 12c',12.0,'none','list @ 18c','trade_site',6.0,0.5,'2h',0.84,'qa evidence A',toDateTime64('2026-01-01 00:00:00',3,'UTC')),"
        "('qa-scan-1','bulk_fragment','Mirage','Maven''s Writ','deep discount','buy <= 105c',105.0,'none','list @ 135c','trade_site',30.0,0.285,'6h',0.79,'qa evidence B',toDateTime64('2026-01-01 00:00:00',3,'UTC'));"
        "INSERT INTO poe_trade.scanner_alert_log "
        "(alert_id, scanner_run_id, strategy_id, league, item_or_market_key, status, evidence_snapshot, recorded_at) VALUES "
        "('qa-alert-1','qa-scan-1','bulk_essence','Mirage','Screaming Essence of Greed','open','qa alert evidence A',toDateTime64('2026-01-01 00:00:00',3,'UTC')),"
        "('qa-alert-2','qa-scan-1','bulk_fragment','Mirage','Maven''s Writ','acked','qa alert evidence B',toDateTime64('2026-01-01 00:00:00',3,'UTC'))"
    )


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
        "('psapi:pc','psapi',1,'Mirage','pc','market_harvester','qa-cursor-1','qa-next-1',now64(3),1.2,0,NULL,'','running'),"
        "('account_stash:pc:Mirage','account_stash',1,'Mirage','pc','account_stash_harvester','qa-cursor-2','qa-next-2',now64(3),0.2,0,NULL,'','running')"
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


if __name__ == "__main__":
    raise SystemExit(main())
