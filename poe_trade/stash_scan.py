from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Literal

from poe_trade.db import ClickHouseClient
from poe_trade.db.clickhouse import ClickHouseClientError


class StashScanBackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class StashPrediction:
    predicted_price: float
    currency: str
    confidence: float
    price_p10: float | None
    price_p90: float | None
    price_recommendation_eligible: bool
    estimate_trust: str
    estimate_warning: str
    fallback_reason: str


PriceBand = Literal["good", "mediocre", "bad"]

_DEFAULT_DIVINE_TO_CHAOS_RATE = 200.0
_PRICE_BAND_VERSION = 1
_PRICE_BAND_GOOD_THRESHOLD = 0.10
_PRICE_BAND_MEDIOCRE_THRESHOLD = 0.25
_HISTORY_RETENTION_DAYS = 90
_PRICE_NOTE_PATTERN = re.compile(
    r"^~(?:b/o|price)\s+([0-9]+(?:\.[0-9]+)?)\s+(.+)$",
    re.IGNORECASE,
)


def content_signature_for_item(item: dict[str, Any]) -> str:
    stable = {
        "name": str(item.get("name") or "").strip(),
        "typeLine": str(item.get("typeLine") or item.get("baseType") or "").strip(),
        "rarity": item.get("frameType"),
        "itemClass": str(item.get("itemClass") or "").strip(),
        "mods": _normalized_mod_lines(item),
        "icon": str(item.get("icon") or "").strip(),
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def lineage_key_for_item(item: dict[str, Any]) -> str:
    item_id = str(item.get("id") or "").strip()
    if item_id:
        return f"item:{item_id}"
    return f"sig:{content_signature_for_item(item)}"


def lineage_key_from_previous_scan(
    *,
    signature: str,
    prior_signature_matches: dict[str, str],
    prior_position_matches: dict[str, str],
    position_key: str,
) -> str:
    if signature in prior_signature_matches:
        return prior_signature_matches[signature]
    if position_key in prior_position_matches:
        return prior_position_matches[position_key]
    return f"sig:{signature}"


def serialize_stash_item_to_clipboard(item: dict[str, Any]) -> str:
    lines = [
        f"Rarity: {_rarity_label(item.get('frameType'))}",
        str(item.get("name") or "").strip(),
        str(
            item.get("typeLine")
            or item.get("baseType")
            or item.get("name")
            or "Unknown"
        ).strip(),
        "--------",
    ]
    for entry in _normalized_mod_lines(item):
        lines.append(entry)
    return "\n".join(line for line in lines if line)


def normalize_stash_prediction(payload: dict[str, Any]) -> StashPrediction:
    interval_obj = payload.get("interval")
    interval = interval_obj if isinstance(interval_obj, dict) else {}
    return StashPrediction(
        predicted_price=float(
            payload.get("predictedValue") or payload.get("price_p50") or 0.0
        ),
        currency=str(payload.get("currency") or "chaos"),
        confidence=float(
            payload.get("confidence") or payload.get("confidence_percent") or 0.0
        ),
        price_p10=_opt_float(interval.get("p10") or payload.get("price_p10")),
        price_p90=_opt_float(interval.get("p90") or payload.get("price_p90")),
        price_recommendation_eligible=bool(
            payload.get("priceRecommendationEligible")
            if "priceRecommendationEligible" in payload
            else payload.get("price_recommendation_eligible", False)
        ),
        estimate_trust=str(
            payload.get("estimateTrust") or payload.get("estimate_trust") or "normal"
        ),
        estimate_warning=str(
            payload.get("estimateWarning") or payload.get("estimate_warning") or ""
        ),
        fallback_reason=str(
            payload.get("fallbackReason") or payload.get("fallback_reason") or ""
        ),
    )


def normalize_chaos_price(
    value: Any,
    *,
    currency: str = "chaos",
    fx_chaos_per_divine: Any | None = None,
) -> float | None:
    amount = _opt_float(value)
    if amount is None:
        return None
    normalized = _normalized_currency_label(currency)
    if normalized in {"", "chaos", "chaos orb", "chaos orbs", "c"}:
        return amount
    if normalized in {"div", "divine", "divines", "divine orb", "divine orbs"}:
        rate = _opt_float(fx_chaos_per_divine)
        if rate is None or rate <= 0:
            rate = _DEFAULT_DIVINE_TO_CHAOS_RATE
        return amount * rate
    return None


def _price_currency_is_computable(currency: Any) -> bool:
    return _normalized_currency_label(currency) in {"chaos", "divine"}


def price_band_for_delta_pct(delta_pct: float | None) -> PriceBand:
    if delta_pct is None:
        return "bad"
    abs_delta = abs(delta_pct)
    if abs_delta <= _PRICE_BAND_GOOD_THRESHOLD * 100.0:
        return "good"
    if abs_delta <= _PRICE_BAND_MEDIOCRE_THRESHOLD * 100.0:
        return "mediocre"
    return "bad"


def price_evaluation_for_band(price_band: PriceBand | None) -> str:
    mapping = {
        "good": "well_priced",
        "mediocre": "could_be_better",
        "bad": "mispriced",
    }
    return mapping.get(price_band or "bad", "mispriced")


def valuation_refresh_status_payload(
    *,
    status: str,
    active_scan_id: str | None,
    source_scan_id: str | None,
    published_scan_id: str | None,
    started_at: str | None,
    updated_at: str | None,
    published_at: str | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "scanKind": "valuation_refresh",
        "sourceScanId": source_scan_id,
        "activeScanId": active_scan_id,
        "publishedScanId": published_scan_id,
        "startedAt": started_at,
        "updatedAt": updated_at,
        "publishedAt": published_at,
        "progress": {
            "tabsTotal": 0,
            "tabsProcessed": 0,
            "itemsTotal": 0,
            "itemsProcessed": 0,
        },
        "error": error,
    }


def _display_price_from_chaos(
    chaos_value: Any,
    currency: str,
    *,
    fx_chaos_per_divine: Any | None = None,
) -> float | None:
    normalized = _normalized_currency_label(currency)
    if normalized == "chaos":
        return _opt_float(chaos_value)
    if normalized == "divine":
        rate = _opt_float(fx_chaos_per_divine)
        if rate is None or rate <= 0:
            rate = _DEFAULT_DIVINE_TO_CHAOS_RATE
        chaos = _opt_float(chaos_value)
        if chaos is None:
            return None
        return chaos / rate
    return None


def _display_price_for_row(
    row: dict[str, Any],
    *,
    chaos_value: Any | None = None,
) -> float | None:
    listed_currency = _listed_currency_for_row(row)
    chaos = chaos_value if chaos_value is not None else row.get("estimated_price_chaos")
    return _display_price_from_chaos(chaos, listed_currency)


def _fetch_latest_scan_run_row(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    scan_id: str | None = None,
    scan_kind: str | None = None,
    source_scan_id: str | None = None,
) -> dict[str, Any] | None:
    scan_id_filter = (
        f"AND scan_id = '{_escape_sql_literal(scan_id)}' " if scan_id else ""
    )
    scan_kind_filter = (
        f"AND scan_kind = '{_escape_sql_literal(scan_kind)}' " if scan_kind else ""
    )
    source_scan_id_filter = (
        f"AND source_scan_id = '{_escape_sql_literal(source_scan_id)}' "
        if source_scan_id
        else ""
    )
    query = (
        "SELECT scan_id, source_scan_id, status, started_at, updated_at, published_at, tabs_total, tabs_processed, items_total, items_processed, error_message "
        "FROM poe_trade.account_stash_scan_runs "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        f"{scan_kind_filter}"
        f"{source_scan_id_filter}"
        f"{scan_id_filter}"
        "ORDER BY updated_at DESC, published_at DESC, completed_at DESC, failed_at DESC LIMIT 1 FORMAT JSONEachRow"
    )
    try:
        payload = client.execute(query).strip()
    except ClickHouseClientError as exc:
        raise StashScanBackendUnavailable("scan run backend unavailable") from exc
    if not payload:
        return None
    row = json.loads(payload.splitlines()[0])
    return {
        "scanId": str(row.get("scan_id") or ""),
        "sourceScanId": str(row.get("source_scan_id") or "") or None,
        "status": str(row.get("status") or "idle"),
        "startedAt": str(row.get("started_at") or "") or None,
        "updatedAt": str(row.get("updated_at") or "") or None,
        "publishedAt": str(row.get("published_at") or "") or None,
        "progress": {
            "tabsTotal": int(row.get("tabs_total") or 0),
            "tabsProcessed": int(row.get("tabs_processed") or 0),
            "itemsTotal": int(row.get("items_total") or 0),
            "itemsProcessed": int(row.get("items_processed") or 0),
        },
        "error": str(row.get("error_message") or "") or None,
    }


def fetch_published_scan_id(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
) -> str | None:
    query = (
        "SELECT argMax(scan_id, published_at) AS scan_id "
        "FROM poe_trade.account_stash_published_scans "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        "FORMAT JSONEachRow"
    )
    try:
        payload = client.execute(query).strip()
    except ClickHouseClientError as exc:
        raise StashScanBackendUnavailable("published scan backend unavailable") from exc
    if not payload:
        return None
    row = json.loads(payload.splitlines()[0])
    scan_id = str(row.get("scan_id") or "").strip()
    return scan_id or None


def fetch_active_scan(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    stale_timeout_seconds: int | None = None,
) -> dict[str, Any] | None:
    active_scan = _fetch_active_scan_row(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_kind="stash_scan",
    )
    if active_scan is None:
        return None
    if not active_scan["isActive"]:
        return active_scan

    timeout_seconds = int(stale_timeout_seconds or 0)
    if timeout_seconds <= 0:
        return active_scan

    latest_run = fetch_latest_scan_run(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_id=str(active_scan.get("scanId") or ""),
    )
    if not _active_scan_is_stale(active_scan, latest_run, timeout_seconds):
        return active_scan

    return _reconcile_stale_active_scan(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        active_scan=active_scan,
        latest_run=latest_run,
    )


def fetch_active_valuation_refresh(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    published_scan_id: str,
    stale_timeout_seconds: int | None = None,
) -> dict[str, Any] | None:
    active_refresh = _fetch_active_scan_row(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_kind="valuation_refresh",
        source_scan_id=published_scan_id,
    )
    if active_refresh is None:
        return None
    if not active_refresh["isActive"]:
        return active_refresh

    timeout_seconds = int(stale_timeout_seconds or 0)
    if timeout_seconds <= 0:
        return active_refresh

    latest_run = fetch_latest_valuation_refresh_run(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        published_scan_id=published_scan_id,
        scan_id=str(active_refresh.get("scanId") or ""),
    )
    if not _active_scan_is_stale(active_refresh, latest_run, timeout_seconds):
        return active_refresh

    return _reconcile_stale_active_scan(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        active_scan=active_refresh,
        latest_run=latest_run,
        scan_kind="valuation_refresh",
        source_scan_id=published_scan_id,
    )


def _fetch_active_scan_row(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    scan_kind: str | None = None,
    source_scan_id: str | None = None,
) -> dict[str, Any] | None:
    scan_kind_filter = (
        f"AND scan_kind = '{_escape_sql_literal(scan_kind)}' " if scan_kind else ""
    )
    source_scan_id_filter = (
        f"AND source_scan_id = '{_escape_sql_literal(source_scan_id)}' "
        if source_scan_id
        else ""
    )
    query = (
        "SELECT scan_id, is_active, started_at, updated_at "
        "FROM poe_trade.account_stash_active_scans "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        f"{scan_kind_filter}"
        f"{source_scan_id_filter}"
        "ORDER BY updated_at DESC LIMIT 1 FORMAT JSONEachRow"
    )
    try:
        payload = client.execute(query).strip()
    except ClickHouseClientError as exc:
        raise StashScanBackendUnavailable("active scan backend unavailable") from exc
    if not payload:
        return None
    row = json.loads(payload.splitlines()[0])
    return {
        "scanId": str(row.get("scan_id") or ""),
        "isActive": bool(row.get("is_active") or 0),
        "startedAt": str(row.get("started_at") or ""),
        "updatedAt": str(row.get("updated_at") or ""),
    }


def fetch_latest_scan_run(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    scan_id: str | None = None,
) -> dict[str, Any] | None:
    return _fetch_latest_scan_run_row(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_id=scan_id,
        scan_kind="stash_scan",
    )


def fetch_latest_valuation_refresh_run(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    published_scan_id: str,
    scan_id: str | None = None,
) -> dict[str, Any] | None:
    return _fetch_latest_scan_run_row(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_id=scan_id,
        scan_kind="valuation_refresh",
        source_scan_id=published_scan_id,
    )


def fetch_latest_published_valuation_refresh_run(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    published_scan_id: str,
) -> dict[str, Any] | None:
    return _fetch_latest_scan_run_row(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_id=published_scan_id,
        scan_kind="valuation_refresh",
    )


def fetch_valuation_refresh_status_payload(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    published_scan_id: str | None,
    stale_timeout_seconds: int = 0,
) -> dict[str, Any]:
    if not published_scan_id:
        return valuation_refresh_status_payload(
            status="idle",
            active_scan_id=None,
            source_scan_id=None,
            published_scan_id=None,
            started_at=None,
            updated_at=None,
            published_at=None,
            error=None,
        )
    active = fetch_active_valuation_refresh(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        published_scan_id=published_scan_id,
        stale_timeout_seconds=stale_timeout_seconds,
    )
    latest = fetch_latest_valuation_refresh_run(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        published_scan_id=published_scan_id,
        scan_id=str((active or {}).get("scanId") or ""),
    )

    if latest is not None:
        status = str(latest.get("status") or "idle")
        active_scan_id = (
            latest.get("scanId")
            if (active and active.get("isActive")) or status in {"running", "publishing"}
            else None
        )
        if status == "published":
            active_scan_id = None
        payload = valuation_refresh_status_payload(
            status=status,
            active_scan_id=active_scan_id,
            source_scan_id=str(latest.get("sourceScanId") or published_scan_id or "")
            or None,
            published_scan_id=published_scan_id,
            started_at=latest.get("startedAt"),
            updated_at=latest.get("updatedAt"),
            published_at=latest.get("publishedAt"),
            error=latest.get("error"),
        )
        payload["progress"] = latest.get("progress") or payload["progress"]
        return payload

    if active is not None and active.get("isActive"):
        return valuation_refresh_status_payload(
            status="running",
            active_scan_id=active.get("scanId"),
            source_scan_id=published_scan_id,
            published_scan_id=published_scan_id,
            started_at=active.get("startedAt"),
            updated_at=active.get("updatedAt"),
            published_at=None,
            error=None,
        )

    published = fetch_latest_published_valuation_refresh_run(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        published_scan_id=published_scan_id,
    )
    if published is not None and str(published.get("status") or "").strip().lower() == "published":
        payload = valuation_refresh_status_payload(
            status="published",
            active_scan_id=None,
            source_scan_id=str(published.get("sourceScanId") or "") or None,
            published_scan_id=published_scan_id,
            started_at=published.get("startedAt"),
            updated_at=published.get("updatedAt"),
            published_at=published.get("publishedAt"),
            error=published.get("error"),
        )
        payload["progress"] = published.get("progress") or payload["progress"]
        return payload

    return valuation_refresh_status_payload(
        status="idle",
        active_scan_id=None,
        source_scan_id=published_scan_id,
        published_scan_id=published_scan_id,
        started_at=None,
        updated_at=None,
        published_at=None,
        error=None,
    )


def _active_scan_is_stale(
    active_scan: dict[str, Any],
    latest_run: dict[str, Any] | None,
    stale_timeout_seconds: int,
) -> bool:
    if stale_timeout_seconds <= 0:
        return False
    candidate_timestamp = _parse_iso_datetime(
        str((latest_run or {}).get("updatedAt") or active_scan.get("updatedAt") or "")
    )
    if candidate_timestamp is None:
        return False
    if candidate_timestamp.tzinfo is None:
        candidate_timestamp = candidate_timestamp.replace(tzinfo=timezone.utc)
    return _utcnow() - candidate_timestamp > timedelta(seconds=stale_timeout_seconds)


def _reconcile_stale_active_scan(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    active_scan: dict[str, Any],
    latest_run: dict[str, Any] | None,
    scan_kind: str = "stash_scan",
    source_scan_id: str = "",
) -> dict[str, Any]:
    reconciled_at = _utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    scan_id = str(active_scan.get("scanId") or "")
    started_at = str(
        (latest_run or {}).get("startedAt")
        or active_scan.get("startedAt")
        or reconciled_at
    )

    _write_active_scan_row(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_id=scan_id,
        is_active=False,
        started_at=started_at,
        updated_at=reconciled_at,
        scan_kind=scan_kind,
        source_scan_id=source_scan_id,
    )

    latest_status = str((latest_run or {}).get("status") or "")
    if latest_run is None or latest_status not in {"failed", "published"}:
        progress = (
            (latest_run or {}).get("progress") if isinstance(latest_run, dict) else {}
        )
        progress = progress if isinstance(progress, dict) else {}
        _write_scan_run_row(
            client,
            scan_id=scan_id,
            status="failed",
            account_name=account_name,
            league=league,
            realm=realm,
            started_at=started_at,
            updated_at=reconciled_at,
            completed_at=None,
            published_at=None,
            failed_at=reconciled_at,
            tabs_total=int(progress.get("tabsTotal") or 0),
            tabs_processed=int(progress.get("tabsProcessed") or 0),
            items_total=int(progress.get("itemsTotal") or 0),
            items_processed=int(progress.get("itemsProcessed") or 0),
            error_message="stale active scan timed out",
            scan_kind=scan_kind,
            source_scan_id=source_scan_id,
        )

    return {
        **active_scan,
        "isActive": False,
        "updatedAt": reconciled_at,
    }


def fetch_published_tabs(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    stale_timeout_seconds: int = 0,
) -> dict[str, Any]:
    _ = fetch_active_scan(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        stale_timeout_seconds=stale_timeout_seconds,
    )
    scan_id = fetch_published_scan_id(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
    )
    latest_run = fetch_latest_scan_run(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
    )
    if not scan_id:
        return {
            "scanId": None,
            "publishedAt": None,
            "isStale": False,
            "scanStatus": latest_run
            if latest_run and latest_run.get("status") in {"running", "publishing"}
            else None,
            "stashTabs": [],
        }

    published_at = _fetch_published_at(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
    )
    tabs_query = (
        "SELECT tab_id, tab_index, tab_name, tab_type "
        "FROM poe_trade.account_stash_scan_tabs "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        f"AND scan_id = '{_escape_sql_literal(scan_id)}' "
        "ORDER BY tab_index ASC FORMAT JSONEachRow"
    )
    items_query = (
        "SELECT tab_id, tab_index, lineage_key, item_id, item_name, base_type, item_class, rarity, x, y, w, h, listed_price, listed_currency, listed_price_chaos, estimated_price_chaos, price_p10_chaos, price_p90_chaos, price_delta_chaos, price_delta_pct, price_band, price_evaluation, price_band_version, confidence, estimate_trust, estimate_warning, fallback_reason, icon_url, priced_at "
        "FROM poe_trade.v_account_stash_latest_scan_items "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        f"AND scan_id = '{_escape_sql_literal(scan_id)}' "
        "ORDER BY tab_index ASC, y ASC, x ASC FORMAT JSONEachRow"
    )
    legacy_items_query = (
        "SELECT tab_id, tab_index, lineage_key, item_id, item_name, item_class, rarity, x, y, w, h, listed_price, currency, predicted_price, confidence, price_p10, price_p90, icon_url, priced_at, payload_json "
        "FROM poe_trade.account_stash_item_valuations "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        f"AND scan_id = '{_escape_sql_literal(scan_id)}' "
        "ORDER BY tab_index ASC, y ASC, x ASC FORMAT JSONEachRow"
    )
    try:
        tabs_payload = client.execute(tabs_query).strip()
        items_payload = client.execute(items_query).strip()
        if not items_payload:
            items_payload = client.execute(legacy_items_query).strip()
    except ClickHouseClientError as exc:
        raise StashScanBackendUnavailable(
            "published stash backend unavailable"
        ) from exc

    tabs: list[dict[str, Any]] = []
    tab_map: dict[str, dict[str, Any]] = {}
    for line in tabs_payload.splitlines() if tabs_payload else []:
        row = json.loads(line)
        tab_id = str(row.get("tab_id") or "")
        tab_items: list[dict[str, Any]] = []
        tab = {
            "id": tab_id,
            "name": str(row.get("tab_name") or ""),
            "type": _normalize_tab_type(str(row.get("tab_type") or "normal")),
            "items": tab_items,
        }
        tabs.append(tab)
        tab_map[tab_id] = tab

    for line in items_payload.splitlines() if items_payload else []:
        row = json.loads(line)
        tab = tab_map.get(str(row.get("tab_id") or ""))
        if tab is None:
            continue
        items = tab.get("items")
        if isinstance(items, list):
            items.append(_to_api_item(row))

    return {
        "scanId": scan_id,
        "publishedAt": published_at,
        "isStale": False,
        "scanStatus": latest_run
        if latest_run and latest_run.get("status") in {"running", "publishing"}
        else None,
        "stashTabs": tabs,
    }


def fetch_item_history(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    lineage_key: str,
    limit: int | None = None,
) -> dict[str, Any]:
    effective_limit = 50 if limit is None else max(limit, 1)
    query = (
        "SELECT lineage_key, item_id, item_name, base_type, item_class, rarity, icon_url, scan_id, priced_at, "
        "listed_price, listed_currency, listed_price_chaos, estimated_price_chaos, price_p10_chaos, price_p90_chaos, "
        "price_delta_chaos, price_delta_pct, price_band, price_evaluation, price_band_version, confidence, estimate_trust, estimate_warning, fallback_reason "
        "FROM poe_trade.account_stash_item_history_v2 "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        f"AND lineage_key = '{_escape_sql_literal(lineage_key)}' "
        f"AND priced_at >= now() - INTERVAL {_HISTORY_RETENTION_DAYS} DAY "
        f"ORDER BY priced_at DESC LIMIT {effective_limit} FORMAT JSONEachRow"
    )
    legacy_query = (
        "SELECT lineage_key, item_id, item_name, item_class, rarity, icon_url, scan_id, priced_at, "
        "listed_price, currency, predicted_price, price_p10, price_p90, confidence, estimate_trust, estimate_warning, fallback_reason, payload_json "
        "FROM poe_trade.account_stash_item_valuations "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        f"AND lineage_key = '{_escape_sql_literal(lineage_key)}' "
        f"AND priced_at >= now() - INTERVAL {_HISTORY_RETENTION_DAYS} DAY "
        f"ORDER BY priced_at DESC LIMIT {effective_limit} FORMAT JSONEachRow"
    )
    try:
        payload = client.execute(query).strip()
        if not payload:
            payload = client.execute(legacy_query).strip()
    except ClickHouseClientError as exc:
        raise StashScanBackendUnavailable("item history backend unavailable") from exc
    if not payload:
        return {"fingerprint": lineage_key, "item": {}, "history": []}

    rows = [_normalize_history_row(json.loads(line)) for line in payload.splitlines() if line.strip()]
    first = rows[0]
    return {
        "fingerprint": str(first.get("lineage_key") or lineage_key),
        "item": {
            "name": str(first.get("item_name") or "Unknown"),
            "itemClass": str(first.get("item_class") or ""),
            "rarity": str(first.get("rarity") or "normal"),
            "iconUrl": str(first.get("icon_url") or ""),
            "baseType": str(first.get("base_type") or ""),
        },
        "history": [
            {
                "scanId": str(row.get("scan_id") or ""),
                "pricedAt": str(row.get("priced_at") or ""),
                "predictedValue": _display_price_for_row(row),
                "predictedValueChaos": _opt_float(row.get("estimated_price_chaos")),
                "listedPrice": _opt_float(row.get("listed_price")),
                "listedPriceChaos": _opt_float(row.get("listed_price_chaos")),
                "currency": str(row.get("listed_currency") or "chaos"),
                "confidence": float(row.get("confidence") or 0.0),
                "interval": {
                    "p10": _display_price_for_row(
                        row,
                        chaos_value=row.get("price_p10_chaos"),
                    ),
                    "p90": _display_price_for_row(
                        row,
                        chaos_value=row.get("price_p90_chaos"),
                    ),
                },
                "priceDeltaChaos": _opt_float(row.get("price_delta_chaos")),
                "priceDeltaPercent": _opt_float(row.get("price_delta_pct")),
                "priceBand": str(row.get("price_band") or "bad"),
                "priceEvaluation": str(
                    row.get("price_evaluation")
                    or price_evaluation_for_band(str(row.get("price_band") or "bad"))
                ),
                "priceBandVersion": int(row.get("price_band_version") or _PRICE_BAND_VERSION),
                "priceRecommendationEligible": str(row.get("price_band") or "bad")
                != "bad",
                "estimateTrust": str(row.get("estimate_trust") or "normal"),
                "estimateWarning": str(row.get("estimate_warning") or ""),
                "fallbackReason": str(row.get("fallback_reason") or ""),
            }
            for row in rows
        ],
    }


def _fetch_published_at(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
) -> str | None:
    query = (
        "SELECT argMax(published_at, published_at) AS published_at "
        "FROM poe_trade.account_stash_published_scans "
        f"WHERE account_name = '{_escape_sql_literal(account_name)}' "
        f"AND league = '{_escape_sql_literal(league)}' "
        f"AND realm = '{_escape_sql_literal(realm)}' "
        "FORMAT JSONEachRow"
    )
    try:
        payload = client.execute(query).strip()
    except ClickHouseClientError as exc:
        raise StashScanBackendUnavailable("published scan backend unavailable") from exc
    if not payload:
        return None
    row = json.loads(payload.splitlines()[0])
    value = str(row.get("published_at") or "").strip()
    return value or None


def _to_api_item(row: dict[str, Any]) -> dict[str, Any]:
    row = _row_with_legacy_payload_fields(row)
    listed_price = _opt_float(row.get("listed_price"))
    listed_currency = _listed_currency_for_row(row)
    estimated_chaos = _opt_float(row.get("estimated_price_chaos"))
    if estimated_chaos is None and _price_currency_is_computable(
        str(row.get("currency") or listed_currency or "chaos")
    ):
        estimated_chaos = normalize_chaos_price(
            row.get("predicted_price"),
            currency=str(row.get("currency") or listed_currency or "chaos"),
        )
    listed_chaos = _opt_float(row.get("listed_price_chaos"))
    if listed_chaos is None and listed_price is not None and _price_currency_is_computable(
        listed_currency
    ):
        listed_chaos = normalize_chaos_price(listed_price, currency=listed_currency)
    if estimated_chaos is None and _price_currency_is_computable(listed_currency):
        estimated_chaos = _opt_float(row.get("estimated_price"))
    price_p10_chaos = _opt_float(row.get("price_p10_chaos"))
    if price_p10_chaos is None and _price_currency_is_computable(
        str(row.get("currency") or listed_currency or "chaos")
    ):
        price_p10_chaos = normalize_chaos_price(
            row.get("price_p10"),
            currency=str(row.get("currency") or listed_currency or "chaos"),
        )
    price_p90_chaos = _opt_float(row.get("price_p90_chaos"))
    if price_p90_chaos is None and _price_currency_is_computable(
        str(row.get("currency") or listed_currency or "chaos")
    ):
        price_p90_chaos = normalize_chaos_price(
            row.get("price_p90"),
            currency=str(row.get("currency") or listed_currency or "chaos"),
        )
    if listed_price is None and listed_chaos is not None and _price_currency_is_computable(
        listed_currency
    ):
        listed_price = _display_price_from_chaos(listed_chaos, listed_currency)
    estimated = _display_price_from_chaos(estimated_chaos, listed_currency)
    delta = (
        None
        if listed_chaos is None or estimated_chaos is None
        else listed_chaos - estimated_chaos
    )
    delta_percent = (
        None
        if listed_chaos is None or estimated_chaos in (None, 0)
        else ((listed_chaos - estimated_chaos) / estimated_chaos) * 100.0
    )
    price_band = str(row.get("price_band") or "bad")
    if delta_percent is not None and not row.get("price_band"):
        price_band = price_band_for_delta_pct(delta_percent)
    evaluation = price_evaluation_for_band(price_band)
    price_recommendation_eligible = price_band != "bad"
    return {
        "id": str(row.get("item_id") or row.get("lineage_key") or ""),
        "fingerprint": str(row.get("lineage_key") or ""),
        "name": str(row.get("item_name") or "Unknown"),
        "x": int(row.get("x") or 0),
        "y": int(row.get("y") or 0),
        "w": int(row.get("w") or 1),
        "h": int(row.get("h") or 1),
        "itemClass": str(row.get("item_class") or "Unknown"),
        "baseType": str(row.get("base_type") or ""),
        "rarity": str(row.get("rarity") or "normal"),
        "listedPrice": listed_price,
        "estimatedPrice": estimated,
        "estimatedPriceChaos": estimated_chaos,
        "listedPriceChaos": listed_chaos,
        "estimatedPriceConfidence": float(row.get("confidence") or 0.0),
        "priceDeltaChaos": delta,
        "priceDeltaPercent": delta_percent,
        "priceBand": price_band,
        "priceEvaluation": str(row.get("price_evaluation") or evaluation),
        "currency": listed_currency,
        "iconUrl": str(row.get("icon_url") or ""),
        "pricedAt": str(row.get("priced_at") or ""),
        "interval": {
            "p10": _display_price_from_chaos(price_p10_chaos, listed_currency),
            "p90": _display_price_from_chaos(price_p90_chaos, listed_currency),
        },
        "priceBandVersion": int(row.get("price_band_version") or _PRICE_BAND_VERSION),
        "priceRecommendationEligible": price_recommendation_eligible,
        "estimateTrust": str(row.get("estimate_trust") or "normal"),
        "estimateWarning": str(row.get("estimate_warning") or ""),
        "fallbackReason": str(row.get("fallback_reason") or ""),
    }


def _normalize_history_row(row: dict[str, Any]) -> dict[str, Any]:
    row = _row_with_legacy_payload_fields(row)
    listed_price = _opt_float(row.get("listed_price"))
    listed_currency = _listed_currency_for_row(row)
    predicted_currency = str(row.get("currency") or listed_currency or "chaos")
    listed_price_chaos = _opt_float(row.get("listed_price_chaos"))
    if listed_price_chaos is None and listed_price is not None and _price_currency_is_computable(
        listed_currency
    ):
        listed_price_chaos = normalize_chaos_price(
            listed_price,
            currency=listed_currency,
        )
    estimated_price_chaos = _opt_float(row.get("estimated_price_chaos"))
    if estimated_price_chaos is None and _price_currency_is_computable(predicted_currency):
        estimated_price_chaos = normalize_chaos_price(
            row.get("predicted_price"),
            currency=predicted_currency,
        )
    if estimated_price_chaos is None and _price_currency_is_computable(listed_currency):
        estimated_price_chaos = _opt_float(row.get("estimated_price"))
    price_p10_chaos = _opt_float(row.get("price_p10_chaos"))
    if price_p10_chaos is None and _price_currency_is_computable(predicted_currency):
        price_p10_chaos = normalize_chaos_price(
            row.get("price_p10"),
            currency=predicted_currency,
        )
    price_p90_chaos = _opt_float(row.get("price_p90_chaos"))
    if price_p90_chaos is None and _price_currency_is_computable(predicted_currency):
        price_p90_chaos = normalize_chaos_price(
            row.get("price_p90"),
            currency=predicted_currency,
        )
    price_delta_chaos = (
        None
        if listed_price_chaos is None or estimated_price_chaos is None
        else listed_price_chaos - estimated_price_chaos
    )
    price_delta_pct = (
        None
        if listed_price_chaos is None or estimated_price_chaos in (None, 0)
        else ((listed_price_chaos - estimated_price_chaos) / estimated_price_chaos)
        * 100.0
    )
    price_band = str(row.get("price_band") or "bad")
    if price_delta_pct is not None and not row.get("price_band"):
        price_band = price_band_for_delta_pct(price_delta_pct)
    normalized = dict(row)
    normalized["listed_currency"] = listed_currency
    normalized["listed_price_chaos"] = listed_price_chaos
    normalized["estimated_price_chaos"] = estimated_price_chaos
    normalized["price_p10_chaos"] = price_p10_chaos
    normalized["price_p90_chaos"] = price_p90_chaos
    normalized["price_delta_chaos"] = price_delta_chaos
    normalized["price_delta_pct"] = price_delta_pct
    normalized["price_band"] = price_band
    normalized["price_evaluation"] = str(
        row.get("price_evaluation") or price_evaluation_for_band(price_band)
    )
    normalized["price_band_version"] = int(
        row.get("price_band_version") or _PRICE_BAND_VERSION
    )
    normalized["confidence"] = _opt_float(row.get("confidence")) or 0.0
    normalized["estimate_trust"] = str(row.get("estimate_trust") or "normal")
    normalized["estimate_warning"] = str(row.get("estimate_warning") or "")
    normalized["fallback_reason"] = str(row.get("fallback_reason") or "")
    return normalized


def _row_with_legacy_payload_fields(row: dict[str, Any]) -> dict[str, Any]:
    payload = _load_payload_json(row.get("payload_json"))
    if not payload:
        return row
    normalized = dict(row)
    base_type = str(
        normalized.get("base_type")
        or payload.get("baseType")
        or payload.get("typeLine")
        or payload.get("itemTypeLine")
        or normalized.get("item_name")
        or ""
    ).strip()
    if base_type:
        normalized["base_type"] = base_type
    listed_price = _parse_listed_price_from_payload(payload)
    if listed_price is not None:
        normalized["listed_price"] = listed_price[0]
        normalized["listed_currency"] = listed_price[1]
    return normalized


def _listed_currency_for_row(row: Mapping[str, Any]) -> str:
    payload = _load_payload_json(row.get("payload_json"))
    if payload:
        parsed = _parse_listed_price_from_payload(payload)
        if parsed is not None:
            return parsed[1]
    listed_currency = str(row.get("listed_currency") or "").strip().lower()
    if listed_currency:
        return listed_currency
    return str(row.get("currency") or "chaos").strip().lower() or "chaos"


def _load_payload_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_listed_price_from_payload(payload: Mapping[str, Any]) -> tuple[float, str] | None:
    note = str(payload.get("note") or "").strip()
    if not note:
        return None
    match = _PRICE_NOTE_PATTERN.match(note)
    if match is None:
        return None
    return float(match.group(1)), match.group(2).lower()


def _normalized_mod_lines(item: dict[str, Any]) -> list[str]:
    sections = (
        "implicitMods",
        "explicitMods",
        "craftedMods",
        "fracturedMods",
        "enchantMods",
    )
    lines: list[str] = []
    for section in sections:
        values = item.get(section)
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value).strip()
            if text:
                lines.append(text)
    return lines


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rarity_label(frame_type: Any) -> str:
    mapping = {0: "Normal", 1: "Magic", 2: "Rare", 3: "Unique"}
    if isinstance(frame_type, int):
        return mapping.get(frame_type, "Normal")
    return "Normal"


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalized_currency_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = " ".join(text.split())
    if text in {"div", "divine", "divines", "divine orb", "divine orbs"}:
        return "divine"
    if text in {"chaos", "chaos orb", "chaos orbs", "c"}:
        return "chaos"
    if text in {"exalted", "exalted orb", "exalted orbs", "exa", "ex"}:
        return "exalted"
    return text


def _write_scan_run_row(
    client: ClickHouseClient,
    *,
    scan_id: str,
    status: str,
    account_name: str,
    league: str,
    realm: str,
    started_at: str,
    updated_at: str,
    completed_at: str | None,
    published_at: str | None,
    failed_at: str | None,
    tabs_total: int,
    tabs_processed: int,
    items_total: int,
    items_processed: int,
    error_message: str,
    scan_kind: str = "stash_scan",
    source_scan_id: str = "",
) -> None:
    row = {
        "scan_id": scan_id,
        "account_name": account_name,
        "league": league,
        "realm": realm,
        "scan_kind": scan_kind,
        "source_scan_id": source_scan_id,
        "status": status,
        "started_at": started_at,
        "updated_at": updated_at,
        "completed_at": completed_at,
        "published_at": published_at,
        "failed_at": failed_at,
        "tabs_total": tabs_total,
        "tabs_processed": tabs_processed,
        "items_total": items_total,
        "items_processed": items_processed,
        "error_message": error_message,
    }
    query = (
        "INSERT INTO poe_trade.account_stash_scan_runs "
        "(scan_id, account_name, league, realm, scan_kind, source_scan_id, status, started_at, updated_at, completed_at, published_at, failed_at, tabs_total, tabs_processed, items_total, items_processed, error_message)\n"
        "FORMAT JSONEachRow\n"
        f"{json.dumps(row, ensure_ascii=False)}"
    )
    client.execute(query)


def _write_active_scan_row(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    scan_id: str,
    is_active: bool,
    started_at: str,
    updated_at: str,
    scan_kind: str = "stash_scan",
    source_scan_id: str = "",
) -> None:
    row = {
        "account_name": account_name,
        "league": league,
        "realm": realm,
        "scan_id": scan_id,
        "scan_kind": scan_kind,
        "source_scan_id": source_scan_id,
        "is_active": 1 if is_active else 0,
        "started_at": started_at,
        "updated_at": updated_at,
    }
    query = (
        "INSERT INTO poe_trade.account_stash_active_scans "
        "(account_name, league, realm, scan_id, scan_kind, source_scan_id, is_active, started_at, updated_at)\n"
        "FORMAT JSONEachRow\n"
        f"{json.dumps(row, ensure_ascii=False)}"
    )
    client.execute(query)


def _normalize_tab_type(raw: str) -> str:
    normalized = raw.lower().strip()
    mapping = {
        "normal": "normal",
        "normalstash": "normal",
        "premiumstash": "normal",
        "quad": "quad",
        "quadstash": "quad",
        "currency": "currency",
        "currencystash": "currency",
        "map": "map",
        "mapstash": "map",
        "fragment": "fragment",
        "fragmentstash": "fragment",
        "essence": "essence",
        "essencestash": "essence",
        "divination": "divination",
        "divinationcardstash": "divination",
        "unique": "unique",
        "uniquestash": "unique",
        "delve": "delve",
        "delvestash": "delve",
        "blight": "blight",
        "blightstash": "blight",
        "ultimatum": "ultimatum",
        "ultimatumstash": "ultimatum",
        "delirium": "delirium",
        "deliriumstash": "delirium",
        "metamorph": "metamorph",
        "metamorphstash": "metamorph",
        "flask": "flask",
        "flaskstash": "flask",
        "gem": "gem",
        "gemstash": "gem",
    }
    return mapping.get(normalized, "normal")
