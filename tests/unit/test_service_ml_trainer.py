from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from poe_trade.db import ClickHouseClient
from poe_trade.services import ml_trainer


def test_ml_trainer_persists_runtime_stage_in_status(monkeypatch) -> None:
    status_path = Path(".sisyphus/state/qa/ml-trainer-last-run.json")
    if status_path.exists():
        status_path.unlink()

    cfg = SimpleNamespace(
        clickhouse_url="http://ch",
        ml_automation_enabled=True,
        ml_automation_league="Mirage",
        ml_automation_interval_seconds=30,
        ml_automation_max_iterations=1,
        ml_automation_max_wall_clock_seconds=60,
        ml_automation_no_improvement_patience=2,
        ml_automation_min_mdape_improvement=0.005,
    )
    monkeypatch.setattr(ml_trainer.config_settings, "get_settings", lambda: cfg)
    monkeypatch.setattr(
        ml_trainer.ClickHouseClient,
        "from_env",
        lambda _url: SimpleNamespace(),
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )
    monkeypatch.setattr(
        ml_trainer,
        "_refresh_v3_training_examples",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "latest_source_at": None,
            "latest_training_at": None,
            "replayed_days": [],
        },
    )
    monkeypatch.setattr(
        ml_trainer.v3_train,
        "train_all_routes_v3",
        lambda *_args, **_kwargs: {
            "run_id": "run-1",
            "trained_count": 1,
            "eval_prediction_rows": 0,
            "routes": ["sparse_retrieval"],
        },
    )
    result = ml_trainer.main(["--once", "--league", "Mirage"])

    assert result == 0
    assert status_path.exists()
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["league"] == "Mirage"
    assert payload["stage"] == "train_cycle"
    assert payload["status"] == "completed"
    assert payload["result"]["v3"]["run_id"] == "run-1"


def test_ml_trainer_rejects_dataset_table_argument(monkeypatch) -> None:
    cfg = SimpleNamespace(
        clickhouse_url="http://ch",
        ml_automation_enabled=True,
        ml_automation_league="Mirage",
        ml_automation_interval_seconds=30,
        ml_automation_max_iterations=1,
        ml_automation_max_wall_clock_seconds=60,
        ml_automation_no_improvement_patience=2,
        ml_automation_min_mdape_improvement=0.005,
    )
    monkeypatch.setattr(ml_trainer.config_settings, "get_settings", lambda: cfg)

    try:
        ml_trainer.main(
            [
                "--once",
                "--league",
                "Mirage",
                "--dataset-table",
                "poe_trade.ml_price_dataset_v1",
            ]
        )
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse error for removed --dataset-table")


def test_ml_trainer_uses_v3_training(monkeypatch) -> None:
    cfg = SimpleNamespace(
        clickhouse_url="http://ch",
        ml_automation_enabled=True,
        ml_automation_league="Mirage",
        ml_automation_interval_seconds=30,
        ml_automation_max_iterations=1,
        ml_automation_max_wall_clock_seconds=60,
        ml_automation_no_improvement_patience=2,
        ml_automation_min_mdape_improvement=0.005,
    )
    monkeypatch.setattr(ml_trainer.config_settings, "get_settings", lambda: cfg)
    monkeypatch.setattr(
        ml_trainer.ClickHouseClient,
        "from_env",
        lambda _url: SimpleNamespace(),
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )
    monkeypatch.setattr(
        ml_trainer,
        "_refresh_v3_training_examples",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "latest_source_at": None,
            "latest_training_at": None,
            "replayed_days": [],
        },
    )
    monkeypatch.setattr(
        ml_trainer.v3_train,
        "train_all_routes_v3",
        lambda *_args, **_kwargs: {"trained_count": 2, "routes": ["a", "b"]},
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "rollout_controls",
        lambda *_args, **_kwargs: {
            "league": "Mirage",
            "shadow_mode": False,
            "cutover_enabled": False,
            "candidate_model_version": None,
            "incumbent_model_version": None,
            "effective_serving_model_version": None,
            "updated_at": "2026-03-20 00:00:00",
            "last_action": "noop",
        },
    )

    result = ml_trainer.main(["--once", "--league", "Mirage"])

    assert result == 0


def test_refresh_v3_training_examples_replays_missing_days() -> None:
    class _Client:
        def execute(self, query: str) -> str:
            if "max(observed_at) AS latest_source_at" in query:
                return '{"latest_source_at":"2026-03-22 12:06:15.756"}\n'
            if "max(as_of_ts) AS latest_training_at" in query:
                return '{"latest_training_at":"2026-03-20 11:57:36.615"}\n'
            if "min(toDate(observed_at)) AS first_day" in query:
                return '{"first_day":"2026-03-01"}\n'
            return ""

    calls: list[tuple[str, str]] = []

    def _backfill_range(*_args, **kwargs):
        calls.append((kwargs["start_day"], kwargs["end_day"]))
        return {
            "results": [
                {"day": "2026-03-21"},
                {"day": "2026-03-22"},
            ]
        }

    original = ml_trainer.v3_backfill.backfill_range
    ml_trainer.v3_backfill.backfill_range = _backfill_range
    try:
        payload = ml_trainer._refresh_v3_training_examples(
            cast(ClickHouseClient, _Client()),
            league="Mirage",
        )
    finally:
        ml_trainer.v3_backfill.backfill_range = original

    assert calls == [("2026-03-21", "2026-03-22")]
    assert payload["replayed_days"] == ["2026-03-21", "2026-03-22"]


def test_assert_stage_completed_accepts_legacy_train_payload_without_status() -> None:
    ml_trainer._assert_stage_completed(
        stage="train_models",
        payload={"trained_count": 1, "results": [{"route": "rings"}]},
    )


def test_assert_stage_completed_accepts_legacy_eval_payload_without_status() -> None:
    ml_trainer._assert_stage_completed(
        stage="evaluate_models",
        payload={
            "run_id": "run-1",
            "summary": {"gate_passed": 1},
            "metrics": {"global_fair_value_mdape": 0.21},
        },
    )


def test_assert_stage_completed_rejects_missing_status_for_refresh_stage() -> None:
    with pytest.raises(
        RuntimeError, match="refresh_training_examples failed with missing status"
    ):
        ml_trainer._assert_stage_completed(
            stage="refresh_training_examples",
            payload={"trained_count": 1, "results": [{"route": "rings"}]},
        )


def test_assert_stage_completed_rejects_missing_status_for_malformed_train_payload() -> (
    None
):
    with pytest.raises(RuntimeError, match="train_models failed with missing status"):
        ml_trainer._assert_stage_completed(
            stage="train_models", payload={"run_id": "run-1"}
        )


def test_assert_stage_completed_rejects_missing_status_for_malformed_eval_payload() -> (
    None
):
    with pytest.raises(
        RuntimeError, match="evaluate_models failed with missing status"
    ):
        ml_trainer._assert_stage_completed(
            stage="evaluate_models",
            payload={"run_id": "run-1", "route_rows": []},
        )
