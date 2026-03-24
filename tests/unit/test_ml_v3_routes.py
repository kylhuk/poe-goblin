from __future__ import annotations

import pytest

from poe_trade.ml.v3 import routes, sql


def test_select_route_matches_current_sparse_rare_behavior() -> None:
    parsed = {"category": "helmet", "rarity": "Rare"}

    assert routes.select_route(parsed) == "sparse_retrieval"


def test_select_route_matches_cluster_jewel_behavior() -> None:
    parsed = {"category": "cluster_jewel", "rarity": "Rare"}

    assert routes.select_route(parsed) == "cluster_jewel_retrieval"


def test_select_route_keeps_unique_cluster_jewel_on_cluster_route() -> None:
    parsed = {"category": "cluster_jewel", "rarity": "Unique"}

    assert routes.select_route(parsed) == "cluster_jewel_retrieval"


def test_select_route_keeps_essence_behavior_from_previous_serving_logic() -> None:
    assert routes.select_route({"category": "essence", "rarity": "Magic"}) == (
        "fallback_abstain"
    )
    assert routes.select_route({"category": "essence", "rarity": "Rare"}) == (
        "sparse_retrieval"
    )


def test_serving_and_training_share_route_contract() -> None:
    parsed = {"category": "ring", "rarity": "Unique"}

    assert sql.select_route(parsed) == routes.select_route(parsed)


def test_route_sql_expression_preserves_edge_case_rule_order() -> None:
    expr = routes.route_sql_expression()

    assert expr.index("= 'cluster_jewel'") < expr.index("= 'Unique'")
    assert "IN ('essence')" not in expr
    assert "= 'Rare'" in expr


@pytest.mark.parametrize(
    ("parsed", "expected_family", "expected_alias"),
    [
        (
            {"category": "cluster_jewel", "rarity": "Unique"},
            "cluster_jewel_retrieval",
            "cluster_jewel_retrieval",
        ),
        (
            {"category": "cluster_jewel", "rarity": "Rare"},
            "cluster_jewel_retrieval",
            "cluster_jewel_retrieval",
        ),
        (
            {"category": "cluster_jewel"},
            "cluster_jewel_retrieval",
            "cluster_jewel_retrieval",
        ),
        (
            {"category": "fossil", "rarity": "Rare"},
            "fungible_reference",
            "fungible_reference",
        ),
        (
            {"category": "fossil", "rarity": "Unique"},
            "fungible_reference",
            "fungible_reference",
        ),
        (
            {"category": "scarab", "rarity": "Rare"},
            "fungible_reference",
            "fungible_reference",
        ),
        (
            {"category": "logbook", "rarity": "Rare"},
            "fungible_reference",
            "fungible_reference",
        ),
        (
            {"category": "ring", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted_other",
        ),
        (
            {"category": "amulet", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted_other",
        ),
        (
            {"category": "belt", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted_other",
        ),
        (
            {"category": "jewel", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted_other",
        ),
        (
            {"category": "other", "base_type": "Two-Stone Ring", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted",
        ),
        (
            {"category": "other", "base_type": "Onyx Amulet", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted",
        ),
        (
            {"category": "other", "base_type": "Leather Belt", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted",
        ),
        (
            {"category": "other", "base_type": "Crimson Jewel", "rarity": "Unique"},
            "structured_boosted_other",
            "structured_boosted",
        ),
        (
            {"category": "helmet", "rarity": "Unique"},
            "structured_boosted",
            "structured_boosted",
        ),
        ({"category": "map", "rarity": "Rare"}, "sparse_retrieval", "sparse_retrieval"),
        (
            {"category": "helmet", "rarity": "Rare"},
            "sparse_retrieval",
            "sparse_retrieval",
        ),
        (
            {"category": "ring", "rarity": "Rare"},
            "sparse_retrieval",
            "sparse_retrieval",
        ),
        (
            {"category": "amulet", "rarity": "Rare"},
            "sparse_retrieval",
            "sparse_retrieval",
        ),
        (
            {"category": "belt", "rarity": "Rare"},
            "sparse_retrieval",
            "sparse_retrieval",
        ),
        (
            {"category": "jewel", "rarity": "Rare"},
            "sparse_retrieval",
            "sparse_retrieval",
        ),
        (
            {"category": "essence", "rarity": "Rare"},
            "sparse_retrieval",
            "sparse_retrieval",
        ),
        (
            {"category": "essence", "rarity": "Magic"},
            "fallback_abstain",
            "fallback_abstain",
        ),
        (
            {"category": "ring", "rarity": "Magic"},
            "fallback_abstain",
            "fallback_abstain",
        ),
        (
            {"category": "helmet", "rarity": "Magic"},
            "fallback_abstain",
            "fallback_abstain",
        ),
    ],
)
def test_assign_cohort_taxonomy_precedence_contract(
    parsed: dict[str, object],
    expected_family: str,
    expected_alias: str,
) -> None:
    cohort = routes.assign_cohort(parsed)

    assert cohort["strategy_family"] == expected_family
    assert cohort["route_compatibility_alias"] == expected_alias
    assert cohort["cohort_key"].startswith(expected_family + "|")
    assert cohort["parent_cohort_key"].startswith(expected_family + "|")
    assert cohort["material_state_signature"].startswith("v1|")


@pytest.mark.parametrize(
    "parsed",
    [
        {},
        {"category": "ring"},
        {"rarity": "Unique"},
        {"category": "", "rarity": ""},
    ],
)
def test_assign_cohort_required_field_fallbacks(parsed: dict[str, object]) -> None:
    cohort = routes.assign_cohort(parsed)

    assert cohort["strategy_family"] == "fallback_abstain"
    assert cohort["route_compatibility_alias"] == "fallback_abstain"
    assert cohort["cohort_key"].startswith("fallback_abstain|")
    assert cohort["parent_cohort_key"].startswith("fallback_abstain|")


@pytest.mark.parametrize(
    ("parsed", "expected_signature"),
    [
        (
            {
                "category": "ring",
                "rarity": "Unique",
                "corrupted": 1,
                "fractured": 0,
                "synthesised": True,
            },
            "v1|rarity=unique|corrupted=1|fractured=0|synthesised=1",
        ),
        (
            {
                "category": "cluster_jewel",
                "rarity": "Rare",
                "corrupted": "false",
                "fractured": "yes",
                "synthesised": "no",
            },
            "v1|rarity=rare|corrupted=0|fractured=1|synthesised=0",
        ),
        (
            {
                "category": "fossil",
                "rarity": "",
                "corrupted": "",
                "fractured": None,
                "synthesised": 7,
            },
            "v1|rarity=unknown|corrupted=0|fractured=0|synthesised=1",
        ),
    ],
)
def test_assign_cohort_material_state_signature_v1_is_deterministic(
    parsed: dict[str, object],
    expected_signature: str,
) -> None:
    first = routes.assign_cohort(parsed)
    second = routes.assign_cohort(dict(parsed))

    assert first["material_state_signature"] == expected_signature
    assert second["material_state_signature"] == expected_signature
    assert first["cohort_key"] == second["cohort_key"]
