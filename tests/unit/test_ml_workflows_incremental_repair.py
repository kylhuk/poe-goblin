from __future__ import annotations

from typing import cast

import pytest

from poe_trade.ml import workflows


def test_repair_incremental_price_dataset_v2_inserts_only_missing_rows(
    monkeypatch,
) -> None:
    executed_queries: list[str] = []

    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del settings
            executed_queries.append(query)
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))
    scalar_results = iter([3, 0])

    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(
        workflows,
        "_scalar_count",
        lambda *_args, **_kwargs: next(scalar_results),
    )

    result = workflows.repair_incremental_price_dataset_v2(client, league="Mirage")

    assert result["rows_repaired"] == 3
    assert result["missing_before"] == 3
    assert result["missing_after"] == 0
    insert_queries = [query for query in executed_queries if "INSERT INTO" in query]
    assert len(insert_queries) == 1
    assert "FROM poe_trade.ml_price_labels_v2 AS labels" in insert_queries[0]
    assert "NOT EXISTS ( SELECT 1 FROM poe_trade.ml_price_dataset_v2 AS dataset" in insert_queries[0]
    assert "route_reason" in insert_queries[0]


def test_repair_incremental_price_dataset_v2_skips_when_no_gap(
    monkeypatch,
) -> None:
    executed_queries: list[str] = []

    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del settings
            executed_queries.append(query)
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))

    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(workflows, "_scalar_count", lambda *_args, **_kwargs: 0)

    result = workflows.repair_incremental_price_dataset_v2(client, league="Mirage")

    assert result["rows_repaired"] == 0
    assert result["missing_before"] == 0
    assert result["missing_after"] == 0
    assert not executed_queries


def test_repair_incremental_price_labels_v2_repairs_missing_fx_rows(
    monkeypatch,
) -> None:
    executed_queries: list[str] = []

    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del settings
            executed_queries.append(query)
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))
    scalar_results = iter([4, 0])

    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(
        workflows,
        "_scalar_count",
        lambda *_args, **_kwargs: next(scalar_results),
    )

    result = workflows.repair_incremental_price_labels_v2(client, league="Mirage")

    assert result["rows_repaired"] == 4
    assert result["missing_fx_before"] == 4
    assert result["missing_fx_after"] == 0
    assert any("ALTER TABLE poe_trade.ml_price_labels_v2 DELETE" in query for query in executed_queries)
    insert_queries = [query for query in executed_queries if "INSERT INTO poe_trade.ml_price_labels_v2" in query]
    assert len(insert_queries) == 1
    assert "replaceRegexpAll(lowerUTF8(trimBoth(fx.currency)), '\\s+orbs?$', '')" in insert_queries[0]
    assert (
        "replaceRegexpAll(replaceRegexpAll(lowerUTF8(trimBoth(items.parsed_currency)), "
        "'\\s+', ' '), '\\s+orbs?$', '') IN ('exa', 'exalt', 'exalted', 'exalts')"
        in insert_queries[0]
    )
    assert "'orb of alchemy'" in insert_queries[0]
    assert "'gemcutter''s prism'" in insert_queries[0]
    assert "labels.normalization_source != 'missing_fx'" in insert_queries[0]


def test_repair_incremental_price_labels_v2_skips_when_no_repairable_rows(
    monkeypatch,
) -> None:
    executed_queries: list[str] = []

    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del settings
            executed_queries.append(query)
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))

    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)
    monkeypatch.setattr(workflows, "_scalar_count", lambda *_args, **_kwargs: 0)

    result = workflows.repair_incremental_price_labels_v2(client, league="Mirage")

    assert result["rows_repaired"] == 0
    assert result["missing_fx_before"] == 0
    assert result["missing_fx_after"] == 0
    assert not executed_queries


def test_repair_incremental_price_dataset_v2_rejects_non_v2_tables(
    monkeypatch,
) -> None:
    class StubClient:
        def execute(self, query: str, settings=None) -> str:
            del query, settings
            return ""

    client = cast(workflows.ClickHouseClient, cast(object, StubClient()))
    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)

    with pytest.raises(ValueError, match="labels_v2"):
        workflows.repair_incremental_price_dataset_v2(
            client,
            league="Mirage",
            labels_table="poe_trade.ml_price_labels_v1",
        )

    with pytest.raises(ValueError, match="dataset_v2"):
        workflows.repair_incremental_price_dataset_v2(
            client,
            league="Mirage",
            dataset_table="poe_trade.ml_price_dataset_v1",
        )
