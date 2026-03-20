from __future__ import annotations

import pytest

from poe_trade.ml import workflows


@pytest.mark.parametrize("mod_features_json", ["", "{"])
def test_feature_dict_builders_normalize_invalid_mod_features_json(
    monkeypatch: pytest.MonkeyPatch, mod_features_json: str
) -> None:
    monkeypatch.setattr(workflows, "_discovered_mod_features", ["MaximumLife_tier"])

    row_features = workflows._feature_dict_from_row(
        {
            "category": "other",
            "base_type": "Amulet",
            "rarity": "Rare",
            "ilvl": 82,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 4,
            "mod_features_json": mod_features_json,
        }
    )
    parsed_item_features = workflows._feature_dict_from_parsed_item(
        {
            "category": "other",
            "base_type": "Amulet",
            "rarity": "Rare",
            "ilvl": 82,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 4,
            "mod_features_json": mod_features_json,
        }
    )

    assert row_features["MaximumLife_tier"] == 0.0
    assert parsed_item_features["MaximumLife_tier"] == 0.0
