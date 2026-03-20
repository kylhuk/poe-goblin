#!/usr/bin/env python3
"""Backfill ml_item_mod_features_v1 using EXACT GGPK matching."""

import json
import re
import sys
import subprocess


def convert_clickhouse_array(s):
    if not s:
        return "[]"
    s2 = s.replace('"', "")
    s2 = s2.replace("'", '"')
    return s2


def load_ggpk_lookup(path):
    with open(path) as f:
        mods = json.load(f)

    lookup = {}

    for mod_id, mod_data in mods.items():
        text = mod_data.get("text", "")
        if not text:
            continue

        tier_match = re.search(r"(\d+)$", mod_id)
        if not tier_match:
            continue
        tier = int(tier_match.group(1))

        base_name = re.sub(r"\d+$", "", mod_id)
        base_lower = base_name.lower()

        range_match = re.search(r"\+\((\d+)-(\d+)\)", text)
        if range_match:
            min_val = int(range_match.group(1))
            max_val = int(range_match.group(2))

            for val in range(min_val, max_val + 1):
                key = (base_lower, val)
                if key not in lookup or tier < lookup[key][0]:
                    lookup[key] = (tier, max_val)

        simple_pct = re.search(r"(\d+)% increased (.+)", text)
        if simple_pct and "movement" in text.lower():
            pct = int(simple_pct.group(1))
            key = (f"movementvelocity{pct}", pct)
            if key not in lookup:
                lookup[key] = (tier, pct)

    return lookup


def match_token(token, lookup):
    results = {}
    token_lower = token.strip().strip('"').lower()

    numbers = re.findall(r"(\d+)", token_lower)

    for num_str in numbers:
        num = int(num_str)

        if "to dexterity" in token_lower:
            tier, maxv = lookup.get(("dexterity", num), (8, 50))
            results["Dexterity"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "to strength" in token_lower:
            tier, maxv = lookup.get(("strength", num), (8, 50))
            results["Strength"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "to intelligence" in token_lower:
            tier, maxv = lookup.get(("intelligence", num), (8, 50))
            results["Intelligence"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "maximum life" in token_lower or "to life" in token_lower:
            tier, maxv = lookup.get(("increasedlife", num), (5, 100))
            results["MaximumLife"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "movement speed" in token_lower or (
            "movement" in token_lower and "speed" in token_lower
        ):
            tier, maxv = lookup.get((f"movementvelocity{num}", num), (5, 30))
            results["MovementSpeed"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "maximum mana" in token_lower or (
            "mana" in token_lower and "maximum" in token_lower
        ):
            tier, maxv = lookup.get(("maximummana", num), (5, 100))
            results["MaximumMana"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "energy shield" in token_lower:
            tier, maxv = lookup.get(("maximumenergyshield", num), (5, 100))
            results["MaximumEnergyShield"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "evasion" in token_lower:
            tier, maxv = lookup.get(("evasionrating", num), (5, 100))
            results["EvasionRating"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "armor" in token_lower or "armour" in token_lower:
            tier, maxv = lookup.get(("armor", num), (5, 100))
            results["Armor"] = {
                "tier": tier,
                "roll": round(num / maxv, 2) if maxv else 1.0,
            }
        elif "resistance" in token_lower or "resistances" in token_lower:
            if "fire" in token_lower:
                results["FireResistance"] = {
                    "tier": min(num // 5 + 1, 10),
                    "roll": min(num / 30, 1.0),
                }
            elif "cold" in token_lower:
                results["ColdResistance"] = {
                    "tier": min(num // 5 + 1, 10),
                    "roll": min(num / 30, 1.0),
                }
            elif "lightning" in token_lower:
                results["LightningResistance"] = {
                    "tier": min(num // 5 + 1, 10),
                    "roll": min(num / 30, 1.0),
                }
            elif "chaos" in token_lower:
                results["ChaosResistance"] = {
                    "tier": min(num // 3 + 1, 10),
                    "roll": min(num / 20, 1.0),
                }
            elif "all elemental" in token_lower:
                results["AllElementalResistances"] = {
                    "tier": min(num // 5 + 1, 10),
                    "roll": min(num / 30, 1.0),
                }
        elif "critical strike chance" in token_lower:
            results["CriticalStrikeChance"] = {
                "tier": min(num // 5 + 1, 10),
                "roll": min(num / 50, 1.0),
            }
        elif "attack speed" in token_lower:
            results["AttackSpeed"] = {
                "tier": min(num // 3 + 1, 10),
                "roll": min(num / 20, 1.0),
            }
        elif "cast speed" in token_lower:
            results["CastSpeed"] = {
                "tier": min(num // 3 + 1, 10),
                "roll": min(num / 20, 1.0),
            }
        elif "physical damage" in token_lower:
            results["PhysicalDamage"] = {
                "tier": min(num // 5 + 1, 10),
                "roll": min(num / 30, 1.0),
            }
        elif "spell damage" in token_lower:
            results["SpellDamage"] = {
                "tier": min(num // 5 + 1, 10),
                "roll": min(num / 40, 1.0),
            }
        elif "elemental damage" in token_lower:
            results["ElementalDamage"] = {
                "tier": min(num // 5 + 1, 10),
                "roll": min(num / 30, 1.0),
            }
        elif "fire damage" in token_lower:
            results["FireDamage"] = {
                "tier": min(num // 10 + 1, 10),
                "roll": min(num / 60, 1.0),
            }
        elif "cold damage" in token_lower:
            results["ColdDamage"] = {
                "tier": min(num // 10 + 1, 10),
                "roll": min(num / 60, 1.0),
            }
        elif "lightning damage" in token_lower:
            results["LightningDamage"] = {
                "tier": min(num // 10 + 1, 10),
                "roll": min(num / 60, 1.0),
            }
        elif "chaos damage" in token_lower:
            results["ChaosDamage"] = {
                "tier": min(num // 5 + 1, 10),
                "roll": min(num / 30, 1.0),
            }

    return results


def get_item_tokens_batch(offset, limit):
    query = f"""
    SELECT item_id, groupArray(mod_token) as tokens 
    FROM poe_trade.ml_item_mod_tokens_v1 
    WHERE league = 'Mirage' 
    GROUP BY item_id 
    LIMIT {limit} OFFSET {offset}
    """

    cmd = [
        "docker",
        "exec",
        "poe_trade-clickhouse-1",
        "clickhouse-client",
        "--query",
        query,
        "--max_threads",
        "8",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        print(f"Query error: {result.stderr[:200]}", file=sys.stderr)
        return {}

    items = {}
    for line in result.stdout.strip().split("\n"):
        if "\t" in line:
            parts = line.split("\t", 1)
            if len(parts) >= 2:
                item_id = parts[0]
                try:
                    tokens_str = convert_clickhouse_array(parts[1])
                    tokens = json.loads(tokens_str)
                    items[item_id] = tokens
                except Exception as e:
                    pass

    return items


def process_items(items, lookup):
    results = {}

    for item_id, tokens in items.items():
        all_mods = {}
        for token in tokens:
            mods = match_token(token, lookup)
            all_mods.update(mods)

        if all_mods:
            feature_dict = {}
            for mod_name, data in all_mods.items():
                feature_dict[f"{mod_name}_tier"] = data["tier"]
                feature_dict[f"{mod_name}_roll"] = data["roll"]
            results[item_id] = feature_dict

    return results


def main():
    lookup = load_ggpk_lookup("/tmp/mods.min.json")
    print(f"Loaded {len(lookup)} GGPK entries", file=sys.stderr)

    batch_size = 5000
    total = 0
    output_file = "mod_features_updates.sql"

    with open(output_file, "w") as f:
        for offset in range(0, 200000, batch_size):
            print(f"Processing offset {offset}...", file=sys.stderr)

            items = get_item_tokens_batch(offset, batch_size)
            if not items:
                break

            item_features = process_items(items, lookup)

            for item_id, features in item_features.items():
                json_str = json.dumps(features).replace("'", "''")
                f.write(
                    f"UPDATE poe_trade.ml_item_mod_features_v1 SET mod_features_json = '{json_str}' WHERE item_id = '{item_id}';\n"
                )

            total += len(item_features)
            print(f"  {len(item_features)} items (total: {total})", file=sys.stderr)

            if len(items) < batch_size:
                break

    print(f"Done. Wrote {total} updates to {output_file}", file=sys.stderr)
    print(
        f"To apply: docker exec poe_trade-clickhouse-1 clickhouse-client --multiquery < {output_file}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
