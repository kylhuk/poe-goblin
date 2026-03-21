"""Tests for poeninja_snapshot service module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from poe_trade.ingestion.poeninja_snapshot import PoeNinjaClient
from poe_trade.ml import workflows
from poe_trade.services import poeninja_snapshot


class _ServiceFixedDatetime(datetime):
    _value: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls._value


class TestPoeninjaSnapshotService:
    def setup_method(self) -> None:
        status_file = Path(".sisyphus/state/poeninja_snapshot-last-run.json")
        if status_file.exists():
            status_file.unlink()

    @staticmethod
    def _seed_default_workflow_returns(
        mock_workflows: MagicMock, *, window_id: str = "window-1"
    ) -> None:
        mock_workflows.snapshot_poeninja.return_value = {"rows_written": 100}
        mock_workflows.repair_incremental_price_labels_v2.return_value = {
            "rows_repaired": 9,
            "missing_fx_before": 9,
            "missing_fx_after": 0,
        }
        mock_workflows.repair_incremental_price_dataset_v2.return_value = {
            "rows_repaired": 17,
            "missing_before": 17,
            "missing_after": 0,
        }
        mock_workflows.run_full_snapshot_rebuild_backfill.return_value = {
            "mode": "explicit_full_rebuild_backfill",
            "fx_rows": 50,
            "labels_rows": 200,
            "events_rows": 150,
            "dataset_rows": 1000,
            "comps_rows": 500,
            "serving_profile_rows": 240,
            "serving_profile_as_of_ts": "2026-03-10 01:00:00.000",
            "rebuild_window": {
            "window_id": window_id,
            "label_rows": 200,
            "label_min_as_of_ts": "2026-03-10 00:00:00",
            "label_max_as_of_ts": "2026-03-10 01:00:00",
            "label_digest_sum": "111",
            "label_digest_max": "222",
            "trade_metadata_rows": 20,
            "trade_metadata_max_retrieved_at": "2026-03-10 01:30:00",
            },
        }

    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_once_ingests_snapshot_only_by_default(
        self,
        mock_settings: MagicMock,
        mock_ch: MagicMock,
        mock_workflows: MagicMock,
    ) -> None:
        # Setup mocks
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        mock_settings.get_settings.return_value = cfg

        self._seed_default_workflow_returns(mock_workflows, window_id="window-1")

        # Run with --once
        result = poeninja_snapshot.main(["--once", "--league", "Mirage"])

        assert result == 0
        mock_workflows.snapshot_poeninja.assert_called_once()
        mock_workflows.repair_incremental_price_labels_v2.assert_not_called()
        mock_workflows.repair_incremental_price_dataset_v2.assert_not_called()
        mock_workflows.run_full_snapshot_rebuild_backfill.assert_not_called()

    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_writes_status_file(
        self,
        mock_settings: MagicMock,
        mock_ch: MagicMock,
        mock_workflows: MagicMock,
    ) -> None:
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        mock_settings.get_settings.return_value = cfg

        self._seed_default_workflow_returns(mock_workflows, window_id="window-1")

        status_file = Path(".sisyphus/state/poeninja_snapshot-last-run.json")
        if status_file.exists():
            status_file.unlink()

        result = poeninja_snapshot.main(["--once", "--league", "Mirage"])

        assert result == 0
        assert status_file.exists()
        with open(status_file) as f:
            status = json.load(f)
        assert status["league"] == "Mirage"
        assert status["snapshot_rows"] == 100
        assert status["snapshot_mode"] == "steady_state_snapshot_only"
        assert status["downstream_derivation_owner"] == "ml_v3"
        assert status["downstream_rebuild_triggered"] is False
        assert status["labels_rows"] == 0
        assert status["dataset_rows"] == 0
        assert status["serving_profile_rows"] == 0
        assert status["serving_profile_as_of_ts"] == ""
        assert status["rebuild_skipped"] is True
        assert status["rebuild_skip_reason"] == "steady_state_snapshot_only"
        assert status["rebuild_window"] == {}

    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_runs_explicit_backfill_when_requested(
        self,
        mock_settings: MagicMock,
        mock_ch: MagicMock,
        mock_workflows: MagicMock,
    ) -> None:
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        mock_settings.get_settings.return_value = cfg

        self._seed_default_workflow_returns(mock_workflows, window_id="window-backfill")

        result = poeninja_snapshot.main(
            ["--once", "--league", "Mirage", "--full-rebuild-backfill"]
        )

        assert result == 0
        mock_workflows.snapshot_poeninja.assert_called_once()
        mock_workflows.repair_incremental_price_labels_v2.assert_not_called()
        mock_workflows.repair_incremental_price_dataset_v2.assert_not_called()
        mock_workflows.run_full_snapshot_rebuild_backfill.assert_not_called()

        status_file = Path(".sisyphus/state/poeninja_snapshot-last-run.json")
        status = json.loads(status_file.read_text(encoding="utf-8"))
        assert status["snapshot_mode"] == "steady_state_snapshot_only"
        assert status["downstream_rebuild_triggered"] is False
        assert status["rebuild_skipped"] is True
        assert status["rebuild_skip_reason"] == "steady_state_snapshot_only"
        assert status["events_rows"] == 0
        assert status["dataset_rows"] == 0
        assert status["comps_rows"] == 0
        assert status["serving_profile_rows"] == 0
        assert status["serving_profile_as_of_ts"] == ""
        assert status["rebuild_window"] == {}

    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_disabled_returns_zero(self, mock_settings: MagicMock) -> None:
        cfg = MagicMock()
        cfg.poe_enable_poeninja_snapshot = False
        mock_settings.get_settings.return_value = cfg

        result = poeninja_snapshot.main(["--once"])
        assert result == 0

    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_no_league_returns_error(self, mock_settings: MagicMock) -> None:
        cfg = MagicMock()
        cfg.ml_automation_league = None
        mock_settings.get_settings.return_value = cfg

        result = poeninja_snapshot.main(["--once"])
        assert result == 1

    @patch("poe_trade.services.poeninja_snapshot.time.sleep")
    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_clamps_interval_to_floor_when_not_once(
        self,
        mock_settings: MagicMock,
        mock_ch: MagicMock,
        mock_workflows: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        cfg.poe_ml_dataset_rebuild_interval_seconds = 60
        mock_settings.get_settings.return_value = cfg

        self._seed_default_workflow_returns(mock_workflows, window_id="window-1")
        mock_sleep.side_effect = KeyboardInterrupt()

        result = poeninja_snapshot.main(["--league", "Mirage"])

        assert result == 0
        mock_sleep.assert_called_once_with(1800)

    @patch("poe_trade.services.poeninja_snapshot.time.sleep")
    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_uses_default_interval_when_not_once(
        self,
        mock_settings: MagicMock,
        mock_ch: MagicMock,
        mock_workflows: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        cfg.poe_ml_dataset_rebuild_interval_seconds = 3600
        mock_settings.get_settings.return_value = cfg

        self._seed_default_workflow_returns(mock_workflows, window_id="window-1")
        mock_sleep.side_effect = KeyboardInterrupt()

        result = poeninja_snapshot.main(["--league", "Mirage"])

        assert result == 0
        mock_sleep.assert_called_once_with(3600)


def test_service_normalizes_sample_time(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = MagicMock()
    cfg.clickhouse_url = "http://localhost:8123"
    cfg.ml_automation_league = "Mirage"
    monkeypatch.setattr(
        poeninja_snapshot.config_settings,
        "get_settings",
        lambda: cfg,
    )

    class DummyClient:
        def execute(self, query: str) -> str:
            return ""

    class DummyClickHouseClient:
        @classmethod
        def from_env(cls, url: str) -> DummyClient:
            return DummyClient()

    monkeypatch.setattr(
        poeninja_snapshot,
        "ClickHouseClient",
        DummyClickHouseClient,
    )

    captured: list[dict[str, object]] = []

    def _capture_insert(_client, _table, rows: list[dict[str, object]]) -> None:
        captured.extend(rows)

    monkeypatch.setattr(workflows, "_insert_json_rows", _capture_insert)

    response = SimpleNamespace(
        payload={
            "lines": [
                {
                    "detailsId": "Currency",
                    "currencyTypeName": "Mirror of Kalandra",
                    "chaosEquivalent": 1.0,
                    "count": 1,
                }
            ]
        },
        stale=False,
        reason="test",
    )

    monkeypatch.setattr(
        PoeNinjaClient,
        "fetch_currency_overview",
        lambda *_args, **_kwargs: response,
    )

    fake_dt = datetime(2026, 3, 19, 10, 0, 0, 0, tzinfo=UTC)
    _ServiceFixedDatetime._value = fake_dt
    monkeypatch.setattr(workflows, "datetime", _ServiceFixedDatetime)

    result = poeninja_snapshot.main(["--once", "--league", "Mirage"])
    assert result == 0
    assert captured, "Service path should emit rows"
    timestamp = str(captured[0]["sample_time_utc"])
    assert timestamp == "2026-03-19 10:00:00.000"
    assert "+" not in timestamp
    assert "T" not in timestamp
