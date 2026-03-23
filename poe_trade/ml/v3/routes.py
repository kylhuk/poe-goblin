from __future__ import annotations

from typing import Any, Mapping


def select_route(parsed: Mapping[str, Any]) -> str:
    """Select a deterministic v3 route from parsed item fields.

    The logic mirrors legacy v3 serving behavior while creating a shared
    contract for future retrieval and training callers.
    """

    category = str(parsed.get("category") or "other").strip().lower()
    rarity = str(parsed.get("rarity") or "").strip()
    if category == "cluster_jewel":
        return "cluster_jewel_retrieval"
    if category in {"fossil", "scarab", "logbook"}:
        return "fungible_reference"
    if rarity == "Unique" and category in {"ring", "amulet", "belt", "jewel"}:
        return "structured_boosted_other"
    if rarity == "Unique":
        return "structured_boosted"
    if rarity == "Rare":
        return "sparse_retrieval"
    return "fallback_abstain"
