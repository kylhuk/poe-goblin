import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _load_script_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "collect_hot_query_log.py"
    )
    spec = importlib.util.spec_from_file_location("collect_hot_query_log", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_query_includes_query_ids_and_since_seconds() -> None:
    module = _load_script_module()

    sql = module._build_query(query_ids=["qid-1", "qid-2"], since_seconds=90, limit=25)

    assert "FROM system.query_log" in sql
    assert "query_id IN ('qid-1', 'qid-2')" in sql
    assert "event_time >= now() - INTERVAL 90 SECOND" in sql
    assert "LIMIT 25" in sql
    assert "query_duration_ms" in sql
    assert "read_rows" in sql
    assert "read_bytes" in sql
    assert "memory_usage" in sql


def test_main_requires_query_filter(monkeypatch, capsys) -> None:
    module = _load_script_module()

    monkeypatch.setattr(sys, "argv", ["collect_hot_query_log.py"])

    try:
        _ = module.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected parser to exit with code 2")

    err = capsys.readouterr().err
    assert "provide at least one --query-id or --since-seconds" in err


def test_main_returns_clear_error_when_no_rows(monkeypatch, capsys) -> None:
    module = _load_script_module()

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return "\n"

    monkeypatch.setattr(
        module.Settings,
        "from_env",
        lambda: SimpleNamespace(clickhouse_url="http://clickhouse"),
    )
    monkeypatch.setattr(
        module.ClickHouseClient, "from_env", lambda _endpoint: _DummyClient()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["collect_hot_query_log.py", "--since-seconds", "120", "--limit", "5"],
    )

    result = module.main()

    assert result == 2
    err = capsys.readouterr().err
    assert "no system.query_log rows found" in err
    assert "since_seconds=120" in err
    assert "limit=5" in err


def test_main_writes_normalized_json(monkeypatch, tmp_path) -> None:
    module = _load_script_module()

    row = {
        "query_id": "abc123",
        "initial_query_id": "abc123",
        "event_time": "2026-03-19 10:11:12",
        "event_time_microseconds": "2026-03-19 10:11:12.123456",
        "query_start_time": "2026-03-19 10:11:12",
        "query_start_time_microseconds": "2026-03-19 10:11:12.100000",
        "query_duration_ms": 23,
        "query_kind": "Select",
        "query": "SELECT 1",
        "normalized_query_hash": "1234567890",
        "read_rows": 42,
        "read_bytes": 4096,
        "result_rows": 1,
        "result_bytes": 16,
        "written_rows": 0,
        "written_bytes": 0,
        "memory_usage": 8192,
        "exception_code": 0,
        "exception": "",
        "user": "default",
        "current_database": "default",
    }

    class _DummyClient:
        def execute(self, _query: str) -> str:
            return json.dumps(row) + "\n"

    monkeypatch.setattr(
        module.Settings,
        "from_env",
        lambda: SimpleNamespace(clickhouse_url="http://clickhouse"),
    )
    monkeypatch.setattr(
        module.ClickHouseClient, "from_env", lambda _endpoint: _DummyClient()
    )

    output_path = tmp_path / "task-1-baseline-shared-host.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collect_hot_query_log.py",
            "--query-id",
            "abc123",
            "--limit",
            "1",
            "--output",
            str(output_path),
        ],
    )

    result = module.main()

    assert result == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "task-1-query-log-v1"
    assert payload["source"] == "system.query_log"
    assert payload["row_count"] == 1
    assert payload["filters"] == {
        "query_ids": ["abc123"],
        "since_seconds": None,
        "limit": 1,
    }
    normalized = payload["rows"][0]
    assert normalized["query_duration_ms"] == 23
    assert normalized["read_rows"] == 42
    assert normalized["read_bytes"] == 4096
    assert normalized["memory_usage"] == 8192
    assert normalized["exception"] is None
    assert normalized["query_text_hash"] == hashlib.sha256(b"SELECT 1").hexdigest()
