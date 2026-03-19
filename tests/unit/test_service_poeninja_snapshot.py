"""Tests for poeninja_snapshot service module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from poe_trade.services import poeninja_snapshot


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
        mock_workflows.build_fx.return_value = {"rows_written": 50}
        mock_workflows.normalize_prices.return_value = {"rows_written": 200}
        mock_workflows.dataset_rebuild_window.return_value = {
            "window_id": window_id,
            "label_rows": 200,
            "label_min_as_of_ts": "2026-03-10 00:00:00",
            "label_max_as_of_ts": "2026-03-10 01:00:00",
            "label_digest_sum": "111",
            "label_digest_max": "222",
            "trade_metadata_rows": 20,
            "trade_metadata_max_retrieved_at": "2026-03-10 01:30:00",
        }
        mock_workflows.build_listing_events_and_labels.return_value = {
            "rows_written": 150
        }
        mock_workflows.build_dataset.return_value = {"rows_written": 1000}
        mock_workflows.build_comps.return_value = {"rows_written": 500}
        mock_workflows.build_serving_profile.return_value = {
            "rows_written": 240,
            "profile_as_of_ts": "2026-03-10 01:00:00.000",
        }

    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_once_calls_all_workflows(
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
        mock_workflows.build_fx.assert_called_once()
        mock_workflows.normalize_prices.assert_called_once()
        mock_workflows.build_listing_events_and_labels.assert_called_once()
        mock_workflows.build_dataset.assert_called_once()
        mock_workflows.build_comps.assert_called_once()
        mock_workflows.build_serving_profile.assert_called_once()

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
        assert status["dataset_rows"] == 1000
        assert status["serving_profile_rows"] == 240
        assert status["serving_profile_as_of_ts"] == "2026-03-10 01:00:00.000"
        assert status["rebuild_skipped"] is False
        assert status["rebuild_window"]["window_id"] == "window-1"

    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_skips_downstream_rebuild_when_snapshot_window_unchanged(
        self,
        mock_settings: MagicMock,
        mock_ch: MagicMock,
        mock_workflows: MagicMock,
    ) -> None:
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        mock_settings.get_settings.return_value = cfg

        self._seed_default_workflow_returns(
            mock_workflows,
            window_id="window-unchanged",
        )

        status_file = Path(".sisyphus/state/poeninja_snapshot-last-run.json")
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            json.dumps(
                {
                    "league": "Mirage",
                    "rebuild_window": {"window_id": "window-unchanged"},
                }
            ),
            encoding="utf-8",
        )

        result = poeninja_snapshot.main(["--once", "--league", "Mirage"])

        assert result == 0
        mock_workflows.snapshot_poeninja.assert_called_once()
        mock_workflows.build_fx.assert_called_once()
        mock_workflows.normalize_prices.assert_called_once()
        mock_workflows.dataset_rebuild_window.assert_called_once()
        mock_workflows.build_listing_events_and_labels.assert_not_called()
        mock_workflows.build_dataset.assert_not_called()
        mock_workflows.build_comps.assert_not_called()
        mock_workflows.build_serving_profile.assert_called_once()

        status = json.loads(status_file.read_text(encoding="utf-8"))
        assert status["rebuild_skipped"] is True
        assert status["rebuild_skip_reason"] == "unchanged_snapshot_window"
        assert status["events_rows"] == 0
        assert status["dataset_rows"] == 0
        assert status["comps_rows"] == 0
        assert status["serving_profile_rows"] == 240
        assert status["serving_profile_as_of_ts"] == "2026-03-10 01:00:00.000"

    @patch("poe_trade.services.poeninja_snapshot.ml_workflows")
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_rebuilds_downstream_tables_when_snapshot_window_changes(
        self,
        mock_settings: MagicMock,
        mock_ch: MagicMock,
        mock_workflows: MagicMock,
    ) -> None:
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        mock_settings.get_settings.return_value = cfg

        self._seed_default_workflow_returns(mock_workflows, window_id="window-new")

        status_file = Path(".sisyphus/state/poeninja_snapshot-last-run.json")
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            json.dumps(
                {
                    "league": "Mirage",
                    "rebuild_window": {"window_id": "window-old"},
                }
            ),
            encoding="utf-8",
        )

        result = poeninja_snapshot.main(["--once", "--league", "Mirage"])

        assert result == 0
        mock_workflows.dataset_rebuild_window.assert_called_once()
        mock_workflows.build_listing_events_and_labels.assert_called_once()
        mock_workflows.build_dataset.assert_called_once()
        mock_workflows.build_comps.assert_called_once()
        mock_workflows.build_serving_profile.assert_called_once()

        status = json.loads(status_file.read_text(encoding="utf-8"))
        assert status["rebuild_skipped"] is False
        assert status["previous_rebuild_window_id"] == "window-old"
        assert status["rebuild_window"]["window_id"] == "window-new"
        assert status["dataset_rows"] == 1000

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
