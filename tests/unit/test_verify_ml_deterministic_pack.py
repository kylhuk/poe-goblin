from __future__ import annotations

import importlib.util
from pathlib import Path

from poe_trade.ml.v3 import benchmark


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "verify_ml_deterministic_pack.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "verify_ml_deterministic_pack", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
verify_ml_deterministic_pack = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(verify_ml_deterministic_pack)


def _row(index: int) -> dict[str, object]:
    price = 50.0 + (index * 4.0)
    return {
        "as_of_ts": f"2026-03-{20 + index:02d} 10:00:00.000",
        "realm": "pc",
        "league": "Mirage",
        "stash_id": f"stash-{index}",
        "item_id": f"item-{index}",
        "identity_key": f"item-{index}",
        "route": "sparse_retrieval",
        "strategy_family": "sparse_retrieval",
        "cohort_key": f"sparse_retrieval|helmet|v1|{index}",
        "parent_cohort_key": f"sparse_retrieval|helmet|v1|{index}",
        "material_state_signature": f"v1|{index}",
        "category": "helmet" if index % 2 == 0 else "ring",
        "item_name": f"Item {index}",
        "item_type_line": "Hubris Circlet",
        "base_type": "Hubris Circlet",
        "rarity": "Rare",
        "ilvl": 80 + (index % 5),
        "stack_size": 1,
        "corrupted": index % 2,
        "fractured": 0,
        "synthesised": 0,
        "item_state_key": f"rare|corrupted={index % 2}|fractured=0|synthesised=0",
        "support_count_recent": 20 + index * 3,
        "feature_vector_json": f'{{"ilvl": {80 + (index % 5)}, "stack_size": 1}}',
        "mod_features_json": f'{{"explicit.max_life": {1.0 + (index * 0.1)}}}',
        "target_price_chaos": price,
        "target_fast_sale_24h_price": price * 0.92,
        "target_sale_probability_24h": 0.75,
        "target_likely_sold": 1,
        "sale_confidence_flag": 1,
        "target_time_to_exit_hours": 8.0,
        "target_sale_price_anchor_chaos": price * 0.95,
        "label_weight": 0.8,
        "label_source": "benchmark_disappearance_proxy_h48_v1",
        "split_bucket": "train",
    }


def test_verify_ml_deterministic_pack_passes_with_benchmark_artifacts(
    tmp_path, monkeypatch
):
    rows = [_row(index) for index in range(12)]
    report = benchmark.save_benchmark_artifacts(
        rows, tmp_path / "ml-pricing-benchmark-update.txt"
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
    assert report["artifacts"]["markdown"] == str(
        tmp_path / "ml-pricing-benchmark-update.txt"
    )
    assert output_log.exists()


def test_verify_ml_deterministic_pack_fails_when_top_single_model_missing(
    tmp_path, monkeypatch
):
    rows = [_row(index) for index in range(12)]
    benchmark.save_benchmark_artifacts(
        rows, tmp_path / "ml-pricing-benchmark-update.txt"
    )
    report_path = tmp_path / "ml-pricing-benchmark-update.txt"
    report_path.write_text(
        "\n".join(
            line
            for line in report_path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("Top single-model:")
        )
        + "\n",
        encoding="utf-8",
    )

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
    assert "missing_top_single_model" in output_log.read_text(encoding="utf-8")
