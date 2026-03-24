from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


@dataclass(frozen=True)
class _RouteRule:
    route: str
    categories: frozenset[str] | None = None
    rarity: str | None = None


_ORDERED_ROUTE_RULES: tuple[_RouteRule, ...] = (
    _RouteRule(
        route="cluster_jewel_retrieval", categories=frozenset({"cluster_jewel"})
    ),
    _RouteRule(
        route="fungible_reference",
        categories=frozenset({"fossil", "scarab", "logbook"}),
    ),
    _RouteRule(
        route="structured_boosted_other",
        rarity="Unique",
        categories=frozenset({"ring", "amulet", "belt", "jewel"}),
    ),
    _RouteRule(route="structured_boosted", rarity="Unique"),
    _RouteRule(route="sparse_retrieval", rarity="Rare"),
)

_DEFAULT_ROUTE = "fallback_abstain"

_FUNGIBLE_CATEGORIES = frozenset({"fossil", "scarab", "logbook"})
_STRUCTURED_OTHER_FAMILIES = frozenset({"ring", "amulet", "belt", "jewel"})


def _matches_rule(*, category: str, rarity: str, rule: _RouteRule) -> bool:
    if rule.rarity is not None and rarity != rule.rarity:
        return False
    if rule.categories is not None and category not in rule.categories:
        return False
    return True


def _normalize_text(value: Any, *, default: str = "") -> str:
    normalized = str(value or "").strip().lower()
    if normalized:
        return normalized
    return default


def _to_flag_int(value: Any) -> int:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "on"}:
            return 1
        if normalized in {"false", "f", "no", "n", "off", ""}:
            return 0
    try:
        return 1 if int(value or 0) != 0 else 0
    except (TypeError, ValueError):
        return 0


def _structured_other_scope(parsed: Mapping[str, Any]) -> str:
    category = _normalize_text(parsed.get("category"), default="other")
    if category in _STRUCTURED_OTHER_FAMILIES:
        return category
    base_type = _normalize_text(parsed.get("base_type"))
    item_type_line = _normalize_text(parsed.get("item_type_line"))
    lowered = " ".join(part for part in (base_type, item_type_line) if part)
    if re.search(r"\bring\b", lowered):
        return "ring"
    if re.search(r"\bamulet\b", lowered):
        return "amulet"
    if re.search(r"\bbelt\b", lowered):
        return "belt"
    if re.search(r"\b(?:cluster\s+)?jewel\b", lowered):
        return "jewel"
    return "other"


def _material_state_signature_v1(parsed: Mapping[str, Any]) -> str:
    rarity = _normalize_text(parsed.get("rarity"), default="unknown")
    corrupted = _to_flag_int(parsed.get("corrupted"))
    fractured = _to_flag_int(parsed.get("fractured"))
    synthesised = _to_flag_int(parsed.get("synthesised"))
    return (
        "v1|"
        + f"rarity={rarity}|"
        + f"corrupted={corrupted}|"
        + f"fractured={fractured}|"
        + f"synthesised={synthesised}"
    )


def assign_cohort(parsed: Mapping[str, Any]) -> dict[str, str]:
    category = _normalize_text(parsed.get("category"))
    rarity = str(parsed.get("rarity") or "").strip()
    route_alias = _DEFAULT_ROUTE if not category else select_route(parsed)
    material_state_signature = _material_state_signature_v1(parsed)

    strategy_family = _DEFAULT_ROUTE
    family_scope = "default"
    if category == "cluster_jewel":
        strategy_family = "cluster_jewel_retrieval"
        family_scope = "cluster_jewel"
    elif category in _FUNGIBLE_CATEGORIES:
        strategy_family = "fungible_reference"
        family_scope = category
    elif category and rarity == "Unique":
        structured_scope = _structured_other_scope(parsed)
        if structured_scope != "other":
            strategy_family = "structured_boosted_other"
            family_scope = structured_scope
        else:
            strategy_family = "structured_boosted"
            family_scope = "default"
    elif category and rarity == "Rare":
        strategy_family = "sparse_retrieval"
        family_scope = category

    parent_cohort_key = f"{strategy_family}|{material_state_signature}"
    cohort_key = f"{strategy_family}|{family_scope}|{material_state_signature}"
    return {
        "strategy_family": strategy_family,
        "cohort_key": cohort_key,
        "parent_cohort_key": parent_cohort_key,
        "material_state_signature": material_state_signature,
        "route_compatibility_alias": route_alias,
    }


def _sql_condition_for_rule(
    rule: _RouteRule, *, category_expr: str, rarity_expr: str
) -> str:
    parts: list[str] = []
    if rule.categories is not None:
        if len(rule.categories) == 1:
            category = next(iter(rule.categories))
            parts.append(f"{category_expr} = '{category}'")
        else:
            categories = ",".join(
                f"'{category}'" for category in sorted(rule.categories)
            )
            parts.append(f"{category_expr} IN ({categories})")
    if rule.rarity is not None:
        parts.append(f"{rarity_expr} = '{rule.rarity}'")
    return " AND ".join(parts)


def select_route(parsed: Mapping[str, Any]) -> str:
    category = str(parsed.get("category") or "other")
    rarity = str(parsed.get("rarity") or "")
    for rule in _ORDERED_ROUTE_RULES:
        if _matches_rule(category=category, rarity=rarity, rule=rule):
            return rule.route
    return _DEFAULT_ROUTE


def route_sql_expression(
    *, category_expr: str = "category", rarity_expr: str = "rarity"
) -> str:
    clauses = [
        f"{_sql_condition_for_rule(rule, category_expr=category_expr, rarity_expr=rarity_expr)}, '{rule.route}'"
        for rule in _ORDERED_ROUTE_RULES
    ]
    return "multiIf(" + ", ".join(clauses) + f", '{_DEFAULT_ROUTE}'" + ")"
