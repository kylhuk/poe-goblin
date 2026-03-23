from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from poe_trade.db import ClickHouseClient
from poe_trade.ml import workflows

from .features import build_feature_row
from . import routes
from . import sql
from .sql import TRAINING_TABLE


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _query_rows(client: ClickHouseClient, query: str) -> list[dict[str, Any]]:
    payload = client.execute(query).strip()
    if not payload:
        return []
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


def _route_for_item(parsed: dict[str, Any]) -> str:
    return routes.select_route(parsed)


def _build_target_identity_key(parsed: dict[str, Any]) -> str:
    return "|".join(
        [
            str(parsed.get("category") or "other").strip().lower(),
            str(parsed.get("base_type") or "").strip().lower(),
            str(parsed.get("rarity") or "").strip().lower(),
            str(parsed.get("mod_token_count") or "0"),
            str(parsed.get("ilvl") or "0"),
        ]
    )


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _combine_with_anchor(anchor: float, model_value: float, blend: float) -> float:
    blend_weight = min(1.0, max(0.0, blend))
    return anchor + (model_value - anchor) * blend_weight


def _weighted_quantile(
    values: list[float], weights: list[float], q: float
) -> float | None:
    if not values:
        return None
    paired = sorted(
        ((float(v), max(0.0, float(w))) for v, w in zip(values, weights, strict=True)),
        key=lambda item: item[0],
    )
    total_weight = sum(weight for _, weight in paired)
    if total_weight <= 0:
        return None
    target_weight = total_weight * q
    cumulative = 0.0
    for price, weight in paired:
        cumulative += weight
        if cumulative >= target_weight:
            return price
    return paired[-1][0]


def _run_retrieval_search(
    client: ClickHouseClient,
    *,
    league: str,
    route: str,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    target_identity_key = _build_target_identity_key(parsed)
    candidate_rows = _query_rows(
        client,
        sql.build_retrieval_candidate_query(
            league=league,
            route=route,
            target_identity_key=target_identity_key,
        ),
    )

    if not candidate_rows:
        candidate_rows = _query_rows(
            client,
            sql.build_retrieval_candidate_query(
                league=league,
                route=route,
            ),
        )

    parsed_prices: list[float] = []
    parsed_weights: list[float] = []
    for row in candidate_rows:
        price = _coerce_float(row.get("candidate_price_chaos"))
        if price is None or price <= 0:
            continue
        distance = _coerce_float(row.get("distance_score"))
        if distance is None:
            distance = 0.5
        score = max(0.0, min(1.0, 1.0 - distance))
        parsed_prices.append(price)
        parsed_weights.append(score)

    if not parsed_prices:
        return {
            "stage": 0,
            "candidate_count": 0,
            "effective_support": 0,
            "dropped_affixes": [],
            "degradation_reason": "no_retrieval_candidates",
            "anchor_price": None,
            "anchor_low": None,
            "anchor_high": None,
        }

    anchor = _weighted_quantile(parsed_prices, parsed_weights, 0.5)
    anchor_low = _weighted_quantile(parsed_prices, parsed_weights, 0.1)
    anchor_high = _weighted_quantile(parsed_prices, parsed_weights, 0.9)
    if anchor is None or anchor_low is None or anchor_high is None:
        return {
            "stage": 1,
            "candidate_count": len(candidate_rows),
            "effective_support": 0,
            "dropped_affixes": [],
            "degradation_reason": "invalid_retrieval_weights",
            "anchor_price": None,
            "anchor_low": None,
            "anchor_high": None,
        }

    return {
        "stage": 4,
        "candidate_count": len(candidate_rows),
        "effective_support": len(parsed_prices),
        "dropped_affixes": [],
        "degradation_reason": None,
        "anchor_price": anchor,
        "anchor_low": anchor_low,
        "anchor_high": anchor_high,
    }


def _load_bundle_if_present(
    *, model_dir: str, league: str, route: str
) -> dict[str, Any] | None:
    path = Path(model_dir) / "v3" / league / route / "bundle.joblib"
    if not path.exists():
        return None
    payload = joblib.load(path)
    if not isinstance(payload, dict):
        return None
    return payload


def _median_fallback(
    client: ClickHouseClient,
    *,
    league: str,
    route: str,
    base_type: str,
    rarity: str,
) -> tuple[float, int]:
    query = " ".join(
        [
            "SELECT quantileTDigest(0.5)(target_price_chaos) AS p50, count() AS rows",
            f"FROM {TRAINING_TABLE}",
            f"WHERE league = {_quote(league)}",
            f"AND route = {_quote(route)}",
            f"AND base_type = {_quote(base_type)}",
            f"AND rarity = {_quote(rarity)}",
            "FORMAT JSONEachRow",
        ]
    )
    rows = _query_rows(client, query)
    if not rows:
        return 1.0, 0
    p50 = float(rows[0].get("p50") or 1.0)
    support = int(rows[0].get("rows") or 0)
    return max(0.1, p50), max(0, support)


def _confidence_from_support_and_interval(
    *, support: int, p10: float, p50: float, p90: float
) -> float:
    support_score = min(max(support, 0), 4000) / 4000.0
    width_ratio = (max(p90, p10) - min(p90, p10)) / max(p50, 0.1)
    tightness_score = max(0.0, 1.0 - min(width_ratio, 1.5) / 1.5)
    confidence = 0.15 + (0.5 * support_score) + (0.35 * tightness_score)
    return max(0.05, min(0.99, confidence))


def predict_one_v3(
    client: ClickHouseClient,
    *,
    league: str,
    clipboard_text: str,
    model_dir: str = "artifacts/ml",
) -> dict[str, Any]:
    parsed = workflows._parse_clipboard_item(clipboard_text)
    route = _route_for_item(parsed)
    features = build_feature_row(parsed)
    base_type = str(parsed.get("base_type") or "")
    rarity = str(parsed.get("rarity") or "")

    retrieval = _run_retrieval_search(
        client,
        league=league,
        route=route,
        parsed=parsed,
    )
    retrieval_anchor = _coerce_float(retrieval.get("anchor_price"))
    retrieval_anchor_low = _coerce_float(retrieval.get("anchor_low"))
    retrieval_anchor_high = _coerce_float(retrieval.get("anchor_high"))
    retrieval_stage = int(_coerce_float(retrieval.get("stage")) or 0)
    retrieval_candidate_count = int(
        _coerce_float(retrieval.get("candidate_count")) or 0
    )
    retrieval_effective_support = int(
        _coerce_float(retrieval.get("effective_support")) or 0
    )
    retrieval_dropped_affixes = _coerce_str_list(retrieval.get("dropped_affixes"))
    retrieval_degradation_reason = str(retrieval.get("degradation_reason") or "")

    bundle = _load_bundle_if_present(model_dir=model_dir, league=league, route=route)

    if bundle is None:
        if retrieval_anchor is None:
            p50, support = _median_fallback(
                client,
                league=league,
                route=route,
                base_type=base_type,
                rarity=rarity,
            )
            p10 = max(0.1, p50 * 0.85)
            p90 = max(p50, p50 * 1.15)
            confidence = 0.25 if support < 20 else 0.45
            sale_prob = 0.35 if support < 20 else 0.55
            source = "v3_median_fallback"
            fast_sale = max(0.1, p50 * 0.9)
            fallback_reason = "v3_no_bundle"
        else:
            p50 = retrieval_anchor
            p10 = retrieval_anchor_low
            p90 = retrieval_anchor_high
            if p10 is None:
                p10 = max(0.1, p50 * 0.85)
            if p90 is None:
                p90 = max(p50, p50 * 1.15)
            support = retrieval_effective_support
            confidence = _confidence_from_support_and_interval(
                support=support,
                p10=p10,
                p50=p50,
                p90=p90,
            )
            sale_prob = 0.35 if support < 20 else 0.55
            source = "v3_retrieval_fallback"
            fast_sale = max(0.1, p50 * 0.9)
            fallback_reason = ""
    else:
        vectorizer = bundle["vectorizer"]
        X = vectorizer.transform([features])
        models = bundle["models"]
        model_p10 = float(models["p10"].predict(X)[0])
        model_p50 = float(models["p50"].predict(X)[0])
        model_p90 = float(models["p90"].predict(X)[0])
        if retrieval_anchor is None:
            p10 = model_p10
            p50 = model_p50
            p90 = model_p90
        else:
            p10 = _combine_with_anchor(retrieval_anchor, model_p10, 0.45)
            p50 = _combine_with_anchor(retrieval_anchor, model_p50, 0.45)
            p90 = _combine_with_anchor(retrieval_anchor, model_p90, 0.45)
        p10 = max(0.1, p10)
        p50 = max(p10, p50)
        p90 = max(p50, p90)
        sale_model = models.get("sale_probability")
        if sale_model is None:
            sale_prob = 0.5
        else:
            sale_prob = float(sale_model.predict_proba(X)[0][1])
        support = int((bundle.get("metadata") or {}).get("row_count") or 0)
        if retrieval_effective_support > 0:
            support = max(support, retrieval_effective_support)
        confidence = _confidence_from_support_and_interval(
            support=support,
            p10=p10,
            p50=p50,
            p90=p90,
        )
        if retrieval_degradation_reason:
            confidence = max(0.05, confidence * 0.85)
        multiplier = float(bundle.get("fallback_fast_sale_multiplier") or 0.9)
        fast_sale_model = models.get("fast_sale_24h")
        if fast_sale_model is None:
            fast_sale = max(0.1, p50 * multiplier)
        else:
            fast_sale = max(0.1, float(fast_sale_model.predict(X)[0]))
        source = "v3_model"
        fallback_reason = ""

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    prediction_id = str(uuid.uuid4())
    uncertainty_tier = (
        "low" if confidence >= 0.7 else ("medium" if confidence >= 0.45 else "high")
    )
    if source != "v3_model":
        confidence = max(0.05, confidence - 0.1)
    return {
        "prediction_id": prediction_id,
        "prediction_as_of_ts": now,
        "route": route,
        "price_p10": p10,
        "price_p50": p50,
        "price_p90": p90,
        "fair_value_p10": p10,
        "fair_value_p50": p50,
        "fair_value_p90": p90,
        "fast_sale_24h_price": fast_sale,
        "sale_probability_24h": sale_prob,
        "sale_probability_percent": round(sale_prob * 100, 2),
        "confidence": confidence,
        "confidence_percent": round(confidence * 100, 2),
        "support_count_recent": support,
        "prediction_source": source,
        "uncertainty_tier": uncertainty_tier,
        "fallback_reason": fallback_reason,
        "ml_predicted": True,
        "price_recommendation_eligible": confidence >= 0.35,
        "predictedValue": p50,
        "interval": {"p10": p10, "p90": p90},
        "retrieval_stage": retrieval_stage,
        "retrieval_candidate_count": retrieval_candidate_count,
        "retrieval_effective_support": retrieval_effective_support,
        "retrieval_dropped_affixes": retrieval_dropped_affixes,
        "retrieval_degradation_reason": retrieval_degradation_reason,
        "retrieval_anchor_price": retrieval_anchor,
        "retrieval_anchor_low": retrieval_anchor_low,
        "retrieval_anchor_high": retrieval_anchor_high,
    }
