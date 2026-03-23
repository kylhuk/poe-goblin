from __future__ import annotations

from poe_trade.ml.v3 import routes


def test_select_route_matches_rare_default() -> None:
    parsed = {"category": "helmet", "rarity": "Rare"}

    assert routes.select_route(parsed) == "sparse_retrieval"


def test_select_route_selects_cluster_jewel_route() -> None:
    parsed = {"category": "cluster_jewel", "rarity": "Rare"}

    assert routes.select_route(parsed) == "cluster_jewel_retrieval"
