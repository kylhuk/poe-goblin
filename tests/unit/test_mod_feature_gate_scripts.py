from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_script_module(script_name: str) -> ModuleType:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluate_cutover_gate_loads_json_settings(tmp_path: Path) -> None:
    module = _load_script_module("evaluate_cutover_gate.py")
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "max_memory_usage": "1610612736",
                "max_threads": "4",
                "max_execution_time": "180",
                "max_bytes_before_external_group_by": "268435456",
                "max_bytes_before_external_sort": "268435456",
            }
        ),
        encoding="utf-8",
    )

    result = module._load_settings_evidence(str(settings_path))

    assert result["max_memory_usage"] == "1610612736"
    assert result["max_threads"] == "4"


def test_final_release_gate_accepts_json_runbook_status() -> None:
    module = _load_script_module("final_release_gate.py")

    assert module._runbook_check_passed('{"status": "OK"}') is True
    assert module._runbook_check_passed('{"status": "missing"}') is False
