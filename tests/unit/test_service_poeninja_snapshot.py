"""Tests for poeninja_snapshot service module."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Mock ml_workflows before importing service to avoid joblib dependency
mock_ml_workflows = MagicMock()
sys.modules["poe_trade.ml.workflows"] = mock_ml_workflows

from poe_trade.services import poeninja_snapshot


class TestPoeninjaSnapshotService:
    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_once_calls_all_workflows(
        self, mock_settings: MagicMock, mock_ch: MagicMock
    ) -> None:
        # Setup mocks
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        mock_settings.get_settings.return_value = cfg

        mock_ml_workflows.snapshot_poeninja.return_value = {"rows_written": 100}
        mock_ml_workflows.build_fx.return_value = {"rows_written": 50}
        mock_ml_workflows.normalize_prices.return_value = {"rows_written": 200}
        mock_ml_workflows.build_listing_events_and_labels.return_value = {
            "rows_written": 150
        }
        mock_ml_workflows.build_dataset.return_value = {"rows_written": 1000}
        mock_ml_workflows.build_comps.return_value = {"rows_written": 500}

        # Run with --once
        result = poeninja_snapshot.main(["--once", "--league", "Mirage"])

        assert result == 0
        mock_ml_workflows.snapshot_poeninja.assert_called_once()
        mock_ml_workflows.build_fx.assert_called_once()
        mock_ml_workflows.normalize_prices.assert_called_once()
        mock_ml_workflows.build_listing_events_and_labels.assert_called_once()
        mock_ml_workflows.build_dataset.assert_called_once()
        mock_ml_workflows.build_comps.assert_called_once()

    @patch("poe_trade.services.poeninja_snapshot.ClickHouseClient")
    @patch("poe_trade.services.poeninja_snapshot.config_settings")
    def test_main_writes_status_file(
        self, mock_settings: MagicMock, mock_ch: MagicMock
    ) -> None:
        cfg = MagicMock()
        cfg.clickhouse_url = "http://localhost:8123"
        cfg.ml_automation_league = "Mirage"
        mock_settings.get_settings.return_value = cfg

        mock_ml_workflows.snapshot_poeninja.return_value = {"rows_written": 100}
        mock_ml_workflows.build_fx.return_value = {"rows_written": 50}
        mock_ml_workflows.normalize_prices.return_value = {"rows_written": 200}
        mock_ml_workflows.build_listing_events_and_labels.return_value = {
            "rows_written": 150
        }
        mock_ml_workflows.build_dataset.return_value = {"rows_written": 1000}
        mock_ml_workflows.build_comps.return_value = {"rows_written": 500}

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
