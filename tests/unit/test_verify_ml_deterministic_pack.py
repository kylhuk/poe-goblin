from __future__ import annotations

import json
import importlib.util
from pathlib import Path


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "verify_ml_deterministic_pack.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "verify_ml_deterministic_pack", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
verify_ml_deterministic_pack = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(verify_ml_deterministic_pack)


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_verify_ml_deterministic_pack_passes_with_expected_shape(tmp_path, monkeypatch):
    _write(
        tmp_path / "task-1-baseline.json",
        {"latency_ms": {"p95": 10}, "p50_ms": 5, "p95_ms": 10, "corpus_hash": "abc"},
    )
    _write(
        tmp_path / "task-10-promotion-gates.json",
        {
            "status": "ok",
            "gate_results": {},
            "summary": {
                "verdict": "promote",
                "mdape_relative_improvement": 0.24,
                "p95_latency_improvement_percent": 51.0,
                "protected_cohort_degradation_count": 0,
            },
            "all_passed": True,
        },
    )
    _write(
        tmp_path / "task-11-rollout-cutover.json",
        {
            "status": "ok",
            "rollout": {"cutover": True},
            "effectiveServingModelVersion": "mirage-v2",
            "lastAction": "enable_cutover",
        },
    )
    _write(
        tmp_path / "task-11-rollout-rollback.json",
        {
            "status": "ok",
            "rollout": {"cutover": False},
            "effectiveServingModelVersion": "mirage-v1",
            "lastAction": "rollback_to_incumbent",
        },
    )

    output_log = tmp_path / "pack.log"
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_ml_deterministic_pack.py",
            "--evidence-root",
            str(tmp_path),
            "--output-log",
            str(output_log),
        ],
    )

    result = verify_ml_deterministic_pack.main()

    assert result == 0
    payload = json.loads(output_log.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["missing"] == []
    assert payload["invalid"] == []


def test_verify_ml_deterministic_pack_fails_on_invalid_payload(tmp_path, monkeypatch):
    _write(
        tmp_path / "task-1-baseline.json",
        {"latency_ms": {"p95": 10}, "p50_ms": 5, "p95_ms": 10, "corpus_hash": "abc"},
    )
    _write(
        tmp_path / "task-10-promotion-gates.json",
        {
            "status": "ok",
            "gate_results": {},
            "summary": {
                "verdict": "hold",
                "mdape_relative_improvement": 0.01,
                "p95_latency_improvement_percent": 10.0,
                "protected_cohort_degradation_count": 2,
            },
            "all_passed": False,
        },
    )
    _write(
        tmp_path / "task-11-rollout-cutover.json",
        {
            "status": "ok",
            "rollout": {"cutover": True},
            "effectiveServingModelVersion": "mirage-v2",
            "lastAction": "enable_cutover",
        },
    )
    _write(tmp_path / "task-11-rollout-rollback.json", {"unexpected": True})

    output_log = tmp_path / "pack-error.log"
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_ml_deterministic_pack.py",
            "--evidence-root",
            str(tmp_path),
            "--output-log",
            str(output_log),
        ],
    )

    result = verify_ml_deterministic_pack.main()

    assert result == 1
    payload = json.loads(output_log.read_text(encoding="utf-8"))
    assert payload["status"] == "missing_or_invalid_artifacts"
    assert payload["missing"] == []
    assert any(
        entry.startswith("task-10-promotion-gates.json") for entry in payload["invalid"]
    )
