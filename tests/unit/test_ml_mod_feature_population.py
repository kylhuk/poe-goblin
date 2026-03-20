from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import cast

from poe_trade.ml import workflows


def test_mod_features_from_tokens_emits_expected_key_shape():
    payload = workflows._mod_features_from_tokens(
        [
            "+55 to Strength",
            "+96 to maximum Life",
            "+34% to Fire Resistance",
            "+14% increased Attack Speed",
        ]
    )

    assert "Strength_tier" in payload
    assert "Strength_roll" in payload
    assert "MaximumLife_tier" in payload
    assert "MaximumLife_roll" in payload
    assert "FireResistance_tier" in payload
    assert "FireResistance_roll" in payload
    assert "AttackSpeed_tier" in payload
    assert "AttackSpeed_roll" in payload
    assert payload["Strength_tier"] >= 1
    assert 0.0 < payload["Strength_roll"] <= 1.0


def test_mod_features_from_tokens_handles_observed_real_token_shapes():
    payload = workflows._mod_features_from_tokens(
        [
            "30% increased movement speed",
            "10% increased attack speed",
            "+10% to all elemental resistances",
            "+28 to maximum life",
            "+23% to chaos resistance",
            "adds 1 to 4 physical damage to attacks",
        ]
    )

    assert payload["MovementSpeed_tier"] >= 1
    assert 0.0 < payload["MovementSpeed_roll"] <= 1.0
    assert payload["AttackSpeed_tier"] >= 1
    assert 0.0 < payload["AttackSpeed_roll"] <= 1.0
    assert payload["AllElementalResistances_tier"] >= 1
    assert 0.0 < payload["AllElementalResistances_roll"] <= 1.0
    assert payload["MaximumLife_tier"] >= 1
    assert 0.0 < payload["MaximumLife_roll"] <= 1.0
    assert payload["ChaosResistance_tier"] >= 1
    assert 0.0 < payload["ChaosResistance_roll"] <= 1.0
    assert payload["PhysicalDamage_tier"] >= 1
    assert 0.0 < payload["PhysicalDamage_roll"] <= 1.0


def test_populate_item_mod_features_scopes_refresh_to_requested_league(monkeypatch):
    token_pages = [
        [
            {
                "item_id": "item-a",
                "mod_tokens": ["+55 to strength", "+96 to maximum life"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            },
            {
                "item_id": "item-b",
                "mod_tokens": ["adds 7 to 14 fire damage to attacks"],
                "max_as_of_ts": "2026-03-18 00:01:00",
            },
        ],
        [],
    ]
    inserted_batches: list[list[dict[str, Any]]] = []

    class _DummyClient:
        def __init__(self) -> None:
            self.executed_queries: list[str] = []

        def execute(self, query: str) -> str:
            self.executed_queries.append(query)
            return ""

    client = _DummyClient()

    def _fake_query_rows(_client, _query: str):
        return token_pages.pop(0)

    def _fake_insert(_client, _table: str, rows: list[dict[str, Any]]):
        inserted_batches.append(rows)

    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    result = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, client)),
        league="Mirage",
        page_size=100,
    )

    delete_queries = [
        query
        for query in client.executed_queries
        if "ALTER TABLE poe_trade.ml_item_mod_features_v1" in query
        and "DELETE WHERE" in query
    ]
    assert len(delete_queries) == 1
    assert "league = 'Mirage'" in delete_queries[0]
    assert all(
        "TRUNCATE TABLE poe_trade.ml_item_mod_features_v1" not in query
        for query in client.executed_queries
    )
    assert result["rows_written"] == 2
    assert result["non_empty_rows"] == 2
    assert len(inserted_batches) == 1

    first_row = inserted_batches[0][0]
    second_row = inserted_batches[0][1]
    assert first_row["mod_features_json"] != "{}"
    assert second_row["mod_features_json"] != "{}"
    assert "_tier" in first_row["mod_features_json"]
    assert "_roll" in first_row["mod_features_json"]


def test_populate_item_mod_features_preserves_token_order_and_duplicates(monkeypatch):
    token_pages = [
        [
            {
                "item_id": "item-order",
                "mod_tokens": [
                    "+55 to strength",
                    "+55 to strength",
                    "+96 to maximum life",
                ],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ],
        [],
    ]
    seen_tokens: list[list[str]] = []

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, _query: str):
        return token_pages.pop(0)

    def _fake_insert(_client, _table: str, _rows: list[dict[str, Any]]):
        return None

    def _fake_mod_features(tokens: list[str]) -> dict[str, Any]:
        seen_tokens.append(tokens)
        return {"sentinel_tier": 1, "sentinel_roll": 1.0}

    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)
    monkeypatch.setattr(workflows, "_mod_features_from_tokens", _fake_mod_features)

    _ = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=10,
    )

    assert seen_tokens == [
        ["+55 to strength", "+55 to strength", "+96 to maximum life"]
    ]


def test_populate_item_mod_features_advances_cursor_monotonically(monkeypatch):
    token_pages = [
        [
            {
                "item_id": "item-001",
                "mod_tokens": ["+10 to strength"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            },
            {
                "item_id": "item-002",
                "mod_tokens": ["+20 to strength"],
                "max_as_of_ts": "2026-03-18 00:00:01",
            },
        ],
        [
            {
                "item_id": "item-003",
                "mod_tokens": ["+30 to strength"],
                "max_as_of_ts": "2026-03-18 00:00:02",
            }
        ],
        [],
    ]
    observed_queries: list[str] = []

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, query: str):
        observed_queries.append(query)
        return token_pages.pop(0)

    def _fake_insert(_client, _table: str, _rows: list[dict[str, Any]]):
        return None

    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    _ = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=2,
    )

    assert "AND item_id > ''" in observed_queries[0]
    assert "AND item_id > 'item-002'" in observed_queries[1]
    assert "AND item_id > 'item-003'" in observed_queries[2]


def test_populate_item_mod_features_retries_legacy_page_on_memory_limit(monkeypatch):
    token_pages = [
        [
            {
                "item_id": "item-001",
                "mod_tokens": ["+10 to strength"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ],
        [],
    ]
    observed_queries: list[str] = []
    failed_once = {"value": False}

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, query: str):
        observed_queries.append(query)
        if (
            "LIMIT 1000" in query
            and "max_memory_usage=1500000000" in query
            and not failed_once["value"]
        ):
            failed_once["value"] = True
            raise workflows.ClickHouseClientError(
                "Code: 241. DB::Exception: MEMORY_LIMIT_EXCEEDED"
            )
        return token_pages.pop(0)

    def _fake_insert(_client, _table: str, _rows: list[dict[str, Any]]):
        return None

    monkeypatch.setenv("POE_ML_MOD_FEATURE_FALLBACK_PAGE_SIZE_CAP", "1000")
    monkeypatch.setenv("POE_ML_MOD_FEATURE_FALLBACK_MAX_MEMORY_USAGE", "1500000000")
    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    result = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=5000,
    )

    assert failed_once["value"] is True
    assert any("LIMIT 1000" in query for query in observed_queries)
    assert any("LIMIT 500" in query for query in observed_queries)
    assert result["rows_written"] == 1


def test_populate_item_mod_features_uses_max_as_of_ts_fallback(monkeypatch):
    token_pages = [
        [
            {
                "item_id": "item-ts-a",
                "mod_tokens": ["+10 to maximum life"],
                "max_as_of_ts": "2026-03-18 08:00:00",
            },
            {
                "item_id": "item-ts-b",
                "mod_tokens": ["+20 to maximum life"],
            },
        ],
        [],
    ]
    inserted_rows: list[dict[str, Any]] = []

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, _query: str):
        return token_pages.pop(0)

    def _fake_insert(_client, _table: str, rows: list[dict[str, Any]]):
        inserted_rows.extend(rows)

    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    _ = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=100,
    )

    assert len(inserted_rows) == 2
    assert inserted_rows[0]["as_of_ts"] == "2026-03-18 08:00:00"
    assert inserted_rows[1]["as_of_ts"] == inserted_rows[1]["updated_at"]


def test_populate_item_mod_features_shadow_mode_reports_mismatches(
    monkeypatch, tmp_path: Path
):
    legacy_pages = [
        [
            {
                "item_id": "item-shadow",
                "mod_tokens": ["a", "b"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ],
        [],
    ]
    rollup_pages = [
        [
            {
                "item_id": "item-shadow",
                "mod_tokens": ["b", "a"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ]
    ]
    inserted_rows: list[dict[str, Any]] = []
    queried_sql: list[str] = []

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, query: str):
        queried_sql.append(query)
        if "ml_item_mod_feature_states_v1" in query:
            return rollup_pages.pop(0)
        return legacy_pages.pop(0)

    def _fake_insert(_client, _table: str, rows: list[dict[str, Any]]):
        inserted_rows.extend(rows)

    shadow_report_path = tmp_path / "shadow-report.json"
    monkeypatch.setenv("POE_ML_MOD_ROLLUP_SHADOW_ENABLED", "true")
    monkeypatch.setenv("POE_ML_MOD_ROLLUP_SHADOW_REPORT_PATH", str(shadow_report_path))
    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    result = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=100,
    )

    assert any("ml_item_mod_tokens_v1" in query for query in queried_sql)
    assert any("ml_item_mod_feature_states_v1" in query for query in queried_sql)
    assert len(inserted_rows) == 1
    assert result["rows_written"] == 1
    assert result["shadow_mismatch_count"] == 1
    report_payload = json.loads(shadow_report_path.read_text(encoding="utf-8"))
    assert report_payload["status"] == "mismatch"
    assert report_payload["shadow"]["comparison_mode"] == "strict"
    assert report_payload["shadow"]["mismatch_count"] == 1


def test_populate_item_mod_features_shadow_mode_passes_when_rollup_matches(monkeypatch, tmp_path: Path):
    legacy_pages = [
        [
            {
                "item_id": "item-shadow",
                "mod_tokens": ["a", "b"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ],
        [],
    ]
    rollup_pages = [
        [
            {
                "item_id": "item-shadow",
                "mod_tokens": ["a", "b"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ],
        [],
    ]
    inserted_rows: list[dict[str, Any]] = []
    queried_sql: list[str] = []

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, query: str):
        queried_sql.append(query)
        if "ml_item_mod_feature_states_v1" in query:
            return rollup_pages.pop(0)
        return legacy_pages.pop(0)

    def _fake_insert(_client, _table: str, rows: list[dict[str, Any]]):
        inserted_rows.extend(rows)

    shadow_report_path = tmp_path / "shadow-match-report.json"
    monkeypatch.setenv("POE_ML_MOD_ROLLUP_SHADOW_ENABLED", "true")
    monkeypatch.setenv("POE_ML_MOD_ROLLUP_SHADOW_REPORT_PATH", str(shadow_report_path))
    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    result = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=100,
    )

    assert any("ml_item_mod_feature_states_v1" in query for query in queried_sql)
    assert len(inserted_rows) == 1
    assert result["shadow_mismatch_count"] == 0
    report_payload = json.loads(shadow_report_path.read_text(encoding="utf-8"))
    assert report_payload["status"] == "ok"
    assert report_payload["shadow"]["mismatch_count"] == 0


def test_populate_item_mod_features_shadow_mode_multiset_treats_reorder_as_match(
    monkeypatch, tmp_path: Path
):
    legacy_pages = [
        [
            {
                "item_id": "item-shadow",
                "mod_tokens": ["a", "b"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ],
        [],
    ]
    rollup_pages = [
        [
            {
                "item_id": "item-shadow",
                "mod_tokens": ["b", "a"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ]
    ]

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, query: str):
        if "ml_item_mod_feature_states_v1" in query:
            return rollup_pages.pop(0)
        return legacy_pages.pop(0)

    def _fake_insert(_client, _table: str, _rows: list[dict[str, Any]]):
        return None

    shadow_report_path = tmp_path / "shadow-report-multiset.json"
    monkeypatch.setenv("POE_ML_MOD_ROLLUP_SHADOW_ENABLED", "true")
    monkeypatch.setenv("POE_ML_MOD_ROLLUP_SHADOW_COMPARISON_MODE", "multiset")
    monkeypatch.setenv("POE_ML_MOD_ROLLUP_SHADOW_REPORT_PATH", str(shadow_report_path))
    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    result = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=100,
    )

    assert result["shadow_mismatch_count"] == 0
    report_payload = json.loads(shadow_report_path.read_text(encoding="utf-8"))
    assert report_payload["status"] == "ok"
    assert report_payload["shadow"]["comparison_mode"] == "multiset"


def test_populate_item_mod_features_force_legacy_fallback_applies_limits(monkeypatch):
    token_pages = [
        [
            {
                "item_id": "item-fallback",
                "mod_tokens": ["+10 to life"],
                "max_as_of_ts": "2026-03-18 00:00:00",
            }
        ],
        [],
    ]
    observed_queries: list[str] = []

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return ""

    def _fake_query_rows(_client, query: str):
        observed_queries.append(query)
        return token_pages.pop(0)

    def _fake_insert(_client, _table: str, _rows: list[dict[str, Any]]):
        return None

    monkeypatch.setenv("POE_ML_MOD_ROLLUP_FORCE_LEGACY", "true")
    monkeypatch.setenv("POE_ML_MOD_FEATURE_FALLBACK_PAGE_SIZE_CAP", "1000")
    monkeypatch.setenv("POE_ML_MOD_FEATURE_FALLBACK_MAX_MEMORY_USAGE", "1610612736")
    monkeypatch.setenv("POE_ML_MOD_FEATURE_FALLBACK_MAX_THREADS", "4")
    monkeypatch.setenv("POE_ML_MOD_FEATURE_FALLBACK_MAX_EXECUTION_TIME", "180")
    monkeypatch.setattr(workflows, "_ensure_mod_feature_table", lambda _client: None)
    monkeypatch.setattr(workflows, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(workflows, "_insert_json_rows", _fake_insert)

    result = workflows._populate_item_mod_features_from_tokens(
        cast(workflows.ClickHouseClient, cast(object, _DummyClient())),
        league="Mirage",
        page_size=5000,
    )

    assert result["fallback"]["active"] is True
    assert result["fallback"]["page_size_cap"] == 1000
    assert "LIMIT 1000" in observed_queries[0]
    assert "SETTINGS" in observed_queries[0]
    assert "max_memory_usage=1610612736" in observed_queries[0]
    assert "max_threads=4" in observed_queries[0]
    assert "max_execution_time=180" in observed_queries[0]


def test_sql_mod_feature_insert_query_avoids_limit_offset_loops() -> None:
    sql = workflows._build_sql_mod_feature_insert_query(league="Mirage")

    assert "INSERT INTO poe_trade.ml_item_mod_features_v1" in sql
    assert "FROM poe_trade.ml_item_mod_tokens_v1" in sql
    assert "mapFromArrays" in sql
    assert "LIMIT" not in sql
    assert "OFFSET" not in sql


def test_populate_item_mod_features_prefers_sql_primary(monkeypatch):
    observed: list[tuple[str, str]] = []

    def _fake_sql(_client, *, league: str):
        observed.append(("sql", league))
        return {"rows_written": 2, "non_empty_rows": 2, "mode": "sql_primary"}

    def _fake_legacy(_client, *, league: str, page_size: int = workflows._MOD_FEATURE_BATCH_SIZE):
        observed.append(("legacy", league))
        return {"rows_written": 1, "non_empty_rows": 1}

    monkeypatch.setattr(workflows, "_populate_item_mod_features_from_tokens_sql", _fake_sql)
    monkeypatch.setattr(workflows, "_populate_item_mod_features_from_tokens", _fake_legacy)

    result = workflows._populate_item_mod_features(
        cast(workflows.ClickHouseClient, cast(object, object())),
        league="Mirage",
    )

    assert result["mode"] == "sql_primary"
    assert observed == [("sql", "Mirage")]


def test_populate_item_mod_features_force_legacy_switches_dispatch(monkeypatch):
    observed: list[tuple[str, str]] = []

    def _fake_sql(_client, *, league: str):
        observed.append(("sql", league))
        return {"rows_written": 2, "non_empty_rows": 2, "mode": "sql_primary"}

    def _fake_legacy(_client, *, league: str, page_size: int = workflows._MOD_FEATURE_BATCH_SIZE):
        observed.append(("legacy", league))
        return {"rows_written": 1, "non_empty_rows": 1}

    monkeypatch.setenv("POE_ML_MOD_ROLLUP_FORCE_LEGACY", "true")
    monkeypatch.setattr(workflows, "_populate_item_mod_features_from_tokens_sql", _fake_sql)
    monkeypatch.setattr(workflows, "_populate_item_mod_features_from_tokens", _fake_legacy)

    result = workflows._populate_item_mod_features(
        cast(workflows.ClickHouseClient, cast(object, object())),
        league="Mirage",
    )

    assert result["mode"] == "legacy_fallback"
    assert observed == [("legacy", "Mirage")]
