from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
from uuid import uuid4

from poe_trade.db import ClickHouseClient

_PRICE_NOTE_PATTERN = re.compile(
    r"^~(?:b/o|price)\s+([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z]+)$",
    re.IGNORECASE,
)


def _fetch_predict_one(
    client: ClickHouseClient, *, league: str, request_payload: dict[str, Any]
) -> dict[str, Any]:
    from .api.ml import fetch_predict_one

    return fetch_predict_one(client, league=league, request_payload=request_payload)


@dataclass(frozen=True)
class StashValuationResult:
    predicted_price: float
    currency: str
    confidence: float
    price_p10: float | None
    price_p90: float | None
    comparable_count: int
    fallback_reason: str
    priced_at: str


def _opt_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _rarity_label(frame_type: Any) -> str:
    mapping = {0: "Normal", 1: "Magic", 2: "Rare", 3: "Unique"}
    if isinstance(frame_type, int):
        return mapping.get(frame_type, "Rare")
    return "Rare"


def fingerprint_item(item: Mapping[str, Any], *, account_name: str, tab_id: str) -> str:
    item_id = str(item.get("id") or "").strip()
    if item_id:
        return f"item:{item_id}"
    stable_payload = {
        "account_name": account_name,
        "tab_id": tab_id,
        "name": str(item.get("name") or item.get("typeLine") or ""),
        "rarity": item.get("frameType"),
        "x": int(item.get("x") or 0),
        "y": int(item.get("y") or 0),
        "w": int(item.get("w") or 1),
        "h": int(item.get("h") or 1),
    }
    return (
        "fp:"
        + sha256(json.dumps(stable_payload, sort_keys=True).encode("utf-8")).hexdigest()
    )


def serialize_stash_item_to_clipboard(item: Mapping[str, Any]) -> str:
    lines = [
        f"Rarity: {_rarity_label(item.get('frameType'))}",
        str(item.get("name") or "").strip(),
        str(
            item.get("typeLine")
            or item.get("baseType")
            or item.get("name")
            or "Unknown"
        ),
        "--------",
    ]
    for section in (
        "implicitMods",
        "explicitMods",
        "craftedMods",
        "enchantMods",
        "fracturedMods",
    ):
        values = item.get(section)
        if isinstance(values, list):
            lines.extend(str(value) for value in values if str(value).strip())
    return "\n".join(line for line in lines if line)


def normalize_stash_prediction(
    payload: Mapping[str, Any], *, comparable_count: int = 0
) -> StashValuationResult:
    raw_interval = payload.get("interval")
    p10_raw = payload.get("price_p10")
    p90_raw = payload.get("price_p90")
    if isinstance(raw_interval, Mapping):
        p10_raw = raw_interval.get("p10") or p10_raw
        p90_raw = raw_interval.get("p90") or p90_raw
    return StashValuationResult(
        predicted_price=float(
            payload.get("predictedValue") or payload.get("price_p50") or 0.0
        ),
        currency=str(payload.get("currency") or "chaos"),
        confidence=float(
            payload.get("confidence") or payload.get("confidence_percent") or 0.0
        ),
        price_p10=_opt_float(p10_raw),
        price_p90=_opt_float(p90_raw),
        comparable_count=comparable_count,
        fallback_reason=str(
            payload.get("fallbackReason") or payload.get("fallback_reason") or ""
        ),
        priced_at=datetime.now(timezone.utc).isoformat(),
    )


def estimate_item(
    client: ClickHouseClient, *, league: str, item_text: str
) -> StashValuationResult:
    payload = _fetch_predict_one(
        client,
        league=league,
        request_payload={
            "input_format": "poe-clipboard",
            "payload": item_text,
            "output_mode": "json",
        },
    )
    comparable_count = (
        len(payload.get("comparables") or [])
        if isinstance(payload.get("comparables"), list)
        else 0
    )
    return normalize_stash_prediction(payload, comparable_count=comparable_count)


def estimate_stash_item(
    client: ClickHouseClient,
    *,
    league: str,
    item: Mapping[str, Any],
) -> StashValuationResult:
    return estimate_item(
        client, league=league, item_text=serialize_stash_item_to_clipboard(item)
    )


def _parse_listed_price(note: str) -> tuple[float, str] | None:
    match = _PRICE_NOTE_PATTERN.match(note.strip())
    if not match:
        return None
    return float(match.group(1)), match.group(2).lower()


def run_account_stash_valuation_scan(
    client: ClickHouseClient,
    *,
    league: str,
    realm: str,
    account_name: str,
) -> str:
    escaped_account = account_name.replace("'", "''")
    escaped_league = league.replace("'", "''")
    escaped_realm = realm.replace("'", "''")
    scan_id = uuid4().hex
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    client.execute(
        "INSERT INTO poe_trade.account_stash_valuation_runs "
        "(scan_id, account_name, league, realm, status, started_at, completed_at, failed_at, tabs_total, tabs_processed, items_total, items_processed, error_message, published_at) "
        "FORMAT JSONEachRow\n"
        + json.dumps(
            {
                "scan_id": scan_id,
                "account_name": account_name,
                "league": league,
                "realm": realm,
                "status": "running",
                "started_at": started_at,
                "completed_at": None,
                "failed_at": None,
                "tabs_total": 0,
                "tabs_processed": 0,
                "items_total": 0,
                "items_processed": 0,
                "error_message": "",
                "published_at": None,
            }
        )
    )
    payload = client.execute(
        "SELECT tab_id, argMax(payload_json, captured_at) AS payload_json, max(captured_at) AS observed_at "
        "FROM poe_trade.raw_account_stash_snapshot "
        f"WHERE league = '{escaped_league}' AND realm = '{escaped_realm}' AND account_name = '{escaped_account}' "
        "GROUP BY tab_id ORDER BY tab_id FORMAT JSONEachRow"
    ).strip()
    if not payload:
        return scan_id

    scan_rows: list[dict[str, Any]] = []
    value_rows: list[dict[str, Any]] = []
    tabs_processed = 0
    items_processed = 0
    for line in payload.splitlines():
        row = json.loads(line)
        stash_payload = json.loads(str(row.get("payload_json") or "{}"))
        tab = (
            stash_payload.get("tab")
            if isinstance(stash_payload.get("tab"), dict)
            else {}
        )
        body = (
            stash_payload.get("payload")
            if isinstance(stash_payload.get("payload"), dict)
            else {}
        )
        tab_id = str(row.get("tab_id") or "")
        tab_name = str(tab.get("n") or tab.get("name") or tab_id)
        tab_type = str(tab.get("type") or "normal")
        raw_items = body.get("items")
        items = raw_items if isinstance(raw_items, list) else []
        tabs_processed += 1
        for item in items:
            if not isinstance(item, dict):
                continue
            listed = _parse_listed_price(str(item.get("note") or ""))
            fingerprint = fingerprint_item(
                item, account_name=account_name, tab_id=tab_id
            )
            observed_at = str(row.get("observed_at") or started_at)
            scan_rows.append(
                {
                    "scan_id": scan_id,
                    "account_name": account_name,
                    "league": league,
                    "realm": realm,
                    "tab_id": tab_id,
                    "tab_name": tab_name,
                    "tab_type": tab_type,
                    "item_fingerprint": fingerprint,
                    "item_id": str(item.get("id") or "") or None,
                    "item_name": str(
                        item.get("name") or item.get("typeLine") or "Unknown"
                    ),
                    "item_class": str(item.get("itemClass") or "Unknown"),
                    "rarity": _rarity_label(item.get("frameType")).lower(),
                    "x": int(item.get("x") or 0),
                    "y": int(item.get("y") or 0),
                    "w": int(item.get("w") or 1),
                    "h": int(item.get("h") or 1),
                    "listed_price": listed[0] if listed else None,
                    "currency": listed[1] if listed else "chaos",
                    "icon_url": str(item.get("icon") or ""),
                    "source_observed_at": observed_at,
                    "payload_json": json.dumps(item, ensure_ascii=False),
                }
            )
            prediction = estimate_stash_item(client, league=league, item=item)
            value_rows.append(
                {
                    "scan_id": scan_id,
                    "account_name": account_name,
                    "league": league,
                    "realm": realm,
                    "tab_id": tab_id,
                    "item_fingerprint": fingerprint,
                    "item_id": str(item.get("id") or "") or None,
                    "item_name": str(
                        item.get("name") or item.get("typeLine") or "Unknown"
                    ),
                    "item_class": str(item.get("itemClass") or "Unknown"),
                    "rarity": _rarity_label(item.get("frameType")).lower(),
                    "listed_price": listed[0] if listed else None,
                    "predicted_price": prediction.predicted_price,
                    "confidence": prediction.confidence,
                    "price_p10": prediction.price_p10,
                    "price_p90": prediction.price_p90,
                    "comparable_count": prediction.comparable_count,
                    "fallback_reason": prediction.fallback_reason,
                    "priced_at": prediction.priced_at,
                    "payload_json": json.dumps(item, ensure_ascii=False),
                }
            )
            items_processed += 1

    if scan_rows:
        client.execute(
            "INSERT INTO poe_trade.account_stash_scan_items "
            "(scan_id, account_name, league, realm, tab_id, tab_name, tab_type, item_fingerprint, item_id, item_name, item_class, rarity, x, y, w, h, listed_price, currency, icon_url, source_observed_at, payload_json) "
            "FORMAT JSONEachRow\n"
            + "\n".join(json.dumps(row, ensure_ascii=False) for row in scan_rows)
        )
    if value_rows:
        client.execute(
            "INSERT INTO poe_trade.account_stash_item_valuations "
            "(scan_id, account_name, league, realm, tab_id, item_fingerprint, item_id, item_name, item_class, rarity, listed_price, predicted_price, confidence, price_p10, price_p90, comparable_count, fallback_reason, priced_at, payload_json) "
            "FORMAT JSONEachRow\n"
            + "\n".join(json.dumps(row, ensure_ascii=False) for row in value_rows)
        )

    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    client.execute(
        "INSERT INTO poe_trade.account_stash_active_scans "
        "(account_name, league, realm, scan_id, published_at) FORMAT JSONEachRow\n"
        + json.dumps(
            {
                "account_name": account_name,
                "league": league,
                "realm": realm,
                "scan_id": scan_id,
                "published_at": finished_at,
            }
        )
    )
    client.execute(
        "INSERT INTO poe_trade.account_stash_valuation_runs "
        "(scan_id, account_name, league, realm, status, started_at, completed_at, failed_at, tabs_total, tabs_processed, items_total, items_processed, error_message, published_at) "
        "FORMAT JSONEachRow\n"
        + json.dumps(
            {
                "scan_id": scan_id,
                "account_name": account_name,
                "league": league,
                "realm": realm,
                "status": "completed",
                "started_at": started_at,
                "completed_at": finished_at,
                "failed_at": None,
                "tabs_total": tabs_processed,
                "tabs_processed": tabs_processed,
                "items_total": items_processed,
                "items_processed": items_processed,
                "error_message": "",
                "published_at": finished_at,
            }
        )
    )
    return scan_id
