#!/usr/bin/env python3
"""
Backfill ml_item_mod_features_v1 from ml_item_mod_tokens_v1

Uses fuzzy matching between tokens and GGPK patterns.
"""

import json
import re
import sys
from collections import defaultdict

# Simplified mod name mapping (token word -> GGPK base name)
MOD_NAME_MAP = {
    "strength": "Strength",
    "dexterity": "Dexterity",
    "intelligence": "Intelligence",
    "life": "MaximumLife",
    "maximum life": "MaximumLife",
    "mana": "MaximumMana",
    "maximum mana": "MaximumMana",
    "energy shield": "MaximumEnergyShield",
    "evasion": "EvasionRating",
    "armor": "Armor",
    "movement speed": "MovementSpeed",
    "critical strike chance": "CriticalStrikeChance",
    "critical strike multiplier": "CriticalStrikeMultiplier",
    "attack speed": "AttackSpeed",
    "cast speed": "CastSpeed",
    "physical damage": "PhysicalDamage",
    "fire damage": "FireDamageFlat",
    "cold damage": "ColdDamageFlat",
    "lightning damage": "LightningDamageFlat",
    "chaos damage": "ChaosDamageFlat",
    "elemental damage": "ElementalDamage",
    "flask duration": "FlaskDuration",
    "flask charges": "FlaskCharges",
    "item quantity": "ItemQuantity",
    "item rarity": "ItemRarity",
    "accuracy rating": "AccuracyRating",
    "block chance": "BlockChance",
    "spell damage": "SpellDamage",
    "projectile damage": "ProjectileDamage",
    "area of effect": "AreaOfEffect",
    "melee damage": "MeleeDamage",
    "minion damage": "MinionDamage",
    "minion life": "MinionLife",
    "trap damage": "TrapDamage",
    "mine damage": "MineDamage",
    "totem damage": "TotemDamage",
    "fire resistance": "FireResistance",
    "cold resistance": "ColdResistance",
    "lightning resistance": "LightningResistance",
    "chaos resistance": "ChaosResistance",
    "all elemental resistances": "AllElementalResistances",
}


def extract_mod_info(token: str) -> dict:
    """Extract mod info from token using simple pattern matching."""
    token_lower = token.lower().strip()
    result = {}

    # Try to match known mod patterns
    for pattern_key, base_name in MOD_NAME_MAP.items():
        if pattern_key in token_lower:
            # Extract tier from token (rough approximation)
            tier = estimate_tier(token_lower, base_name)
            result[base_name] = {"tier": tier, "roll": 1.0}

    return result


def estimate_tier(token: str, base_name: str) -> int:
    """Roughly estimate tier from token values."""
    # Extract numbers from token
    numbers = re.findall(r"\d+", token)
    if not numbers:
        return 5  # Default mid tier

    # Use the largest number as the value
    max_val = max(int(n) for n in numbers)

    # Map value to tier (rough approximation based on typical mod values)
    tier_ranges = {
        "Strength": [
            (15, 1),
            (20, 2),
            (25, 3),
            (30, 4),
            (35, 5),
            (40, 6),
            (45, 7),
            (50, 8),
            (55, 9),
            (60, 10),
        ],
        "Dexterity": [
            (15, 1),
            (20, 2),
            (25, 3),
            (30, 4),
            (35, 5),
            (40, 6),
            (45, 7),
            (50, 8),
            (55, 9),
            (60, 10),
        ],
        "Intelligence": [
            (15, 1),
            (20, 2),
            (25, 3),
            (30, 4),
            (35, 5),
            (40, 6),
            (45, 7),
            (50, 8),
            (55, 9),
            (60, 10),
        ],
        "MaximumLife": [
            (20, 1),
            (30, 2),
            (40, 3),
            (50, 4),
            (60, 5),
            (70, 6),
            (80, 7),
            (90, 8),
            (100, 9),
            (110, 10),
        ],
        "MaximumMana": [
            (15, 1),
            (20, 2),
            (25, 3),
            (30, 4),
            (35, 5),
            (40, 6),
            (45, 7),
            (50, 8),
            (55, 9),
            (60, 10),
        ],
        "MovementSpeed": [
            (5, 1),
            (6, 2),
            (7, 3),
            (8, 4),
            (9, 5),
            (10, 6),
            (11, 7),
            (12, 8),
            (13, 9),
            (14, 10),
        ],
        "CriticalStrikeChance": [
            (20, 1),
            (25, 2),
            (30, 3),
            (35, 4),
            (40, 5),
            (45, 6),
            (50, 7),
            (55, 8),
            (60, 9),
            (65, 10),
        ],
        "FireResistance": [
            (10, 1),
            (12, 2),
            (14, 3),
            (16, 4),
            (18, 5),
            (20, 6),
            (22, 7),
            (24, 8),
            (26, 9),
            (28, 10),
        ],
        "ColdResistance": [
            (10, 1),
            (12, 2),
            (14, 3),
            (16, 4),
            (18, 5),
            (20, 6),
            (22, 7),
            (24, 8),
            (26, 9),
            (28, 10),
        ],
        "LightningResistance": [
            (10, 1),
            (12, 2),
            (14, 3),
            (16, 4),
            (18, 5),
            (20, 6),
            (22, 7),
            (24, 8),
            (26, 9),
            (28, 10),
        ],
    }

    ranges = tier_ranges.get(base_name, [(20, 5)])
    for threshold, tier in ranges:
        if max_val <= threshold:
            return tier
    return ranges[-1][1]  # Return max tier


if __name__ == "__main__":
    # Read tokens from stdin (JSON array)
    tokens = json.load(sys.stdin)

    results = {}
    for item in tokens:
        item_id = item["item_id"]
        token = item["mod_token"]

        mod_info = extract_mod_info(token)
        if mod_info:
            results[item_id] = mod_info

    print(json.dumps(results))
