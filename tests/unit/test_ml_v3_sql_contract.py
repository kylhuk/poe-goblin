from __future__ import annotations

from datetime import date
from typing import cast

import pytest

from poe_trade.db import ClickHouseClient
from poe_trade.ml.contract import PRICING_BENCHMARK_CONTRACT
from poe_trade.ml import workflows
from poe_trade.ml.v3 import sql
from poe_trade.ml.v3 import routes


def test_disk_usage_query_targets_system_parts() -> None:
    query = sql.disk_usage_query()

    assert "FROM system.parts" in query
    assert "database = 'poe_trade'" in query


def test_build_events_insert_query_scopes_league_and_day() -> None:
    query = sql.build_events_insert_query(league="Mirage", day=date(2026, 3, 20))

    assert f"INSERT INTO {sql.EVENTS_TABLE}" in query
    assert "WHERE league = 'Mirage'" in query
    assert "toDate('2026-03-20')" in query
    assert "lagInFrame" in query


def test_build_disappearance_events_insert_query_uses_snapshot_delta() -> None:
    query = sql.build_disappearance_events_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert f"INSERT INTO {sql.EVENTS_TABLE}" in query
    assert "arrayExcept" in query
    assert "disappeared" in query


def test_build_sale_proxy_labels_insert_query_uses_event_table() -> None:
    query = sql.build_sale_proxy_labels_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert f"INSERT INTO {sql.SALE_LABELS_TABLE}" in query
    assert f"FROM {sql.EVENTS_TABLE}" in query
    assert "sold_probability" in query
    assert PRICING_BENCHMARK_CONTRACT.label_source in query


class _NoopClickHouseClient:
    def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
        del query, settings
        return ""


def test_pricing_benchmark_contract_freezes_non_exchange_scope() -> None:
    assert PRICING_BENCHMARK_CONTRACT.name == "non_exchange_disappearance_benchmark_v1"
    assert PRICING_BENCHMARK_CONTRACT.confirmation_horizon_hours == 48
    assert PRICING_BENCHMARK_CONTRACT.exchange_routes == ("fungible_reference",)
    assert "sparse_retrieval" in PRICING_BENCHMARK_CONTRACT.non_exchange_routes
    assert "fallback_abstain" in PRICING_BENCHMARK_CONTRACT.non_exchange_routes


def test_build_listing_episodes_insert_query_collapses_snapshot_bursts() -> None:
    query = sql.build_listing_episodes_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert f"INSERT INTO {sql.LISTING_EPISODES_TABLE}" in query
    assert "lagInFrame(observed_at) OVER w" in query
    assert "sum(is_new_episode) OVER" in query
    assert "first_seen" in query
    assert "last_seen" in query
    assert "snapshot_count" in query
    assert "latest_price" in query
    assert "min_price" in query
    assert "latest_price_divine" in query
    assert "min_price_divine" in query
    assert "fx_chaos_per_divine" in query
    assert "target_price_divine" in query


def test_build_training_examples_insert_query_uses_listing_episodes() -> None:
    query = sql.build_training_examples_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert f"INSERT INTO {sql.TRAINING_TABLE}" in query
    assert f"INSERT INTO {sql.TRAINING_TABLE} (" in query
    assert ") SELECT" in query
    assert f"FROM {sql.LISTING_EPISODES_TABLE} AS episode" in query
    assert "listing_episode_id" in query
    assert "snapshot_count" in query
    assert "target_fast_sale_24h_price" in query
    assert "target_fast_sale_24h_price_divine" in query
    assert "target_price_divine" in query
    assert "sale_confidence_flag" in query


def test_training_sql_emits_route_and_item_state_search_keys() -> None:
    query = sql.build_training_examples_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert "AS route" in query
    assert "AS item_state_key" in query
    assert "episode.item_state_key AS item_state_key" in query
    assert "episode.corrupted AS corrupted" in query
    assert "episode.fractured AS fractured" in query
    assert "episode.synthesised AS synthesised" in query


def test_training_sql_emits_cohort_identity_projections() -> None:
    query = sql.build_training_examples_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert "AS strategy_family" in query
    assert "AS cohort_key" in query
    assert "AS material_state_signature" in query
    assert "episode.strategy_family AS strategy_family" in query
    assert "episode.cohort_key AS cohort_key" in query
    assert "episode.material_state_signature AS material_state_signature" in query
    assert "episode.fx_chaos_per_divine AS fx_chaos_per_divine" in query


def test_training_sql_strategy_family_uses_family_scope_logic_not_route_alias() -> None:
    query = sql.build_training_examples_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert "episode.strategy_family AS strategy_family" in query


def test_training_sql_emits_target_metadata_projections() -> None:
    query = sql.build_training_examples_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert "toUInt8(episode.snapshot_count >= 2) AS target_likely_sold" in query
    assert "CAST(NULL AS Nullable(Float64)) AS target_time_to_exit_hours" in query
    assert "episode.min_price AS target_sale_price_anchor_chaos" in query
    assert "episode.latest_price_divine AS target_price_divine" in query
    assert "episode.min_price_divine AS target_fast_sale_24h_price_divine" in query


def test_training_sql_keeps_insert_column_order_for_new_contract_fields() -> None:
    query = sql.build_training_examples_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert query.index("strategy_family,") < query.index("cohort_key,")
    assert query.index("cohort_key,") < query.index("material_state_signature,")
    assert query.index("listing_episode_id,") < query.index("first_seen,")
    assert query.index("first_seen,") < query.index("last_seen,")
    assert query.index("last_seen,") < query.index("snapshot_count,")
    assert query.index("target_likely_sold,") < query.index(
        "target_time_to_exit_hours,"
    )
    assert query.index("target_time_to_exit_hours,") < query.index(
        "target_sale_price_anchor_chaos,"
    )


def test_listing_episode_sql_normalizes_chaos_and_divine_prices() -> None:
    query = sql.build_listing_episodes_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert "normalized_price_chaos" in query
    assert "normalized_price_divine" in query
    assert "multiIf(" in query


def test_retrieval_candidate_sql_can_partition_by_route_and_state() -> None:
    query = sql.build_retrieval_candidate_query(
        league="Mirage",
        route="sparse_retrieval",
        item_state_key="rare|corrupted=1|fractured=0|synthesised=0",
    )

    assert "PARTITION BY league, route, item_state_key" in query
    assert "route = 'sparse_retrieval'" in query
    assert "item_state_key = 'rare|corrupted=1|fractured=0|synthesised=0'" in query


def test_retrieval_candidate_sql_includes_identity_and_mod_payload() -> None:
    query = sql.build_retrieval_candidate_query(
        league="Mirage",
        route="sparse_retrieval",
        item_state_key="rare|corrupted=1|fractured=0|synthesised=0",
    )

    assert "identity_key," in query
    assert "mod_features_json" in query


def test_route_sql_fragment_delegates_to_routes_module() -> None:
    query = sql.build_training_examples_insert_query(
        league="Mirage", day=date(2026, 3, 20)
    )

    assert routes.route_sql_expression() in query


def test_sql_select_route_matches_routes_module() -> None:
    parsed = {"category": "cluster_jewel", "rarity": "Rare"}

    assert sql.select_route(parsed) == routes.select_route(parsed)


def test_pricing_benchmark_contract_spec_freezes_non_exchange_columns() -> None:
    spec = sql.pricing_benchmark_contract_spec()

    assert spec["name"] == PRICING_BENCHMARK_CONTRACT.name
    assert spec["confirmation_horizon_hours"] == 48
    assert spec["row_grain"] == "one row per listing episode at first_seen"
    assert "sale_confidence_flag" in spec["allowed_columns"]
    assert "future_snapshot" in spec["forbidden_feature_patterns"]


def test_fast_sale_benchmark_contract_spec_freezes_target_and_split_policy() -> None:
    spec = sql.fast_sale_benchmark_contract_spec()

    assert spec["name"] == "fast_sale_24h_price_benchmark_v1"
    assert spec["target_name"] == "target_fast_sale_24h_price"
    assert spec["candidate_count"] == 3
    assert spec["split_kind"] == "grouped_forward"
    assert spec["tail_metric_quantile"] == 0.9
    assert "target_fast_sale_24h_price" in spec["allowed_columns"]
    assert "future_snapshot" in spec["forbidden_feature_patterns"]


def test_pricing_benchmark_extract_query_filters_non_exchange_routes() -> None:
    query = sql.build_pricing_benchmark_extract_query(
        league="Mirage",
        as_of_ts="2026-03-24 10:00:00",
    )

    assert f"INSERT INTO {sql.BENCHMARK_EXTRACT_TABLE}" in query
    assert (
        "route IN ('cluster_jewel_retrieval', 'structured_boosted', 'structured_boosted_other', 'sparse_retrieval', 'fallback_abstain')"
        in query
    )
    assert "sale_confidence_flag" in query
    assert "target_price_chaos" in query
    assert "ORDER BY as_of_ts ASC, identity_key ASC, item_id ASC" in query
    assert "listing_episode_id" in query


def test_mirage_iron_ring_benchmark_sample_query_uses_branch_view() -> None:
    query = sql.build_mirage_iron_ring_benchmark_sample_query(
        league="Mirage",
        sample_size=10_000,
    )

    assert "FROM poe_trade.v_ml_v3_mirage_iron_ring_item_features_v1" in query
    assert "category = 'ring'" in query
    assert "base_type = 'Iron Ring'" in query
    assert "parsed_amount IS NOT NULL" in query
    assert "parsed_amount > 0" in query
    assert "normalized_affix_hash" in query
    assert "hash_rank = 1" in query
    assert "influence_mask" in query
    assert "catalyst_type" in query
    assert "catalyst_quality" in query
    assert "synth_imp_count" in query
    assert "synth_implicit_mods_json" in query
    assert "corrupted_implicit_mods_json" in query
    assert "veiled_count" in query
    assert "crafted_count" in query
    assert "prefix_count" in query
    assert "suffix_count" in query
    assert "open_prefixes" in query
    assert "open_suffixes" in query
    assert "mod_features_json" in query
    assert "target_price_chaos" in query
    assert "support_count_recent" in query
    assert "affixes" in query
    assert "observed_at AS as_of_ts" in query


def test_mirage_iron_ring_affix_catalog_query_reads_ring_mod_catalog() -> None:
    query = sql.build_mirage_iron_ring_affix_catalog_query()

    assert "FROM poe_trade.ml_ring_mod_catalog_v1" in query
    assert "mod_text_pattern" in query
    assert "mod_base_name" in query
    assert "mod_max_value" in query


def test_lgbm_neo_training_query_targets_the_wide_rare_item_table() -> None:
    query = sql.build_lgbm_neo_training_query()

    assert f"FROM {sql.POE_RARE_ITEM_TRAIN_TABLE}" in query
    assert "price_chaos > 0" in query
    assert "ORDER BY observed_at ASC, item_fingerprint ASC, item_id ASC" in query
    assert "observed_at" in query
    assert "item_fingerprint" in query
    assert "league" in query
    assert "category" in query
    assert "base_type" in query
    assert "has_exp_dex_flat" in query
    assert "val_exp_mana_flat" in query
    assert "has_exp_all_attributes" in query
    assert "has_exp_strength" in query
    assert "has_fract_all_attributes" in query
    assert "has_craft_strength" in query
    assert "has_enchant_intelligence" in query
    assert "support_count_recent" not in query
    assert "strategy_family" not in query
    assert "cohort_key" not in query
    assert "item_state_key" not in query
    assert "base_identity_key" not in query


def test_reference_snapshot_policy_enforces_route_and_category_thresholds() -> None:
    fungible = workflows._reference_snapshot_policy(
        route="fungible_reference",
        category="fossil",
    )
    assert fungible == {
        "target_window_hours": 6,
        "fallback_window_hours": 24,
        "min_support": 100,
    }

    logbook = workflows._reference_snapshot_policy(
        route="fungible_reference",
        category="logbook",
    )
    assert logbook == {
        "target_window_hours": 12,
        "fallback_window_hours": 48,
        "min_support": 40,
    }

    maps = workflows._reference_snapshot_policy(
        route="fallback_abstain",
        category="map",
    )
    assert maps == {
        "target_window_hours": 12,
        "fallback_window_hours": 48,
        "min_support": 40,
    }


def test_reference_snapshot_builder_query_contract_groups_by_cohort_and_window() -> (
    None
):
    query = workflows._build_reference_snapshot_insert_query(
        league="Mirage",
        as_of_ts="2026-03-24 10:00:00",
    )

    assert "INSERT INTO poe_trade.ml_v3_reference_snapshots" in query
    assert "UNION ALL" in query
    assert "'target' AS window_kind" in query
    assert "'fallback' AS window_kind" in query
    assert "category IN ('logbook', 'map')" in query
    assert "route = 'fungible_reference'" in query
    assert "toUInt16(6)" in query
    assert "toUInt16(24)" in query
    assert "toUInt16(12)" in query
    assert "toUInt16(48)" in query
    assert "toUInt32(100)" in query
    assert "toUInt32(40)" in query
    assert (
        "GROUP BY league, route, category, base_type, window_kind, window_hours, min_support"
        in query
    )


def test_reference_snapshot_lookup_uses_parent_route_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_calls: list[str] = []

    responses = [
        [],
        [
            {
                "route": "sparse_retrieval",
                "window_kind": "fallback",
                "window_hours": 48,
                "min_support": 40,
                "support_count_recent": 77,
                "reference_price_p50": 33.0,
                "source_max_as_of_ts": "2026-03-24 08:30:00",
            }
        ],
    ]

    def _fake_query_rows(_client, query: str):
        query_calls.append(query)
        return responses.pop(0)

    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    client = cast(ClickHouseClient, cast(object, _NoopClickHouseClient()))

    payload = workflows._reference_snapshot_lookup(
        client,
        league="Mirage",
        route="fallback_abstain",
        parent_route="sparse_retrieval",
        category="map",
        base_type="T16 Maze Map",
        as_of_ts="2026-03-24 10:00:00",
    )

    assert len(query_calls) == 2
    assert "route = 'fallback_abstain'" in query_calls[0]
    assert "route = 'sparse_retrieval'" in query_calls[1]
    assert payload["hit"] is True
    assert payload["route"] == "sparse_retrieval"
    assert payload["window_kind"] == "fallback"
    assert payload["fallback_reason"] == "parent_snapshot_fallback"
    assert payload["reference_price"] == 33.0


def test_reference_snapshot_lookup_uses_poeninja_when_stash_snapshots_stale_or_thin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        [
            {
                "route": "fungible_reference",
                "window_kind": "target",
                "window_hours": 6,
                "min_support": 100,
                "support_count_recent": 12,
                "reference_price_p50": 14.0,
                "source_max_as_of_ts": "2026-03-23 00:00:00",
            }
        ],
        [
            {
                "route": "fungible_reference",
                "window_kind": "fallback",
                "window_hours": 24,
                "min_support": 100,
                "support_count_recent": 31,
                "reference_price_p50": 13.0,
                "source_max_as_of_ts": "2026-03-23 00:00:00",
            }
        ],
        [
            {
                "chaos_equivalent": 18.0,
                "sample_time_utc": "2026-03-24 09:50:00",
            }
        ],
    ]

    def _fake_query_rows(_client, _query: str):
        return responses.pop(0)

    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    client = cast(ClickHouseClient, cast(object, _NoopClickHouseClient()))

    payload = workflows._reference_snapshot_lookup(
        client,
        league="Mirage",
        route="fungible_reference",
        parent_route="fallback_abstain",
        category="fossil",
        base_type="Jagged Fossil",
        as_of_ts="2026-03-24 10:00:00",
    )

    assert payload["hit"] is True
    assert payload["source"] == "poeninja"
    assert payload["reference_price"] == 18.0
    assert payload["fallback_reason"] == "temporary_poeninja_fallback"


def test_reference_snapshot_lookup_applies_policy_per_candidate_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_calls: list[str] = []
    responses = [
        [],
        [
            {
                "route": "fungible_reference",
                "window_kind": "fallback",
                "window_hours": 24,
                "min_support": 100,
                "support_count_recent": 50,
                "reference_price_p50": 20.0,
                "source_max_as_of_ts": "2026-03-23 00:00:00",
            }
        ],
        [],
        [
            {
                "chaos_equivalent": 22.0,
                "sample_time_utc": "2026-03-24 09:59:00",
            }
        ],
    ]

    def _fake_query_rows(_client, query: str):
        query_calls.append(query)
        return responses.pop(0)

    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    client = cast(ClickHouseClient, cast(object, _NoopClickHouseClient()))

    payload = workflows._reference_snapshot_lookup(
        client,
        league="Mirage",
        route="fallback_abstain",
        parent_route="fungible_reference",
        category="fossil",
        base_type="Jagged Fossil",
        as_of_ts="2026-03-24 10:00:00",
    )

    assert "route = 'fallback_abstain'" in query_calls[0]
    assert "route = 'fungible_reference'" in query_calls[1]
    assert payload["source"] == "poeninja"
    assert payload["reference_price"] == 22.0


def test_reference_snapshot_lookup_constrains_snapshot_as_of_ts_no_future_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []

    def _fake_query_rows(_client, query: str):
        queries.append(query)
        return []

    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    client = cast(ClickHouseClient, cast(object, _NoopClickHouseClient()))

    _ = workflows._reference_snapshot_lookup(
        client,
        league="Mirage",
        route="fungible_reference",
        parent_route="fallback_abstain",
        category="fossil",
        base_type="Jagged Fossil",
        as_of_ts="2026-03-24 10:00:00",
    )

    assert queries
    assert (
        "snapshot_as_of_ts <= toDateTime64('2026-03-24 10:00:00', 3, 'UTC')"
        in queries[0]
    )


def test_reference_snapshot_row_usability_rejects_future_and_stale_rows() -> None:
    base_row = {
        "support_count_recent": 120,
        "reference_price_p50": 15.0,
    }

    assert (
        workflows._reference_snapshot_row_is_usable(
            {
                **base_row,
                "source_max_as_of_ts": "2026-03-24 10:30:00",
            },
            as_of_ts="2026-03-24 10:00:00",
            required_min_support=100,
            required_window_hours=24,
        )
        is False
    )

    assert (
        workflows._reference_snapshot_row_is_usable(
            {
                **base_row,
                "source_max_as_of_ts": "2026-03-23 07:59:59",
            },
            as_of_ts="2026-03-24 10:00:00",
            required_min_support=100,
            required_window_hours=24,
        )
        is False
    )
