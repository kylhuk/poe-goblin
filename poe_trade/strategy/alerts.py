from __future__ import annotations

import json
from datetime import datetime, timezone

from ..db import ClickHouseClient, ClickHouseClientError


def list_alerts(client: ClickHouseClient) -> list[dict[str, str]]:
    query = (
        "SELECT alert_id, strategy_id, league, item_or_market_key, status, latest_recorded_at AS recorded_at "
        "FROM ("
        "SELECT alert_id, argMax(strategy_id, recorded_at) AS strategy_id, argMax(league, recorded_at) AS league, "
        "argMax(item_or_market_key, recorded_at) AS item_or_market_key, argMax(status, recorded_at) AS status, max(recorded_at) AS latest_recorded_at "
        "FROM poe_trade.scanner_alert_log GROUP BY alert_id"
        ") ORDER BY latest_recorded_at DESC FORMAT JSONEachRow"
    )
    payload = client.execute(query).strip()
    if not payload:
        return []
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


def ack_alert(client: ClickHouseClient, *, alert_id: str) -> str:
    recorded_at = _format_ts(datetime.now(timezone.utc))
    query = (
        "INSERT INTO poe_trade.scanner_alert_log "
        "(alert_id, scanner_run_id, strategy_id, league, recommendation_source, recommendation_contract_version, producer_version, producer_run_id, item_or_market_key, status, evidence_snapshot, recorded_at) "
        "SELECT "
        f"'{alert_id}' AS alert_id, "
        "scanner_run_id, strategy_id, league, recommendation_source, recommendation_contract_version, producer_version, producer_run_id, item_or_market_key, 'acked' AS status, evidence_snapshot, "
        f"toDateTime64('{recorded_at}', 3, 'UTC') AS recorded_at "
        "FROM ("
        "SELECT scanner_run_id, strategy_id, league, recommendation_source, recommendation_contract_version, producer_version, producer_run_id, item_or_market_key, evidence_snapshot "
        "FROM poe_trade.scanner_alert_log "
        f"WHERE alert_id = '{alert_id}' ORDER BY recorded_at DESC LIMIT 1"
        ")"
    )
    legacy_query = (
        "INSERT INTO poe_trade.scanner_alert_log "
        "SELECT "
        f"'{alert_id}' AS alert_id, "
        "scanner_run_id, strategy_id, league, item_or_market_key, 'acked' AS status, evidence_snapshot, "
        f"toDateTime64('{recorded_at}', 3, 'UTC') AS recorded_at "
        "FROM ("
        "SELECT scanner_run_id, strategy_id, league, item_or_market_key, evidence_snapshot "
        "FROM poe_trade.scanner_alert_log "
        f"WHERE alert_id = '{alert_id}' ORDER BY recorded_at DESC LIMIT 1"
        ")"
    )
    try:
        _ = client.execute(query)
    except ClickHouseClientError as exc:
        message = str(exc).lower()
        if "column" not in message or (
            "unknown" not in message and "missing" not in message
        ):
            raise
        _ = client.execute(legacy_query)
    return alert_id


def _format_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
