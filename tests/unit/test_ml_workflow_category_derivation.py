from __future__ import annotations

from typing import cast

import pytest

from poe_trade.ml import workflows


@pytest.mark.parametrize(
    ("item_class", "base_type", "expected"),
    [
        ("Jewels", "Crimson Jewel", "jewel"),
        ("Abyss Jewels", "Searching Eye Jewel", "jewel"),
        ("Rings", "Two-Stone Ring", "ring"),
        ("Amulets", "Onyx Amulet", "amulet"),
        ("Belts", "Leather Belt", "belt"),
        ("Maps", "Cemetery Map", "map"),
    ],
)
def test_derive_category_splits_dominant_other_families(
    item_class: str, base_type: str, expected: str
) -> None:
    assert (
        workflows._derive_category(
            "other",
            item_class=item_class,
            base_type=base_type,
            item_type_line=base_type,
        )
        == expected
    )


def test_derive_category_keeps_cluster_jewel_specificity() -> None:
    assert (
        workflows._derive_category(
            "other",
            item_class="Jewels",
            base_type="Large Cluster Jewel",
            item_type_line="Large Cluster Jewel",
        )
        == "cluster_jewel"
    )


def test_parse_clipboard_item_uses_derived_category_for_jewel_family() -> None:
    parsed = workflows._parse_clipboard_item(
        "\n".join(
            [
                "Item Class: Jewels",
                "Rarity: Magic",
                "Crimson Jewel",
                "--------",
                "Item Level: 84",
            ]
        )
    )

    assert parsed["category"] == "jewel"


def test_build_dataset_uses_derived_category_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed_queries: list[str] = []

    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del settings
            executed_queries.append(query)
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))

    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(workflows, "_ensure_dataset_table", lambda *_args: None)
    monkeypatch.setattr(workflows, "_ensure_mod_tables", lambda *_args: None)
    monkeypatch.setattr(
        workflows, "_ensure_route_candidates_table", lambda *_args: None
    )
    monkeypatch.setattr(workflows, "_ensure_no_leakage_audit", lambda *_args: None)
    monkeypatch.setattr(workflows, "_write_leakage_audit", lambda *_args: None)
    monkeypatch.setattr(
        workflows,
        "_populate_item_mod_features_from_tokens",
        lambda *_args, **_kwargs: {"rows_written": 0, "non_empty_rows": 0},
    )
    monkeypatch.setattr(workflows, "_scalar_count", lambda *_args, **_kwargs: 0)

    workflows.build_dataset(
        client,
        league="Mirage",
        as_of_ts="2026-03-10T12:00:00Z",
        output_table="poe_trade.ml_price_dataset_v1",
    )

    dataset_queries = [
        query
        for query in executed_queries
        if "INSERT INTO poe_trade.ml_price_dataset_v1" in query
    ]
    assert dataset_queries
    assert " AS category," in dataset_queries[0]
    assert "AS category, labels.normalized_price_chaos" in dataset_queries[0]
    assert "'jewel'" in dataset_queries[0]
    assert "'ring'" in dataset_queries[0]
    assert "'amulet'" in dataset_queries[0]
    assert "'belt'" in dataset_queries[0]
    assert "'map'" in dataset_queries[0]


@pytest.mark.parametrize(
    ("raw_category", "expected"),
    [
        ("jewel", "other"),
        ("ring", "other"),
        ("amulet", "other"),
        ("belt", "other"),
        ("cluster_jewel", "cluster_jewel"),
        ("map", "map"),
        ("other", "other"),
    ],
)
def test_canonical_model_category_soft_reverts_split_families(
    raw_category: str, expected: str
) -> None:
    assert workflows._canonical_model_category(raw_category) == expected


def test_feature_dict_from_row_uses_canonical_model_category() -> None:
    row = {
        "category": "jewel",
        "base_type": "Crimson Jewel",
        "rarity": "Rare",
        "ilvl": 84,
        "stack_size": 1,
        "corrupted": 0,
        "fractured": 0,
        "synthesised": 0,
        "mod_token_count": 4,
        "mod_features_json": "{}",
    }
    features = workflows._feature_dict_from_row(row)
    assert features["category"] == "other"


def test_dataset_rebuild_window_is_stable_for_unchanged_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del query, settings
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))

    label_row = {
        "row_count": 200,
        "min_as_of_ts": "2026-03-10 00:00:00",
        "max_as_of_ts": "2026-03-10 01:00:00",
        "digest_sum": "111",
        "digest_max": "222",
    }
    trade_row = {
        "row_count": 20,
        "max_retrieved_at": "2026-03-10 01:30:00",
    }

    def _fake_query_rows(_client, query: str):
        if "FROM poe_trade.ml_price_labels_v1" in query:
            return [dict(label_row)]
        if "FROM poe_trade.bronze_trade_metadata" in query:
            return [dict(trade_row)]
        return []

    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(
        workflows,
        "_ensure_price_labels_table",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)

    first = workflows.dataset_rebuild_window(client, league="Mirage")
    second = workflows.dataset_rebuild_window(client, league="Mirage")

    assert first["window_id"] == second["window_id"]
    assert first["label_rows"] == 200
    assert first["trade_metadata_rows"] == 20


def test_dataset_rebuild_window_changes_when_snapshot_digest_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del query, settings
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))

    label_row = {
        "row_count": 200,
        "min_as_of_ts": "2026-03-10 00:00:00",
        "max_as_of_ts": "2026-03-10 01:00:00",
        "digest_sum": "111",
        "digest_max": "222",
    }
    trade_row = {
        "row_count": 20,
        "max_retrieved_at": "2026-03-10 01:30:00",
    }

    def _fake_query_rows(_client, query: str):
        if "FROM poe_trade.ml_price_labels_v1" in query:
            return [dict(label_row)]
        if "FROM poe_trade.bronze_trade_metadata" in query:
            return [dict(trade_row)]
        return []

    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(
        workflows,
        "_ensure_price_labels_table",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)

    before = workflows.dataset_rebuild_window(client, league="Mirage")
    label_row["digest_sum"] = "999"
    after = workflows.dataset_rebuild_window(client, league="Mirage")

    assert before["window_id"] != after["window_id"]


def test_route_slice_id_changes_when_holdout_content_changes() -> None:
    rows_a = [
        {
            "as_of_ts": "2026-03-10 00:00:00",
            "category": "map",
            "base_type": "Cemetery Map",
            "rarity": "Rare",
            "ilvl": 80,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 2,
            "normalized_price_chaos": 10.0,
            "sale_probability_label": 0.5,
        },
        {
            "as_of_ts": "2026-03-10 01:00:00",
            "category": "map",
            "base_type": "Cemetery Map",
            "rarity": "Rare",
            "ilvl": 80,
            "stack_size": 1,
            "corrupted": 0,
            "fractured": 0,
            "synthesised": 0,
            "mod_token_count": 2,
            "normalized_price_chaos": 11.0,
            "sale_probability_label": 0.5,
        },
    ]
    rows_b = [dict(row) for row in rows_a]
    rows_b[1]["normalized_price_chaos"] = 99.0

    slice_a = workflows._route_slice_id("structured_boosted", rows_a)
    slice_b = workflows._route_slice_id("structured_boosted", rows_b)

    assert slice_a != slice_b
