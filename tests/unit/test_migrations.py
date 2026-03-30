from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from poe_trade.db.migrations import (
    Migration,
    MigrationRunner,
    MigrationStatus,
    _resolve_migrations_dir,
)


class RecordingClient:
    def __init__(self, payload: str = "", responses: list[str] | None = None) -> None:
        self.payload = payload
        self.responses = list(responses or [])
        self.queries: list[str] = []
        self.settings: list[dict[str, str] | None] = []

    def execute(self, query: str, settings: dict[str, str] | None = None) -> str:
        self.queries.append(query)
        self.settings.append(settings)
        if self.responses:
            return self.responses.pop(0)
        return self.payload


def test_source_checkout_resolves_repo_schema(tmp_path: Path) -> None:
    module_path = tmp_path / "repo" / "poe_trade" / "db" / "migrations.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    repo_schema = tmp_path / "repo" / "schema" / "migrations"
    repo_schema.mkdir(parents=True, exist_ok=True)

    assert _resolve_migrations_dir(module_path) == repo_schema


def test_installed_package_uses_package_schema(tmp_path: Path) -> None:
    site_packages = tmp_path / "python" / "lib" / "python3.12" / "site-packages"
    module_path = site_packages / "poe_trade" / "db" / "migrations.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    package_schema = site_packages / "poe_trade" / "schema" / "migrations"
    package_schema.mkdir(parents=True, exist_ok=True)

    assert _resolve_migrations_dir(module_path) == package_schema


def test_installed_package_falls_back_to_cwd_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site_packages = tmp_path / "python" / "lib" / "python3.12" / "site-packages"
    module_path = site_packages / "poe_trade" / "db" / "migrations.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    cwd_schema = tmp_path / "schema" / "migrations"
    cwd_schema.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

    assert _resolve_migrations_dir(module_path) == cwd_schema


def test_installed_package_prefers_package_schema_when_both_exist(
    tmp_path: Path,
) -> None:
    site_packages = tmp_path / "python" / "lib" / "python3.12" / "site-packages"
    module_path = site_packages / "poe_trade" / "db" / "migrations.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    package_schema = site_packages / "poe_trade" / "schema" / "migrations"
    package_schema.mkdir(parents=True, exist_ok=True)
    global_schema = site_packages / "schema" / "migrations"
    global_schema.mkdir(parents=True, exist_ok=True)

    assert _resolve_migrations_dir(module_path) == package_schema


def test_missing_paths_reports_attempted_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = tmp_path / "env" / "poe_trade" / "db" / "migrations.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path / "missing-cwd")

    with pytest.raises(RuntimeError) as excinfo:
        _resolve_migrations_dir(module_path)

    message = str(excinfo.value)
    assert "Migrations directory missing" in message
    assert "Checked:" in message


def test_split_sql_statements_skips_empty_chunks() -> None:
    sql = "CREATE DATABASE IF NOT EXISTS poe_trade;\n\nCREATE TABLE IF NOT EXISTS poe_trade.demo (id UInt8);\n"

    statements = MigrationRunner._split_sql_statements(sql)

    assert statements == [
        "CREATE DATABASE IF NOT EXISTS poe_trade",
        "CREATE TABLE IF NOT EXISTS poe_trade.demo (id UInt8)",
    ]


def test_split_sql_statements_handles_line_comment_semicolons() -> None:
    sql = "SELECT 1; -- ignore ; inside comment\nSELECT 2;"

    statements = MigrationRunner._split_sql_statements(sql)

    assert statements == [
        "SELECT 1",
        "-- ignore ; inside comment\nSELECT 2",
    ]


def test_split_sql_statements_handles_block_comment_semicolons() -> None:
    sql = "SELECT 1 /* block ; comment */;\nSELECT 2;"

    statements = MigrationRunner._split_sql_statements(sql)

    assert statements == [
        "SELECT 1 /* block ; comment */",
        "SELECT 2",
    ]


def test_split_sql_statements_handles_quoted_semicolons() -> None:
    sql = "SELECT ';';\nSELECT \"semi;colon\";\nSELECT `ident;ifier`;"

    statements = MigrationRunner._split_sql_statements(sql)

    assert statements == [
        "SELECT ';'",
        'SELECT "semi;colon"',
        "SELECT `ident;ifier`",
    ]


def test_apply_bootstraps_metadata_before_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MigrationRunner(
        client=cast(Any, RecordingClient()),
        database="poe_trade",
        dry_run=False,
    )
    order: list[str] = []

    monkeypatch.setattr(
        runner, "_ensure_metadata_table", lambda: order.append("ensure")
    )

    def fake_status() -> list[MigrationStatus]:
        order.append("status")
        return []

    monkeypatch.setattr(runner, "status", fake_status)

    runner.apply()

    assert order == ["ensure", "status"]


def test_apply_executes_each_statement_and_records_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = RecordingClient()
    runner = MigrationRunner(
        client=cast(Any, client),
        database="poe_trade",
        dry_run=False,
    )
    migration = Migration(
        version="0001",
        description="meta",
        path=tmp_path / "0001_meta.sql",
        sql="CREATE DATABASE IF NOT EXISTS poe_trade;\nCREATE TABLE IF NOT EXISTS poe_trade.demo (id UInt8);",
        checksum="abc123",
    )
    recorded: list[str] = []

    monkeypatch.setattr(runner, "_ensure_metadata_table", lambda: None)
    monkeypatch.setattr(
        runner,
        "status",
        lambda: [
            MigrationStatus(migration=migration, applied=False, checksum_match=True)
        ],
    )
    monkeypatch.setattr(runner, "_record_applied", lambda m: recorded.append(m.version))

    runner.apply()

    assert client.queries == [
        "CREATE DATABASE IF NOT EXISTS poe_trade",
        "CREATE TABLE IF NOT EXISTS poe_trade.demo (id UInt8)",
    ]
    assert client.settings == [
        {"prefer_column_name_to_alias": "1"},
        {"prefer_column_name_to_alias": "1"},
    ]
    assert recorded == ["0001"]


def test_apply_records_already_materialized_train_restore_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = RecordingClient(
        responses=[
            '{"row_count":259702,"min_observed_at":"2026-03-14 17:45:40.484","max_observed_at":"2026-03-27 19:21:59.825","fingerprint_sum":14192855530119660083}',
            '{"row_count":259702,"min_observed_at":"2026-03-14 17:45:40.484","max_observed_at":"2026-03-27 19:21:59.825","fingerprint_sum":14192855530119660083}',
        ]
    )
    runner = MigrationRunner(
        client=cast(Any, client),
        database="poe_trade",
        dry_run=False,
    )
    migration = Migration(
        version="0085",
        description="poe rare item train restore temporal context",
        path=Path("/tmp/0085_poe_rare_item_train_restore_temporal_context.sql"),
        sql="CREATE TABLE poe_trade.poe_rare_item_train_v3 ...",
        checksum="abc123",
    )
    recorded: list[str] = []

    monkeypatch.setattr(runner, "_ensure_metadata_table", lambda: None)
    monkeypatch.setattr(
        runner,
        "status",
        lambda: [
            MigrationStatus(migration=migration, applied=False, checksum_match=True)
        ],
    )
    monkeypatch.setattr(runner, "_record_applied", lambda m: recorded.append(m.version))

    runner.apply()

    assert len(client.queries) == 2
    assert "poe_trade.poe_rare_item_train" in client.queries[0]
    assert "poe_trade.poe_rare_item_train_v3" in client.queries[1]
    assert recorded == ["0085"]
    assert all(settings is None for settings in client.settings)


def test_ensure_metadata_table_executes_create_database_and_table() -> None:
    client = RecordingClient()
    runner = MigrationRunner(
        client=cast(Any, client),
        database="poe_trade",
        dry_run=False,
    )

    runner._ensure_metadata_table()

    assert client.queries[0] == "CREATE DATABASE IF NOT EXISTS poe_trade"
    assert (
        "CREATE TABLE IF NOT EXISTS poe_trade.poe_schema_migrations"
        in client.queries[1]
    )


def test_account_stash_account_scope_migration_is_additive() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0035_account_stash_account_scope.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "ALTER TABLE poe_trade.raw_account_stash_snapshot" in sql
    assert "ALTER TABLE poe_trade.silver_account_stash_items" in sql
    assert "ADD COLUMN IF NOT EXISTS account_name String DEFAULT ''" in sql


def test_mod_feature_stage_mv_migration_defines_materialized_view() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0047_poeninja_mod_feature_stage_mv_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert (
        "CREATE TABLE IF NOT EXISTS poe_trade.ml_item_mod_features_sql_stage_v1" in sql
    )
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS "
        "poe_trade.mv_ml_item_mod_features_sql_stage_v1" in sql
    )


def test_incremental_v2_migration_defines_side_by_side_pipeline() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0048_ml_pricing_incremental_v2.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_fx_hour_v2" in sql
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS "
        "poe_trade.mv_raw_poeninja_to_ml_fx_hour_v2" in sql
    )
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_price_labels_v2" in sql
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS "
        "poe_trade.mv_silver_ps_items_to_price_labels_v2" in sql
    )
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_price_dataset_v2" in sql
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS "
        "poe_trade.mv_price_labels_to_dataset_v2" in sql
    )


def test_incremental_v2_fx_currency_key_fix_migration_rebuilds_price_label_mv() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0049_ml_pricing_v2_fx_currency_key_fix.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "DROP TABLE IF EXISTS poe_trade.mv_silver_ps_items_to_price_labels_v2" in sql
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS "
        "poe_trade.mv_silver_ps_items_to_price_labels_v2" in sql
    )
    assert "replaceRegexpAll(lowerUTF8(trimBoth(fx.currency))" in sql
    assert "IN ('div', 'divine', 'divines'), 'divine'" in sql


def test_incremental_v2_fx_alias_expansion_migration_maps_common_shorthand() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0050_ml_pricing_v2_fx_currency_alias_expansion.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "IN ('alch', 'alchemy'), 'orb of alchemy'" in sql
    assert (
        "IN ('gcp', 'gemcutter', 'gemcutters', 'gemcutter''s prism'), 'gemcutter''s prism'"
        in sql
    )
    assert "IN ('mirror',), 'mirror of kalandra'" in sql
    assert "IN ('exa', 'exalt', 'exalted', 'exalts'), 'exalted'" in sql


def test_v3_silver_observations_migration_creates_clickhouse_first_contract() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0051_ml_v3_silver_observations.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.silver_v3_item_observations" in sql
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_raw_public_stash_to_silver_v3_item_observations"
        in sql
    )
    assert "FROM poe_trade.raw_public_stash_pages" in sql
    assert "CODEC(ZSTD(6))" in sql


def test_v3_events_and_sale_proxy_migration_creates_lifecycle_tables() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0052_ml_v3_events_and_sale_proxy_labels.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.silver_v3_stash_snapshots" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.silver_v3_item_events" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_sale_proxy_labels" in sql
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_raw_public_stash_to_v3_stash_snapshots"
        in sql
    )


def test_v3_training_store_migration_creates_prediction_registry_tables() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0053_ml_v3_training_and_serving_store.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_training_examples" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_retrieval_candidates" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_model_registry" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_price_predictions" in sql


def test_v3_sale_confidence_migration_adds_training_example_flag() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0064_ml_v3_sale_confidence_flag.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "ALTER TABLE poe_trade.ml_v3_training_examples" in sql
    assert "ADD COLUMN IF NOT EXISTS sale_confidence_flag UInt8" in sql


def test_mirage_iron_ring_context_migration_aliases_as_of_ts() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0086_ml_v3_mirage_iron_ring_context_columns_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "item.observed_at AS as_of_ts" in sql
    assert "SELECT\n    as_of_ts," in sql
    assert "GROUP BY\n    as_of_ts," in sql


def test_v3_divine_price_migration_adds_listing_and_training_columns() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0087_ml_v3_divine_price_columns.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_listing_episodes" in sql
    assert "ALTER TABLE poe_trade.ml_v3_listing_episodes" in sql
    assert "ADD COLUMN IF NOT EXISTS latest_price_divine Nullable(Float64)" in sql
    assert "ADD COLUMN IF NOT EXISTS fx_chaos_per_divine Nullable(Float64)" in sql
    assert "ALTER TABLE poe_trade.ml_v3_training_examples" in sql
    assert "ADD COLUMN IF NOT EXISTS target_price_divine Nullable(Float64)" in sql
    assert (
        "ADD COLUMN IF NOT EXISTS target_fast_sale_24h_price_divine Nullable(Float64)"
        in sql
    )


def test_mod_registry_migration_creates_canonical_mod_table() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0069_ml_mod_registry_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_mod_registry_v1" in sql
    assert "mod_id String" in sql
    assert "spawn_weight_tags Array(String)" in sql
    assert "source_json String" in sql
    assert "ReplacingMergeTree(updated_at)" in sql


def test_iron_ring_wide_migration_uses_full_registry_family_set() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0070_ml_v3_iron_ring_wide_training_poc_registry.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW poe_trade.v_ml_v3_iron_ring_wide_training_poc" in sql
    assert "ml_mod_registry_v1" not in sql
    assert "intelligence_value" in sql
    assert "light_radius_to_accuracy_rating_value" in sql
    assert "item_found_rarity_increase_value" in sql
    assert "countIf(mod_value > 0) AS recognized_affix_count" in sql


def test_v3_eval_migration_creates_slice_gates_and_audit_tables() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0054_ml_v3_eval_and_promotion.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_route_eval" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_eval_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_promotion_audit" in sql


def test_v3_cleanup_migration_drops_legacy_derived_tables_not_raw() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0055_ml_v3_cleanup_legacy_derived.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "DROP TABLE IF EXISTS poe_trade.ml_price_dataset_v2" in sql
    assert "DROP TABLE IF EXISTS poe_trade.ml_model_registry_v1" in sql
    assert "DROP TABLE IF EXISTS poe_trade.silver_ps_items_raw" in sql
    assert "DROP TABLE IF EXISTS poe_trade.raw_public_stash_pages" not in sql
    assert "DROP TABLE IF EXISTS poe_trade.raw_account_stash_snapshot" not in sql


def test_private_stash_scan_migration_is_present() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0056_private_stash_scan_storage.sql"
    )

    assert migration.exists()


def test_private_stash_scan_migration_creates_run_tab_item_and_pointer_tables() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0056_private_stash_scan_storage.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_scan_tabs" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_item_valuations" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_active_scans" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.account_stash_published_scans" in sql


def test_private_stash_scan_migration_relies_on_existing_poe_rw_role_grants() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0056_private_stash_scan_storage.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "GRANT " not in sql


def test_scanner_opportunity_analytics_migration_adds_decision_storage() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0057_scanner_opportunity_analytics_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    expected_recommendation_columns = [
        "ADD COLUMN IF NOT EXISTS complexity_tier Nullable(String)",
        "ADD COLUMN IF NOT EXISTS required_capital_chaos Nullable(Float64)",
        "ADD COLUMN IF NOT EXISTS opportunity_type Nullable(String)",
        "ADD COLUMN IF NOT EXISTS estimated_operations Nullable(UInt16)",
        "ADD COLUMN IF NOT EXISTS estimated_whispers Nullable(UInt16)",
        "ADD COLUMN IF NOT EXISTS expected_profit_per_operation_chaos Nullable(Float64)",
        "ADD COLUMN IF NOT EXISTS feasibility_score Nullable(Float64)",
    ]
    expected_decision_columns = [
        "scanner_run_id String",
        "accepted UInt8",
        "decision_reason LowCardinality(String)",
        "strategy_id String",
        "league String",
        "recommendation_source Nullable(String)",
        "recommendation_contract_version Nullable(UInt32)",
        "producer_version Nullable(String)",
        "producer_run_id Nullable(String)",
        "item_or_market_key String",
        "complexity_tier Nullable(String)",
        "required_capital_chaos Nullable(Float64)",
        "estimated_operations Nullable(UInt16)",
        "estimated_whispers Nullable(UInt16)",
        "expected_profit_chaos Nullable(Float64)",
        "expected_profit_per_operation_chaos Nullable(Float64)",
        "feasibility_score Nullable(Float64)",
        "evidence_snapshot String",
        "recorded_at DateTime64(3, 'UTC')",
    ]

    assert "ALTER TABLE poe_trade.scanner_recommendations" in sql
    for column in expected_recommendation_columns:
        assert column in sql

    assert "CREATE TABLE IF NOT EXISTS poe_trade.scanner_candidate_decisions" in sql
    for column in expected_decision_columns:
        assert column in sql


def test_legacy_listing_source_migration_restores_enriched_views() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0088_restore_legacy_listing_source.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.silver_ps_stash_changes" in sql
    assert "CREATE TABLE IF NOT EXISTS poe_trade.silver_ps_items_raw" in sql
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS poe_trade.mv_ps_items_raw" in sql
    assert "CREATE VIEW IF NOT EXISTS poe_trade.v_ps_items_enriched" in sql
    assert "CREATE VIEW IF NOT EXISTS poe_trade.v_ps_current_stashes" in sql
    assert "CREATE VIEW IF NOT EXISTS poe_trade.v_ps_current_items" in sql


def test_single_solution_cleanup_migration_drops_legacy_ml_tables() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0058_ml_single_solution_cleanup.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "DROP TABLE IF EXISTS poe_trade.ml_price_dataset_v1" in sql
    assert "DROP TABLE IF EXISTS poe_trade.ml_price_dataset_v2" in sql
    assert "DROP TABLE IF EXISTS poe_trade.ml_model_registry_v1" in sql
    assert "DROP TABLE IF EXISTS poe_trade.ml_serving_profile_v1" in sql
    assert "DROP TABLE IF EXISTS poe_trade.ml_train_runs" in sql


def test_mirage_iron_ring_branch_migration_is_additive() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0079_ml_v3_mirage_iron_ring_branch_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert (
        "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_mirage_iron_ring_branch_v1" in sql
    )
    assert (
        "CREATE MATERIALIZED VIEW IF NOT EXISTS "
        "poe_trade.mv_silver_v3_item_observations_to_ml_v3_mirage_iron_ring_branch_v1"
        in sql
    )
    assert "FROM poe_trade.silver_v3_item_observations" in sql
    assert "league = 'Mirage'" in sql
    assert "category = 'ring'" in sql
    assert "base_type = 'Iron Ring'" in sql
    assert "v_ml_v3_mirage_iron_ring_wide" not in sql
    assert "poc" not in sql


def test_lgbm_neo_migration_defines_wide_rare_item_training_table() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0081_poe_rare_item_train_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS poe_trade.poe_rare_item_train" in sql
    assert "league LowCardinality(String)" in sql
    assert "base_type LowCardinality(String)" in sql
    assert "has_exp_dex_flat UInt8 DEFAULT 0" in sql
    assert "val_exp_dex_flat Nullable(Float32) DEFAULT NULL" in sql
    assert "tier_exp_dex_flat Nullable(UInt8) DEFAULT NULL" in sql
    assert "ENGINE = MergeTree()" in sql
    assert "ORDER BY (league, category, base_type, observed_at, item_id)" in sql


def test_lgbm_neo_ring_widening_migration_adds_canonical_family_columns() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0082_poe_rare_item_train_ring_family_widening.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "ALTER TABLE poe_trade.poe_rare_item_train" in sql
    assert "has_exp_all_attributes UInt8 DEFAULT 0" in sql
    assert "val_exp_all_attributes Nullable(Float32) DEFAULT NULL" in sql
    assert "tier_exp_all_attributes Nullable(UInt8) DEFAULT NULL" in sql
    assert "has_exp_strength UInt8 DEFAULT 0" in sql
    assert "tier_exp_strength Nullable(UInt8) DEFAULT NULL" in sql


def test_lgbm_neo_context_drop_migration_rebuilds_lean_table() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0084_poe_rare_item_train_drop_context_columns.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE poe_trade.poe_rare_item_train_v2" in sql
    assert "SELECT * EXCEPT(league, category, base_type, observed_at)" in sql
    assert "RENAME TABLE" in sql
    assert "poe_trade.poe_rare_item_train_v1_context_legacy" in sql


def test_lgbm_neo_temporal_context_migration_restores_split_metadata() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0085_poe_rare_item_train_restore_temporal_context.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE poe_trade.poe_rare_item_train_v3" in sql
    assert "PARTITION BY toYYYYMM(observed_at)" in sql
    assert (
        "ORDER BY (league, category, base_type, observed_at, item_fingerprint, item_id)"
        in sql
    )
    assert "poe_trade.poe_rare_item_train_v1_context_legacy" in sql
    assert "item_fingerprint" in sql
    assert "cityHash64" in sql
    assert "RENAME TABLE" in sql


def test_mirage_iron_ring_branch_views_migration_aggregates_affixes() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0080_ml_v3_mirage_iron_ring_branch_views_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert (
        "CREATE OR REPLACE VIEW poe_trade.v_ml_v3_mirage_iron_ring_affix_rows_v1" in sql
    )
    assert "FROM poe_trade.ml_v3_mirage_iron_ring_branch_v1" in sql
    assert "JSONExtractArrayRaw(item.item_json, 'explicitMods')" in sql
    assert "ARRAY JOIN affix_tuples AS affix_tuple" in sql
    assert (
        "CREATE OR REPLACE VIEW poe_trade.v_ml_v3_mirage_iron_ring_item_features_v1"
        in sql
    )
    assert "groupArray(tuple(affix_kind, affix_text)) AS affixes" in sql
    assert "affix_count" in sql
    assert "parsed_amount" in sql
    assert "v_ml_v3_mirage_iron_ring_wide" not in sql


def test_mirage_iron_ring_context_migration_adds_ring_context_columns() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "schema"
        / "migrations"
        / "0086_ml_v3_mirage_iron_ring_context_columns_v1.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert (
        "CREATE OR REPLACE VIEW poe_trade.v_ml_v3_mirage_iron_ring_item_features_v1"
        in sql
    )
    assert "influence_mask" in sql
    assert "catalyst_type" in sql
    assert "catalyst_quality" in sql
    assert "synth_imp_count" in sql
    assert "synth_implicit_mods_json" in sql
    assert "corrupted_implicit_mods_json" in sql
    assert "veiled_count" in sql
    assert "crafted_count" in sql
    assert "prefix_count" in sql
    assert "suffix_count" in sql
    assert "open_prefixes" in sql
    assert "open_suffixes" in sql
