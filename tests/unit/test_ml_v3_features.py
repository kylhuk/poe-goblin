from __future__ import annotations

import pytest
from typing import cast

from poe_trade.db import ClickHouseClient
from poe_trade.ml import workflows
from poe_trade.ml.v3 import features


def test_canonicalize_mod_features_json_filters_invalid_values() -> None:
    payload = features.canonicalize_mod_features_json(
        '{"MaximumLife_tier":8,"bad":"x","":4,"AttackSpeed_roll":0.42}'
    )

    assert payload == {
        "MaximumLife_tier": 8.0,
        "AttackSpeed_roll": 0.42,
    }


def test_build_feature_row_includes_base_fields_and_mods() -> None:
    row = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": 86,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 1,
            "synthesised": 0,
            "mod_token_count": 2,
            "mod_features_json": '{"MaximumLife_tier":8}',
        }
    )

    assert row["category"] == "helmet"
    assert row["base_type"] == "Hubris Circlet"
    assert row["MaximumLife_tier"] == 8.0


def test_validate_ring_parser_row_accepts_clean_ring() -> None:
    counts = features.validate_ring_parser_row(
        {
            "synthesised": 0,
            "fractured": 0,
            "influence_mask": 0,
            "prefix_count": 3,
            "suffix_count": 3,
            "mod_features_json": '{"fire_resistance_present":1,"fire_resistance_quality_roll":0.8}',
        }
    )

    assert counts == {
        "synthesised_and_fractured": 0,
        "synthesised_and_influenced": 0,
        "too_many_prefixes": 0,
        "too_many_suffixes": 0,
        "non_ring_mod_family": 0,
        "non_influenced_ring_with_influence_family": 0,
    }


def test_validate_ring_parser_row_rejects_impossible_ring() -> None:
    with pytest.raises(ValueError, match="ring parser invariant violation"):
        features.validate_ring_parser_row(
            {
                "synthesised": 1,
                "fractured": 1,
                "influence_mask": 1,
                "prefix_count": 4,
                "suffix_count": 4,
                "mod_features_json": '{"shaper_present":1,"not_a_ring_present":1}',
            }
        )


def test_audit_ring_parser_invariants_passes_clean_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflows,
        "_query_rows",
        lambda _client, _query: [
            {
                "synthesised": 0,
                "fractured": 0,
                "influence_mask": 0,
                "prefix_count": 3,
                "suffix_count": 3,
                "mod_features_json": '{"fire_resistance_present":1}',
            }
        ],
    )

    counts = workflows.audit_ring_parser_invariants(
        cast(ClickHouseClient, object()), league="Mirage"
    )

    assert counts == {
        "synthesised_and_fractured": 0,
        "synthesised_and_influenced": 0,
        "too_many_prefixes": 0,
        "too_many_suffixes": 0,
        "non_ring_mod_family": 0,
        "non_influenced_ring_with_influence_family": 0,
    }


def test_audit_ring_parser_invariants_fails_on_invalid_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflows,
        "_query_rows",
        lambda _client, _query: [
            {
                "synthesised": 1,
                "fractured": 1,
                "influence_mask": 1,
                "prefix_count": 4,
                "suffix_count": 4,
                "mod_features_json": '{"shaper_present":1,"not_a_ring_present":1}',
            }
        ],
    )

    with pytest.raises(ValueError, match="ring parser invariant violation"):
        workflows.audit_ring_parser_invariants(
            cast(ClickHouseClient, object()), league="Mirage"
        )


def test_build_feature_row_includes_recent_support_count() -> None:
    row = features.build_feature_row(
        {
            "support_count_recent": "17",
        }
    )

    assert row["support_count_recent"] == 17


def test_build_feature_row_passthroughs_wide_view_columns() -> None:
    row = features.build_feature_row(
        {
            "as_of_ts": "2026-03-24 10:00:00.000",
            "realm": "pc",
            "league": "Mirage",
            "checkpoint": "cp-1",
            "next_change_id": "n-1",
            "account_name": "acct",
            "stash_name": "stash",
            "observed_at": "2026-03-24 10:00:00.000",
            "inserted_at": "2026-03-24 10:00:01.000",
            "split_bucket": 7,
            "mirrored": 1,
            "quality": 20,
            "number_of_sockets": 4,
            "number_of_links": 4,
            "sale_confidence_flag": 1,
            "target_price_chaos": 123.0,
            "label_weight": 0.75,
            "item_id": "item-1",
            "stash_id": "stash-1",
            "influence_mask": 12,
            "catalyst_type": "Prismatic",
            "catalyst_quality": 18,
            "synth_imp_count": 1,
            "synth_implicit_mods_json": '["+1 to Level of Socketed Gems"]',
            "corrupted_implicit_mods_json": "[]",
            "veiled_count": 0,
            "crafted_count": 1,
            "prefix_count": 2,
            "suffix_count": 2,
            "open_prefixes": 1,
            "open_suffixes": 1,
            "mod_features_json": "{}",
            "affixes": [("explicit", "foo")],
        }
    )

    assert row["mirrored"] == 1
    assert row["quality"] == 20
    assert row["number_of_sockets"] == 4
    assert row["number_of_links"] == 4
    assert "as_of_ts" not in row
    assert "realm" not in row
    assert "league" not in row
    assert "checkpoint" not in row
    assert "next_change_id" not in row
    assert "account_name" not in row
    assert "stash_name" not in row
    assert "observed_at" not in row
    assert "inserted_at" not in row
    assert "split_bucket" not in row
    assert "sale_confidence_flag" not in row
    assert "parsed_amount" not in row
    assert "affixes" not in row
    assert "target_price_chaos" not in row
    assert "label_weight" not in row
    assert "item_id" not in row
    assert "stash_id" not in row
    assert row["influence_mask"] == 12
    assert row["catalyst_type"] == "Prismatic"
    assert row["catalyst_quality"] == 18
    assert row["synth_imp_count"] == 1
    assert row["crafted_count"] == 1


def test_feature_schema_has_deterministic_fingerprint() -> None:
    one = features.feature_schema({"b": 1, "a": 2})
    two = features.feature_schema({"a": 9, "b": 0})

    assert one["version"] == "v3"
    assert one["fields"] == ["a", "b"]
    assert one["fingerprint"] == two["fingerprint"]


def test_build_feature_row_emits_item_state_key() -> None:
    row = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "corrupted": 1,
            "fractured": 0,
            "synthesised": 0,
            "mod_features_json": '{"explicit.life":1}',
        }
    )

    assert row["item_state_key"] == "rare|corrupted=1|fractured=0|synthesised=0"


def test_build_feature_row_emits_route_family_and_base_identity_key() -> None:
    one = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "corrupted": 1,
            "fractured": 0,
            "synthesised": 0,
            "mod_features_json": "{}",
        }
    )
    two = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "corrupted": 1,
            "fractured": 0,
            "synthesised": 0,
            "mod_features_json": "{}",
        }
    )

    assert one["route_family"] == "sparse_retrieval"
    assert one["base_identity_key"] == (
        "hubris circlet|rare|corrupted=1|fractured=0|synthesised=0"
    )
    assert two["base_identity_key"] == one["base_identity_key"]


def test_build_feature_row_includes_cohort_identity_fields() -> None:
    row = features.build_feature_row(
        {
            "strategy_family": "sparse_retrieval",
            "cohort_key": "sparse_retrieval|helmet|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "parent_cohort_key": "sparse_retrieval|v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "material_state_signature": "v1|rarity=rare|corrupted=0|fractured=0|synthesised=0",
            "item_name": "Hubris Circlet",
            "item_type_line": "Hubris Circlet",
        }
    )

    assert row["strategy_family"] == "sparse_retrieval"
    assert row["cohort_key"].startswith("sparse_retrieval|")
    assert row["parent_cohort_key"].startswith("sparse_retrieval|")
    assert row["material_state_signature"].startswith("v1|")
    assert row["item_name"] == "Hubris Circlet"
    assert row["item_type_line"] == "Hubris Circlet"


def test_build_feature_row_base_identity_changes_for_identity_inputs() -> None:
    base = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
        }
    )
    changed_base_type = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Lion Pelt",
            "rarity": "Rare",
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
        }
    )
    changed_state = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "corrupted": 1,
            "fractured": 0,
            "synthesised": 0,
        }
    )

    assert changed_base_type["base_identity_key"] != base["base_identity_key"]
    assert changed_state["base_identity_key"] != base["base_identity_key"]


def test_build_feature_row_route_family_changes_for_route_inputs() -> None:
    rare_helmet = features.build_feature_row(
        {
            "category": "helmet",
            "rarity": "Rare",
        }
    )
    unique_helmet = features.build_feature_row(
        {
            "category": "helmet",
            "rarity": "Unique",
        }
    )
    rare_cluster = features.build_feature_row(
        {
            "category": "cluster_jewel",
            "rarity": "Rare",
        }
    )

    assert rare_helmet["route_family"] == "sparse_retrieval"
    assert unique_helmet["route_family"] == "structured_boosted"
    assert rare_cluster["route_family"] == "cluster_jewel_retrieval"
    assert unique_helmet["route_family"] != rare_helmet["route_family"]
    assert rare_cluster["route_family"] != rare_helmet["route_family"]


def test_build_feature_row_handles_stringish_numeric_and_flag_inputs() -> None:
    row = features.build_feature_row(
        {
            "category": "helmet",
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "ilvl": "86",
            "stack_size": "2",
            "corrupted": "true",
            "fractured": "0",
            "synthesised": "False",
            "mod_token_count": "3",
        }
    )

    assert row["ilvl"] == 86
    assert row["stack_size"] == 2
    assert row["corrupted"] == 1
    assert row["fractured"] == 0
    assert row["synthesised"] == 0
    assert row["mod_token_count"] == 3


def test_build_feature_row_defaults_on_unparseable_stringish_numeric_inputs() -> None:
    row = features.build_feature_row(
        {
            "ilvl": "oops",
            "stack_size": "",
            "corrupted": "nope",
            "fractured": "n/a",
            "synthesised": None,
            "mod_token_count": "x",
        }
    )

    assert row["ilvl"] == 0
    assert row["stack_size"] == 1
    assert row["corrupted"] == 0
    assert row["fractured"] == 0
    assert row["synthesised"] == 0
    assert row["mod_token_count"] == 0


def test_build_feature_row_defaults_on_overflow_stringish_numeric_inputs() -> None:
    row = features.build_feature_row(
        {
            "ilvl": "inf",
            "stack_size": "1e309",
        }
    )

    assert row["ilvl"] == 0
    assert row["stack_size"] == 1
