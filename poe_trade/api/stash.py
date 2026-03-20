from __future__ import annotations

import json
import re
from typing import Any, cast

from poe_trade.db import ClickHouseClient
from poe_trade.db.clickhouse import ClickHouseClientError

_PRICE_NOTE_PATTERN = re.compile(
    r"^~(?:b/o|price)\s+([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z]+)$",
    re.IGNORECASE,
)


class StashBackendUnavailable(RuntimeError):
    pass


def _safe_json_rows(client: ClickHouseClient, query: str) -> list[dict[str, Any]]:
    try:
        payload = client.execute(query).strip()
    except ClickHouseClientError as exc:
        raise StashBackendUnavailable("stash backend unavailable") from exc
    if not payload:
        return []
    return [
        cast(dict[str, Any], row)
        for row in (json.loads(line) for line in payload.splitlines() if line.strip())
        if isinstance(row, dict)
    ]


def stash_status_payload(
    client: ClickHouseClient,
    *,
    league: str,
    realm: str,
    enable_account_stash: bool,
    session: dict[str, Any] | None,
) -> dict[str, Any]:
    if not enable_account_stash:
        return {
            "status": "feature_unavailable",
            "connected": False,
            "tabCount": 0,
            "itemCount": 0,
            "reason": "set POE_ENABLE_ACCOUNT_STASH=true to enable stash APIs",
            "featureFlag": "POE_ENABLE_ACCOUNT_STASH",
            "session": None,
        }
    if session is None:
        return {
            "status": "disconnected",
            "connected": False,
            "tabCount": 0,
            "itemCount": 0,
            "session": None,
        }
    session_status = str(session.get("status") or "")
    if session_status == "session_expired":
        return {
            "status": "session_expired",
            "connected": False,
            "tabCount": 0,
            "itemCount": 0,
            "session": {
                "accountName": str(session.get("account_name") or ""),
                "expiresAt": str(session.get("expires_at") or ""),
            },
        }
    if session_status != "connected":
        return {
            "status": "disconnected",
            "connected": False,
            "tabCount": 0,
            "itemCount": 0,
            "session": None,
        }

    raw_account_name = str(session.get("account_name") or "")
    if not raw_account_name:
        return {
            "status": "disconnected",
            "connected": False,
            "tabCount": 0,
            "itemCount": 0,
            "session": None,
        }
    account_name = _escape_sql_literal(raw_account_name)
    published_rows = _safe_json_rows(
        client,
        " ".join(
            [
                "SELECT",
                "active.scan_id AS scan_id,",
                "active.published_at AS published_at,",
                "countDistinct(items.tab_id) AS tabs,",
                "count() AS items",
                "FROM poe_trade.account_stash_active_scans AS active",
                "LEFT JOIN poe_trade.account_stash_scan_items AS items",
                "ON items.scan_id = active.scan_id",
                f"AND items.account_name = '{account_name}'",
                f"AND items.league = '{_escape_sql_literal(league)}'",
                f"AND items.realm = '{_escape_sql_literal(realm)}'",
                f"WHERE active.account_name = '{account_name}'",
                f"AND active.league = '{_escape_sql_literal(league)}'",
                f"AND active.realm = '{_escape_sql_literal(realm)}'",
                "GROUP BY active.scan_id, active.published_at",
                "ORDER BY active.published_at DESC LIMIT 1 FORMAT JSONEachRow",
            ]
        ),
    )
    run_rows = _safe_json_rows(
        client,
        " ".join(
            [
                "SELECT scan_id, status, started_at, tabs_total, tabs_processed, items_total, items_processed",
                "FROM poe_trade.account_stash_valuation_runs",
                f"WHERE account_name = '{account_name}'",
                f"AND league = '{_escape_sql_literal(league)}'",
                f"AND realm = '{_escape_sql_literal(realm)}'",
                "ORDER BY started_at DESC LIMIT 1 FORMAT JSONEachRow",
            ]
        ),
    )

    published = published_rows[0] if published_rows else {}
    latest_run = run_rows[0] if run_rows else {}
    tabs = int(published.get("tabs") or 0)
    snapshots = int(published.get("items") or 0)
    valuation_status = "idle"
    if str(latest_run.get("status") or "") == "running":
        valuation_status = "running"
    elif published:
        valuation_status = "completed"
    return {
        "status": "connected_populated" if snapshots > 0 else "connected_empty",
        "connected": True,
        "tabCount": tabs,
        "itemCount": snapshots,
        "valuation": {
            "status": valuation_status,
            "activeScanId": str(latest_run.get("scan_id") or "") or None,
            "lastSuccessfulScanId": str(published.get("scan_id") or "") or None,
            "lastSuccessfulFullScanAt": str(published.get("published_at") or "")
            or None,
            "tabsProcessed": int(latest_run.get("tabs_processed") or tabs),
            "tabsTotal": int(latest_run.get("tabs_total") or tabs),
            "itemsProcessed": int(latest_run.get("items_processed") or snapshots),
            "itemsTotal": int(latest_run.get("items_total") or snapshots),
        },
        "session": {
            "accountName": raw_account_name,
            "expiresAt": str(session.get("expires_at") or ""),
        },
    }


def fetch_stash_tabs(
    client: ClickHouseClient,
    *,
    league: str,
    realm: str,
    account_name: str = "",
) -> dict[str, Any]:
    escaped_account = _escape_sql_literal(account_name)
    rows = _safe_json_rows(
        client,
        " ".join(
            [
                "SELECT",
                "items.tab_id, items.tab_name, items.tab_type,",
                "items.item_fingerprint, items.item_id, items.item_name, items.item_class, items.rarity,",
                "items.x, items.y, items.w, items.h, items.listed_price, items.currency, items.icon_url,",
                "values.predicted_price, values.confidence, values.price_p10, values.price_p90, values.priced_at, values.scan_id",
                "FROM poe_trade.account_stash_active_scans AS active",
                "INNER JOIN poe_trade.account_stash_scan_items AS items ON items.scan_id = active.scan_id",
                "LEFT JOIN poe_trade.account_stash_item_valuations AS values",
                "ON values.scan_id = items.scan_id AND values.item_fingerprint = items.item_fingerprint",
                f"WHERE active.account_name = '{escaped_account}'",
                f"AND active.league = '{_escape_sql_literal(league)}'",
                f"AND active.realm = '{_escape_sql_literal(realm)}'",
                "ORDER BY items.tab_id, items.item_name FORMAT JSONEachRow",
            ]
        ),
    )
    if not rows:
        return {"stashTabs": []}

    tabs_by_id: dict[str, dict[str, Any]] = {}
    valuation_scan_id = None
    for row in rows:
        tab_id = str(row.get("tab_id") or "")
        if not tab_id:
            continue
        if tab_id not in tabs_by_id:
            tabs_by_id[tab_id] = {
                "id": tab_id,
                "name": str(row.get("tab_name") or tab_id),
                "type": _normalize_tab_type(str(row.get("tab_type") or "normal")),
                "items": [],
            }
        valuation_scan_id = valuation_scan_id or str(row.get("scan_id") or "") or None
        tabs_by_id[tab_id]["items"].append(_to_api_item_from_row(row))
    return {
        "stashTabs": list(tabs_by_id.values()),
        "valuationScanId": valuation_scan_id,
    }


def _to_api_item_from_row(row: dict[str, Any]) -> dict[str, Any]:
    listed_value = row.get("listed_price")
    estimated = float(row.get("predicted_price") or 0.0)
    confidence = float(row.get("confidence") or 0.0)
    if isinstance(listed_value, (int, float)):
        listed = float(listed_value)
    else:
        listed = None
    delta = 0.0 if listed is None else estimated - listed
    delta_percent = 0.0 if listed in (None, 0) else (delta / listed) * 100.0
    evaluation = "well_priced"
    if delta_percent >= 10:
        evaluation = "mispriced"
    elif delta_percent >= 3:
        evaluation = "could_be_better"
    return {
        "id": str(row.get("item_fingerprint") or row.get("item_id") or ""),
        "itemFingerprint": str(row.get("item_fingerprint") or ""),
        "name": str(row.get("item_name") or "Unknown"),
        "x": int(row.get("x") or 0),
        "y": int(row.get("y") or 0),
        "w": int(row.get("w") or 1),
        "h": int(row.get("h") or 1),
        "itemClass": str(row.get("item_class") or "Unknown"),
        "rarity": str(row.get("rarity") or "normal"),
        "listedPrice": listed,
        "estimatedPrice": estimated,
        "estimatedPriceConfidence": confidence,
        "priceP10": row.get("price_p10"),
        "priceP90": row.get("price_p90"),
        "pricedAt": row.get("priced_at"),
        "priceDeltaChaos": delta,
        "priceDeltaPercent": delta_percent,
        "priceEvaluation": evaluation,
        "currency": str(row.get("currency") or "chaos"),
        "iconUrl": str(row.get("icon_url") or ""),
    }


def stash_item_history_payload(
    client: ClickHouseClient,
    *,
    league: str,
    realm: str,
    account_name: str,
    item_fingerprint: str,
) -> dict[str, Any]:
    escaped_account = _escape_sql_literal(account_name)
    escaped_fingerprint = _escape_sql_literal(item_fingerprint)
    rows = _safe_json_rows(
        client,
        " ".join(
            [
                "SELECT value.scan_id, value.predicted_price, value.confidence, value.price_p10, value.price_p90, value.priced_at",
                "FROM poe_trade.account_stash_item_valuations AS value",
                "INNER JOIN poe_trade.account_stash_valuation_runs AS run",
                "ON run.scan_id = value.scan_id",
                f"WHERE value.account_name = '{escaped_account}'",
                f"AND value.league = '{_escape_sql_literal(league)}'",
                f"AND value.realm = '{_escape_sql_literal(realm)}'",
                f"AND value.item_fingerprint = '{escaped_fingerprint}'",
                "AND run.status = 'completed'",
                "AND run.published_at IS NOT NULL",
                "ORDER BY value.priced_at ASC FORMAT JSONEachRow",
            ]
        ),
    )
    return {
        "itemFingerprint": item_fingerprint,
        "history": [
            {
                "scanId": str(row.get("scan_id") or ""),
                "predictedPrice": float(row.get("predicted_price") or 0.0),
                "confidence": float(row.get("confidence") or 0.0),
                "priceP10": row.get("price_p10"),
                "priceP90": row.get("price_p90"),
                "pricedAt": row.get("priced_at"),
            }
            for row in rows
        ],
    }


def _parse_listed_price(raw: str) -> tuple[float, str] | None:
    match = _PRICE_NOTE_PATTERN.match(raw.strip())
    if not match:
        return None
    return float(match.group(1)), match.group(2).lower()


def _normalize_tab_type(raw: str) -> str:
    normalized = raw.lower().strip()
    if normalized in {"normal", "quad", "currency", "map"}:
        return normalized
    return "normal"


def _rarity_from_frame_type(frame_type: Any) -> str:
    mapping = {0: "normal", 1: "magic", 2: "rare", 3: "unique"}
    if isinstance(frame_type, int):
        return mapping.get(frame_type, "normal")
    return "normal"


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")
