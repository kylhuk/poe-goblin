from __future__ import annotations

import json
import sys
import types
from datetime import date
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from poe_trade.db.clickhouse import ClickHouseClientError
from poe_trade.ml.v3 import backfill


def _load_ml_trainer_module():
    if "joblib" not in sys.modules:
        sys.modules["joblib"] = types.ModuleType("joblib")
    if "numpy" not in sys.modules:
        numpy_module = types.ModuleType("numpy")
        numpy_module.ndarray = object
        numpy_module.array = lambda *args, **kwargs: list(args)
        sys.modules["numpy"] = numpy_module
    if "sklearn" not in sys.modules:
        sklearn_module = types.ModuleType("sklearn")
        ensemble_module = types.ModuleType("sklearn.ensemble")
        feature_extraction_module = types.ModuleType("sklearn.feature_extraction")
        linear_model_module = types.ModuleType("sklearn.linear_model")

        class _GradientBoostingRegressor:  # noqa: D401
            """test stub"""

        class _DictVectorizer:  # noqa: D401
            """test stub"""

        class _LogisticRegression:  # noqa: D401
            """test stub"""

        ensemble_module.GradientBoostingRegressor = _GradientBoostingRegressor
        feature_extraction_module.DictVectorizer = _DictVectorizer
        linear_model_module.LogisticRegression = _LogisticRegression
        sys.modules["sklearn"] = sklearn_module
        sys.modules["sklearn.ensemble"] = ensemble_module
        sys.modules["sklearn.feature_extraction"] = feature_extraction_module
        sys.modules["sklearn.linear_model"] = linear_model_module
    return importlib.import_module("poe_trade.services.ml_trainer")


class _RecordingClient:
    def __init__(self, *, bytes_on_disk: int = 1_000_000) -> None:
        self.bytes_on_disk = bytes_on_disk
        self.queries: list[str] = []

    def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
        self.queries.append(query)
        if "FROM system.parts" in query:
            return json.dumps({"bytes_on_disk": self.bytes_on_disk}) + "\n"
        return ""


def test_guard_disk_budget_raises_when_limit_exceeded() -> None:
    client = _RecordingClient(bytes_on_disk=200)

    with pytest.raises(ValueError, match="disk budget exceeded"):
        backfill.guard_disk_budget(client, max_bytes=100)


def test_guard_disk_budget_raises_when_disk_telemetry_unavailable() -> None:
    class _TelemetryErrorClient(_RecordingClient):
        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            if "FROM system.parts" in query:
                raise ClickHouseClientError("disk telemetry unavailable")
            return super().execute(query, settings=settings)

    with pytest.raises(ValueError, match="disk telemetry unavailable"):
        backfill.guard_disk_budget(_TelemetryErrorClient(), max_bytes=100)


def test_replay_day_executes_episode_event_label_and_training_queries() -> None:
    client = _RecordingClient(bytes_on_disk=10)

    result = backfill.replay_day(
        client,
        league="Mirage",
        day=date(2026, 3, 20),
        max_bytes=1_000,
    )

    joined = "\n".join(client.queries)
    assert "CREATE TABLE IF NOT EXISTS poe_trade.ml_v3_listing_episodes" in joined
    assert "INSERT INTO poe_trade.ml_v3_listing_episodes" in joined
    assert "INSERT INTO poe_trade.silver_v3_item_events" in joined
    assert "INSERT INTO poe_trade.ml_v3_sale_proxy_labels" in joined
    assert "INSERT INTO poe_trade.ml_v3_training_examples" in joined
    assert "sale_confidence_flag" in joined
    assert result.day == "2026-03-20"


def test_backfill_range_processes_all_days_inclusive() -> None:
    client = _RecordingClient(bytes_on_disk=10)

    payload = backfill.backfill_range(
        client,
        league="Mirage",
        start_day="2026-03-20",
        end_day="2026-03-22",
        max_bytes=1_000,
    )

    assert payload["days_requested"] == 3
    assert payload["days_processed"] == 3
    assert [row["day"] for row in payload["results"]] == [
        "2026-03-20",
        "2026-03-21",
        "2026-03-22",
    ]


def test_backfill_range_retries_transient_replay_failures() -> None:
    class _FlakyClient(_RecordingClient):
        def __init__(self) -> None:
            super().__init__(bytes_on_disk=10)
            self._failed_once = False

        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            if (
                "INSERT INTO poe_trade.silver_v3_item_events" in query
                and "2026-03-20" in query
                and not self._failed_once
            ):
                self._failed_once = True
                raise ClickHouseClientError("temporary replay failure")
            return super().execute(query, settings=settings)

    client = _FlakyClient()

    payload = backfill.backfill_range(
        client,
        league="Mirage",
        start_day="2026-03-20",
        end_day="2026-03-20",
        max_bytes=1_000,
        chunk_days=1,
        max_retries=1,
    )

    assert payload["days_processed"] == 1
    assert client._failed_once is True


def test_chunk_retry_does_not_replay_completed_days() -> None:
    calls: list[str] = []
    attempts_by_day: dict[str, int] = {}
    original = backfill.replay_day

    def _replay_day(client, *, league, day, max_bytes=13_500_000_000):  # noqa: ANN001
        day_key = day.isoformat()
        calls.append(day_key)
        attempts = attempts_by_day.get(day_key, 0) + 1
        attempts_by_day[day_key] = attempts
        if day_key == "2026-03-21" and attempts == 1:
            raise ClickHouseClientError("transient day failure")
        return original(client, league=league, day=day, max_bytes=max_bytes)

    client = _RecordingClient(bytes_on_disk=10)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(backfill, "replay_day", _replay_day)
    try:
        payload = backfill.backfill_range(
            client,
            league="Mirage",
            start_day="2026-03-20",
            end_day="2026-03-21",
            max_bytes=1_000,
            chunk_days=2,
            max_retries=1,
        )
    finally:
        monkeypatch.undo()

    assert payload["days_processed"] == 2
    assert calls == ["2026-03-20", "2026-03-21", "2026-03-21"]


def test_backfill_range_falls_back_to_day_replay_when_chunk_fails() -> None:
    class _ChunkFlakyClient(_RecordingClient):
        def __init__(self) -> None:
            super().__init__(bytes_on_disk=10)
            self._failed_once = False

        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            if (
                "INSERT INTO poe_trade.silver_v3_item_events" in query
                and "2026-03-21" in query
            ):
                if not self._failed_once:
                    self._failed_once = True
                    raise ClickHouseClientError("chunk replay failed")
            return super().execute(query, settings=settings)

    client = _ChunkFlakyClient()

    payload = backfill.backfill_range(
        client,
        league="Mirage",
        start_day="2026-03-20",
        end_day="2026-03-21",
        max_bytes=1_000,
        chunk_days=2,
        max_retries=0,
    )

    assert payload["days_processed"] == 2
    assert payload["results"][0]["day"] == "2026-03-20"
    assert payload["results"][1]["day"] == "2026-03-21"


def test_replay_day_clears_target_day_slice_before_inserts() -> None:
    client = _RecordingClient(bytes_on_disk=10)

    _ = backfill.replay_day(
        client,
        league="Mirage",
        day=date(2026, 3, 20),
        max_bytes=1_000,
    )

    joined = "\n".join(client.queries)
    assert "DELETE FROM poe_trade.ml_v3_listing_episodes" in joined
    assert "DELETE FROM poe_trade.silver_v3_item_events" in joined
    assert "DELETE FROM poe_trade.ml_v3_sale_proxy_labels" in joined
    assert "DELETE FROM poe_trade.ml_v3_training_examples" in joined


def test_partial_replay_retry_keeps_single_effective_day_output() -> None:
    class _IdempotentClient(_RecordingClient):
        def __init__(self) -> None:
            super().__init__(bytes_on_disk=10)
            self._failed_once = False
            self.day_insert_effect: dict[str, int] = {}

        def execute(self, query: str, settings=None) -> str:  # noqa: ANN001
            if (
                "DELETE FROM poe_trade.silver_v3_item_events" in query
                and "2026-03-21" in query
            ):
                self.day_insert_effect["2026-03-21"] = 0
            if (
                "INSERT INTO poe_trade.silver_v3_item_events" in query
                and "2026-03-21" in query
                and not self._failed_once
            ):
                self._failed_once = True
                raise ClickHouseClientError("transient day replay failure")
            response = super().execute(query, settings=settings)
            if (
                "INSERT INTO poe_trade.silver_v3_item_events" in query
                and "2026-03-21" in query
            ):
                self.day_insert_effect["2026-03-21"] = (
                    self.day_insert_effect.get("2026-03-21", 0) + 1
                )
            return response

    client = _IdempotentClient()
    payload = backfill.backfill_range(
        client,
        league="Mirage",
        start_day="2026-03-20",
        end_day="2026-03-21",
        max_bytes=1_000,
        chunk_days=2,
        max_retries=1,
    )

    assert payload["days_processed"] == 2
    assert client.day_insert_effect["2026-03-21"] == 2


def test_ml_trainer_once_fails_when_refresh_stage_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ml_trainer = _load_ml_trainer_module()
    status_path = tmp_path / "ml-trainer-last-run.json"
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
        ml_trainer.ClickHouseClient, "from_env", lambda _url: SimpleNamespace()
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )
    monkeypatch.setattr(
        ml_trainer,
        "_write_status",
        lambda payload: status_path.write_text(json.dumps(payload), encoding="utf-8"),
    )
    monkeypatch.setattr(
        ml_trainer,
        "_refresh_v3_training_examples",
        lambda *_args, **_kwargs: {
            "status": "failed",
            "latest_source_at": None,
            "latest_training_at": None,
            "replayed_days": [],
        },
    )

    result = ml_trainer.main(["--once", "--league", "Mirage"])

    assert result == 1
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "train_cycle"
    assert payload["status"] == "failed"


def test_ml_trainer_once_allows_legacy_training_status_missing_with_success_indicators(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ml_trainer = _load_ml_trainer_module()
    status_path = tmp_path / "ml-trainer-last-run.json"
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
        ml_trainer.ClickHouseClient, "from_env", lambda _url: SimpleNamespace()
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )
    monkeypatch.setattr(
        ml_trainer,
        "_write_status",
        lambda payload: status_path.write_text(json.dumps(payload), encoding="utf-8"),
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
        },
    )

    result = ml_trainer.main(["--once", "--league", "Mirage"])

    assert result == 0
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "train_cycle"
    assert payload["status"] == "completed"
    assert payload["result"]["v3"]["run_id"] == "run-1"


def test_ml_trainer_once_fails_when_training_status_missing_and_no_success_indicators(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ml_trainer = _load_ml_trainer_module()
    status_path = tmp_path / "ml-trainer-last-run.json"
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
        ml_trainer.ClickHouseClient, "from_env", lambda _url: SimpleNamespace()
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )
    monkeypatch.setattr(
        ml_trainer,
        "_write_status",
        lambda payload: status_path.write_text(json.dumps(payload), encoding="utf-8"),
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
            "eval_prediction_rows": 0,
        },
    )

    result = ml_trainer.main(["--once", "--league", "Mirage"])

    assert result == 1
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "train_cycle"
    assert payload["status"] == "failed"


def test_ml_trainer_once_fails_when_training_stage_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ml_trainer = _load_ml_trainer_module()
    status_path = tmp_path / "ml-trainer-last-run.json"
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
        ml_trainer.ClickHouseClient, "from_env", lambda _url: SimpleNamespace()
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )
    monkeypatch.setattr(
        ml_trainer,
        "_write_status",
        lambda payload: status_path.write_text(json.dumps(payload), encoding="utf-8"),
    )
    monkeypatch.setattr(
        ml_trainer,
        "_refresh_v3_training_examples",
        lambda *_args, **_kwargs: {
            "latest_source_at": None,
            "latest_training_at": None,
            "replayed_days": [],
        },
    )
    monkeypatch.setattr(
        ml_trainer.v3_train,
        "train_all_routes_v3",
        lambda *_args, **_kwargs: {
            "status": "failed",
            "run_id": "run-1",
            "trained_count": 0,
            "eval_prediction_rows": 0,
        },
    )

    result = ml_trainer.main(["--once", "--league", "Mirage"])

    assert result == 1
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "train_cycle"
    assert payload["status"] == "failed"


def test_ml_trainer_once_fails_when_eval_stage_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ml_trainer = _load_ml_trainer_module()
    status_path = tmp_path / "ml-trainer-last-run.json"
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
        ml_trainer.ClickHouseClient, "from_env", lambda _url: SimpleNamespace()
    )
    monkeypatch.setattr(
        ml_trainer.workflows,
        "warmup_active_models",
        lambda *_args, **_kwargs: {"lastAttemptAt": None, "routes": {}},
    )
    monkeypatch.setattr(
        ml_trainer,
        "_write_status",
        lambda payload: status_path.write_text(json.dumps(payload), encoding="utf-8"),
    )
    monkeypatch.setattr(
        ml_trainer,
        "_refresh_v3_training_examples",
        lambda *_args, **_kwargs: {
            "latest_source_at": None,
            "latest_training_at": None,
            "replayed_days": [],
        },
    )
    monkeypatch.setattr(
        ml_trainer.v3_train,
        "train_all_routes_v3",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "run_id": "run-1",
            "trained_count": 1,
            "eval_prediction_rows": 5,
        },
    )
    monkeypatch.setattr(
        ml_trainer.v3_eval,
        "evaluate_run",
        lambda *_args, **_kwargs: {"status": "failed", "run_id": "run-1"},
    )

    result = ml_trainer.main(["--once", "--league", "Mirage"])

    assert result == 1
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "train_cycle"
    assert payload["status"] == "failed"
