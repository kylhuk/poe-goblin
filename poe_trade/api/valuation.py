from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from poe_trade.db import ClickHouseClient
from poe_trade.db.clickhouse import ClickHouseClientError
from poe_trade.ml import workflows as ml_workflows
from poe_trade.ml.v3.sql import TRAINING_SOURCE_TABLE, _normalized_currency_sql
from poe_trade.stash_scan import (
    _DEFAULT_DIVINE_TO_CHAOS_RATE,
    _display_price_from_chaos,
    _price_currency_is_computable,
    price_band_for_delta_pct,
    price_evaluation_for_band,
)


class ValuationBackendUnavailable(RuntimeError):
    pass


_PRICE_NOTE_PATTERN = re.compile(
    r"^~(?:b/o|price)\s+([0-9]+(?:\.[0-9]+)?)\s+(.+)$",
    re.IGNORECASE,
)


def safe_json_rows(client: ClickHouseClient, query: str) -> list[dict[str, Any]]:
    try:
        payload = client.execute(query).strip()
    except ClickHouseClientError as exc:
        raise ValuationBackendUnavailable("valuation backend unavailable") from exc
    if not payload:
        return []
    try:
        return [json.loads(line) for line in payload.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise ValuationBackendUnavailable("valuation backend unavailable") from exc


def price_check_comparables(
    client: ClickHouseClient,
    *,
    league: str,
    item_text: str,
) -> list[dict[str, Any]]:
    try:
        parsed = ml_workflows._parse_clipboard_item(item_text)
    except ValueError:
        return []
    base_type = str(parsed.get("base_type") or "").strip()
    if not base_type:
        return []
    clauses = [
        f"league = {_quote_sql_string(league)}",
        "target_price_chaos IS NOT NULL",
        "target_price_chaos > 0",
        f"base_type = {_quote_sql_string(base_type)}",
    ]
    rarity = str(parsed.get("rarity") or "").strip()
    if rarity:
        clauses.append(f"ifNull(rarity, '') = {_quote_sql_string(rarity)}")
    item_name = str(parsed.get("item_name") or "").strip()
    if rarity == "Unique" and item_name:
        clauses.append(f"nullIf(item_name, '') = {_quote_sql_string(item_name)}")
    label_expr = _search_item_label_sql()
    rows = safe_json_rows(
        client,
        " ".join(
            [
                "WITH base AS (",
                "SELECT",
                "as_of_ts,",
                "league,",
                "base_type,",
                "item_name,",
                "target_price_chaos,",
                "target_price_divine",
                f"FROM {TRAINING_SOURCE_TABLE}",
                "WHERE " + " AND ".join(clauses),
                "), priced AS (",
                "SELECT",
                "base.* ,",
                "if(base.target_price_chaos IS NOT NULL, base.target_price_chaos, if(base.target_price_divine IS NULL OR fx_divine.chaos_equivalent <= 0, NULL, base.target_price_divine * fx_divine.chaos_equivalent)) AS normalized_price_chaos",
                "FROM base",
                "LEFT JOIN poe_trade.ml_fx_hour_latest_v2 AS fx_divine",
                "ON fx_divine.league = base.league",
                f"AND {_normalized_currency_sql('fx_divine.currency')} = 'divine'",
                "AND fx_divine.hour_ts = toStartOfHour(base.as_of_ts)",
                ")",
                "SELECT",
                f"{label_expr} AS item_name,",
                "league,",
                "normalized_price_chaos AS listed_price,",
                "as_of_ts AS added_on",
                "FROM priced",
                "WHERE normalized_price_chaos IS NOT NULL",
                "AND normalized_price_chaos > 0",
                "ORDER BY as_of_ts DESC",
                "LIMIT 8 FORMAT JSONEachRow",
            ]
        ),
    )
    return [
        {
            "name": str(row.get("item_name") or base_type),
            "price": _coerce_float(row.get("listed_price")) or 0.0,
            "currency": "chaos",
            "league": str(row.get("league") or league),
            "addedOn": _as_iso_utc(row.get("added_on")),
        }
        for row in rows
    ]


def build_stash_scan_valuations_payload(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    scan_id: str,
    item_id: str | None,
    structured_mode: bool,
    min_threshold: float,
    max_threshold: float,
    max_age_days: int,
) -> dict[str, Any]:
    rows = _fetch_stash_valuation_rows(
        client,
        account_name=account_name,
        league=league,
        realm=realm,
        scan_id=scan_id,
        item_id=None if structured_mode else item_id,
    )
    if item_id and not structured_mode and not rows:
        raise LookupError("item not found")

    items = [
        _build_stash_item_valuation(
            client,
            row,
            league=league,
            min_threshold=min_threshold,
            max_threshold=max_threshold,
            max_age_days=max_age_days,
        )
        for row in rows
    ]
    selected = items[0] if items and not structured_mode else None
    payload: dict[str, Any] = {
        "structuredMode": structured_mode,
        "scanId": scan_id,
        "stashId": scan_id,
        "itemId": selected.get("itemId") if selected else item_id,
        "scanDatetime": selected.get("scanDatetime") if selected else None,
        "chaosMedian": selected.get("chaosMedian") if selected else None,
        "daySeries": selected.get("daySeries") if selected else [],
        "items": items,
    }
    if selected:
        payload.update(
            {
                "listedPrice": selected.get("listedPrice"),
                "listedCurrency": selected.get("listedCurrency"),
                "listedPriceChaos": selected.get("listedPriceChaos"),
                "estimatedPrice": selected.get("estimatedPrice"),
                "estimatedPriceChaos": selected.get("estimatedPriceChaos"),
                "priceDeltaChaos": selected.get("priceDeltaChaos"),
                "priceDeltaPercent": selected.get("priceDeltaPercent"),
                "priceBand": selected.get("priceBand"),
                "priceEvaluation": selected.get("priceEvaluation"),
                "priceBandVersion": selected.get("priceBandVersion"),
                "priceRecommendationEligible": selected.get(
                    "priceRecommendationEligible"
                ),
                "confidence": selected.get("confidence"),
                "estimateTrust": selected.get("estimateTrust"),
                "estimateWarning": selected.get("estimateWarning"),
                "fallbackReason": selected.get("fallbackReason"),
            }
        )
    if selected and "affixFallbackMedians" in selected:
        payload["affixFallbackMedians"] = selected["affixFallbackMedians"]
    return payload


def normalize_chaos_price(
    value: Any,
    *,
    currency: str = "chaos",
    fx_chaos_per_divine: Any | None = None,
) -> float | None:
    amount = _coerce_float(value)
    if amount is None:
        return None
    normalized = _normalized_currency_label(currency)
    if normalized in {"chaos", "chaos orb", "chaos orbs", "c", ""}:
        return amount
    if normalized in {"divine", "div", "divines", "divine orb", "divine orbs"}:
        rate = _coerce_float(fx_chaos_per_divine)
        if rate is None or rate <= 0:
            rate = _DEFAULT_DIVINE_TO_CHAOS_RATE
        return amount * rate
    return None


def median_chaos_price(rows: Sequence[Mapping[str, Any]]) -> float | None:
    values: list[float] = []
    for row in rows:
        value = normalize_chaos_price(
            row.get("normalized_price_chaos")
            or row.get("target_price_chaos")
            or row.get("listed_price")
            or row.get("price"),
            currency=str(row.get("currency") or "chaos"),
            fx_chaos_per_divine=row.get("fx_chaos_per_divine"),
        )
        if value is not None:
            values.append(value)
    if not values:
        return None
    return float(median(values))


def day_series_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    days: int = 10,
) -> list[dict[str, Any]]:
    normalized_days = max(1, int(days))
    if rows:
        anchor = max(
            (
                parsed
                for parsed in (
                    _parse_datetime(row.get("as_of_ts") or row.get("priced_at"))
                    for row in rows
                )
                if parsed is not None
            ),
            default=datetime.now(timezone.utc),
        )
    else:
        anchor = datetime.now(timezone.utc)
    anchor_day = anchor.date()
    buckets: dict[str, list[float]] = {}
    for row in rows:
        parsed = _parse_datetime(row.get("as_of_ts") or row.get("priced_at"))
        if parsed is None:
            continue
        value = normalize_chaos_price(
            row.get("normalized_price_chaos")
            or row.get("target_price_chaos")
            or row.get("listed_price")
            or row.get("price"),
            currency=str(row.get("currency") or "chaos"),
            fx_chaos_per_divine=row.get("fx_chaos_per_divine"),
        )
        if value is None:
            continue
        day_key = parsed.date().isoformat()
        buckets.setdefault(day_key, []).append(value)

    series: list[dict[str, Any]] = []
    for offset in range(normalized_days - 1, -1, -1):
        day = anchor_day - timedelta(days=offset)
        values = buckets.get(day.isoformat(), [])
        series.append(
            {
                "date": day.isoformat(),
                "chaosMedian": float(median(values)) if values else None,
            }
        )
    return series


def build_comparable_query(
    *,
    league: str,
    base_type: str,
    affixes: Sequence[str],
    min_threshold: float,
    max_threshold: float,
    max_age_days: int,
    limit: int | None = None,
) -> str:
    clauses = [
        f"league = {_quote_sql_string(league)}",
        f"base_type = {_quote_sql_string(base_type)}",
        "target_price_chaos IS NOT NULL",
        f"target_price_chaos >= {_float_sql(min_threshold)}",
        f"target_price_chaos <= {_float_sql(max_threshold)}",
        f"as_of_ts >= now() - INTERVAL {max(1, int(max_age_days))} DAY",
    ]
    for affix in affixes:
        clauses.append(
            "positionCaseInsensitiveUTF8("
            f"ifNull(mod_features_json, ''), {_quote_sql_string(affix)}"
            ") > 0"
        )
    query = " ".join(
        [
            "WITH base AS (",
            "SELECT as_of_ts, league, base_type, item_name, target_price_chaos, target_price_divine",
            f"FROM {TRAINING_SOURCE_TABLE}",
            "WHERE",
            " AND ".join(clauses),
            "), priced AS (",
            "SELECT",
            "base.* ,",
            "if(base.target_price_chaos IS NOT NULL, base.target_price_chaos, if(base.target_price_divine IS NULL OR fx_divine.chaos_equivalent <= 0, NULL, base.target_price_divine * fx_divine.chaos_equivalent)) AS normalized_price_chaos",
            "FROM base",
            "LEFT JOIN poe_trade.ml_fx_hour_latest_v2 AS fx_divine",
            "ON fx_divine.league = base.league",
            f"AND {_normalized_currency_sql('fx_divine.currency')} = 'divine'",
            "AND fx_divine.hour_ts = toStartOfHour(base.as_of_ts)",
            ")",
            "SELECT as_of_ts, normalized_price_chaos, target_price_chaos, target_price_divine",
            "FROM priced",
            "WHERE",
            "normalized_price_chaos IS NOT NULL",
            "AND normalized_price_chaos > 0",
            "ORDER BY as_of_ts DESC",
        ]
    )
    if limit is not None:
        query += f" LIMIT {max(1, int(limit))}"
    return query + " FORMAT JSONEachRow"


def build_fallback_comparable_queries(
    *,
    league: str,
    base_type: str,
    affixes: Sequence[str],
    min_threshold: float,
    max_threshold: float,
    max_age_days: int,
    limit: int | None = None,
) -> list[tuple[str, str]]:
    return [
        (
            affix,
            build_comparable_query(
                league=league,
                base_type=base_type,
                affixes=[affix],
                min_threshold=min_threshold,
                max_threshold=max_threshold,
                max_age_days=max_age_days,
                limit=limit,
            ),
        )
        for affix in affixes
    ]


def pricing_outlier_row_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    p10 = _coerce_float(row.get("p10")) or 0.0
    median_value = _coerce_float(row.get("median")) or 0.0
    profit = max(0.0, median_value - p10)
    return {
        "itemName": str(row.get("item_name") or ""),
        "affixAnalyzed": str(row.get("affix_analyzed") or ""),
        "p10": p10,
        "median": median_value,
        "p90": _coerce_float(row.get("p90")) or 0.0,
        "itemsPerWeek": _coerce_float(row.get("items_per_week")) or 0.0,
        "itemsTotal": _as_int(row.get("items_total")),
        "analysisLevel": str(row.get("analysis_level") or "item"),
        "entryPrice": p10,
        "expectedProfit": profit,
        "roi": profit / p10 if p10 else 0.0,
        "underpricedRate": _coerce_float(
            row.get("underpriced_rate") or row.get("underpricedRate")
        )
        or 0.0,
    }


def pricing_outlier_weekly_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "weekStart": _as_iso_utc(row.get("week_start")),
        "tooCheapCount": _as_int(row.get("too_cheap_count")),
    }


def extract_explicit_affixes(item: Mapping[str, Any]) -> list[str]:
    values = item.get("explicitMods")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _fetch_stash_valuation_rows(
    client: ClickHouseClient,
    *,
    account_name: str,
    league: str,
    realm: str,
    scan_id: str,
    item_id: str | None,
) -> list[dict[str, Any]]:
    clauses = [
        f"account_name = {_quote_sql_string(account_name)}",
        f"league = {_quote_sql_string(league)}",
        f"realm = {_quote_sql_string(realm)}",
        f"scan_id = {_quote_sql_string(scan_id)}",
    ]
    if item_id:
        clauses.append(f"item_id = {_quote_sql_string(item_id)}")
    query = " ".join(
        [
            "SELECT",
            "scan_id, account_name, league, realm, tab_id, tab_index, tab_name, tab_type,",
            "lineage_key, item_id, item_name, base_type, item_class, rarity, x, y, w, h, listed_price,",
            "listed_currency, listed_price_chaos, estimated_price_chaos, price_p10_chaos, price_p90_chaos,",
            "confidence, estimate_trust, estimate_warning, fallback_reason,",
            "icon_url, priced_at, payload_json",
            "FROM poe_trade.account_stash_scan_items_v2",
            "WHERE",
            " AND ".join(clauses),
            "ORDER BY tab_index ASC, y ASC, x ASC FORMAT JSONEachRow",
        ]
    )
    rows = safe_json_rows(client, query)
    if rows:
        return rows
    legacy_query = " ".join(
        [
            "SELECT",
            "scan_id, account_name, league, realm, tab_id, tab_index, tab_name, tab_type,",
            "lineage_key, item_id, item_name, item_class, rarity, x, y, w, h, listed_price,",
            "currency, predicted_price, confidence, price_p10, price_p90,",
            "estimate_trust, estimate_warning, fallback_reason,",
            "icon_url, priced_at, payload_json",
            "FROM poe_trade.account_stash_item_valuations",
            "WHERE",
            " AND ".join(clauses),
            "ORDER BY tab_index ASC, y ASC, x ASC FORMAT JSONEachRow",
        ]
    )
    return safe_json_rows(client, legacy_query)


def _build_stash_item_valuation(
    client: ClickHouseClient,
    row: Mapping[str, Any],
    *,
    league: str,
    min_threshold: float,
    max_threshold: float,
    max_age_days: int,
) -> dict[str, Any]:
    raw_item = _load_payload_json(row.get("payload_json"))
    parsed_listed = _parse_listed_price(str(raw_item.get("note") or ""))
    listed_price, listed_currency = (
        parsed_listed if parsed_listed is not None else (None, "")
    )
    base_type = str(
        raw_item.get("baseType")
        or raw_item.get("typeLine")
        or raw_item.get("itemTypeLine")
        or row.get("item_name")
        or ""
    ).strip()
    affixes = extract_explicit_affixes(raw_item)
    predicted_currency = str(row.get("currency") or row.get("listed_currency") or listed_currency or "chaos")
    predicted_price = _coerce_float(row.get("estimated_price_chaos"))
    if predicted_price is None:
        predicted_price = _coerce_float(row.get("predicted_price"))
    if predicted_price is None:
        predicted_price = _coerce_float(row.get("estimated_price"))
    listed_price = (
        listed_price if listed_price is not None else _coerce_float(row.get("listed_price"))
    )
    listed_currency = listed_currency or str(row.get("listed_currency") or row.get("currency") or "chaos")
    listed_price_chaos = _coerce_float(row.get("listed_price_chaos"))
    if listed_price_chaos is None and _price_currency_is_computable(listed_currency):
        listed_price_chaos = normalize_chaos_price(
            listed_price,
            currency=listed_currency,
        )
    estimated_price_chaos = _coerce_float(row.get("estimated_price_chaos"))
    if estimated_price_chaos is None and _price_currency_is_computable(predicted_currency):
        estimated_price_chaos = normalize_chaos_price(
            predicted_price,
            currency=predicted_currency,
        )
    if listed_price is None and listed_price_chaos is not None and _price_currency_is_computable(
        listed_currency
    ):
        listed_price = _display_price_from_chaos(listed_price_chaos, listed_currency)
    estimated_price = _display_price_from_chaos(estimated_price_chaos, listed_currency)
    delta_chaos = (
        None
        if listed_price_chaos is None or estimated_price_chaos is None
        else listed_price_chaos - estimated_price_chaos
    )
    delta_percent = (
        None
        if listed_price_chaos is None or estimated_price_chaos in (None, 0)
        else ((listed_price_chaos - estimated_price_chaos) / estimated_price_chaos)
        * 100.0
    )
    price_band = str(row.get("price_band") or "bad")
    if delta_percent is not None and not row.get("price_band"):
        price_band = price_band_for_delta_pct(delta_percent)
    price_recommendation_eligible = price_band != "bad"
    full_query = build_comparable_query(
        league=league,
        base_type=base_type,
        affixes=affixes,
        min_threshold=min_threshold,
        max_threshold=max_threshold,
        max_age_days=max_age_days,
    )
    full_rows = safe_json_rows(client, full_query)
    day_series = day_series_from_rows(full_rows, days=10)
    chaos_median = median_chaos_price(full_rows)
    payload: dict[str, Any] = {
        "stashId": str(row.get("scan_id") or ""),
        "itemId": str(row.get("item_id") or ""),
        "fingerprint": str(
            row.get("lineage_key")
            or row.get("fingerprint")
            or (
                f"item:{row.get('item_id')}"
                if str(row.get("item_id") or "").strip()
                else ""
            )
        ),
        "scanDatetime": _as_iso_utc(row.get("priced_at")),
        "chaosMedian": chaos_median,
        "daySeries": day_series,
        "listedPrice": listed_price,
        "listedCurrency": listed_currency,
        "listedPriceChaos": listed_price_chaos,
        "estimatedPrice": estimated_price,
        "estimatedPriceChaos": estimated_price_chaos,
        "priceDeltaChaos": delta_chaos,
        "priceDeltaPercent": delta_percent,
        "priceBand": price_band,
        "priceEvaluation": price_evaluation_for_band(price_band),
        "priceBandVersion": int(row.get("price_band_version") or 1),
        "priceRecommendationEligible": price_recommendation_eligible,
        "confidence": _coerce_float(row.get("confidence")) or 0.0,
        "estimateTrust": str(row.get("estimate_trust") or "normal"),
        "estimateWarning": str(row.get("estimate_warning") or ""),
        "fallbackReason": str(row.get("fallback_reason") or ""),
    }
    if chaos_median is None and affixes:
        fallback_medians: list[dict[str, Any]] = []
        for affix, query in build_fallback_comparable_queries(
            league=league,
            base_type=base_type,
            affixes=affixes,
            min_threshold=min_threshold,
            max_threshold=max_threshold,
            max_age_days=max_age_days,
        ):
            rows = safe_json_rows(client, query)
            fallback_median = median_chaos_price(rows)
            if fallback_median is not None:
                fallback_medians.append(
                    {
                        "affix": affix,
                        "chaosMedian": fallback_median,
                    }
                )
        payload["affixFallbackMedians"] = fallback_medians
    return payload


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


def _parse_listed_price(note: str) -> tuple[float, str] | None:
    match = _PRICE_NOTE_PATTERN.match(note.strip())
    if match is None:
        return None
    return float(match.group(1)), " ".join(match.group(2).split()).lower()


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


def _quote_sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _float_sql(value: float) -> str:
    return format(float(value), ".15g")


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_iso_utc(value: Any) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _search_item_label_sql(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return (
        "if(length(trimBoth("
        + prefix
        + "item_name)) > 0, "
        + prefix
        + "item_name, "
        + prefix
        + "base_type)"
    )
