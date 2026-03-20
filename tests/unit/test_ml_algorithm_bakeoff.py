from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from poe_trade.ml import workflows


def _client() -> workflows.ClickHouseClient:
    return cast(workflows.ClickHouseClient, cast(object, SimpleNamespace()))


def test_compare_single_item_algorithms_ranks_modes(monkeypatch) -> None:
    monkeypatch.setattr(workflows, "_ensure_supported_league", lambda _league: None)

    def _eval(_client, *, prediction_mode: str, **_kwargs):
        table = {
            "ml": {
                "overall": {
                    "count": 10,
                    "relative_abs_error_mean": 0.20,
                    "extreme_miss_rate": 0.10,
                    "band_hit_rate": 0.40,
                    "abstain_rate": 0.10,
                }
            },
            "anchor": {
                "overall": {
                    "count": 10,
                    "relative_abs_error_mean": 0.15,
                    "extreme_miss_rate": 0.07,
                    "band_hit_rate": 0.45,
                    "abstain_rate": 0.10,
                }
            },
            "hybrid": {
                "overall": {
                    "count": 10,
                    "relative_abs_error_mean": 0.12,
                    "extreme_miss_rate": 0.05,
                    "band_hit_rate": 0.52,
                    "abstain_rate": 0.09,
                }
            },
        }
        return table[prediction_mode]

    monkeypatch.setattr(workflows, "evaluate_serving_path", _eval)
    monkeypatch.setattr(
        workflows,
        "_evaluate_reset_windows",
        lambda *_args, **_kwargs: {"enabled": False, "windows": {}},
    )

    payload = workflows.compare_single_item_algorithms(
        _client(),
        league="Mirage",
        dataset_table="poe_trade.ml_price_dataset_v2",
        limit=100,
    )

    assert payload["winner"] == "hybrid"
    assert payload["decision"]["approved"] is True


def test_predict_single_item_mode_anchor_uses_anchor_signal(monkeypatch) -> None:
    monkeypatch.setattr(
        workflows,
        "_parse_clipboard_item",
        lambda _text: {
            "base_type": "Hubris Circlet",
            "rarity": "Rare",
            "category": "helmet",
        },
    )
    monkeypatch.setattr(
        workflows,
        "_route_for_item",
        lambda _item: {"route": "structured_boosted", "route_reason": "ok"},
    )
    monkeypatch.setattr(
        workflows,
        "_anchor_price_for_item",
        lambda *_args, **_kwargs: {
            "anchor_price": 18.0,
            "credible_low": 15.0,
            "credible_high": 21.0,
            "support_count": 40,
        },
    )

    payload = workflows._predict_single_item_mode(
        _client(),
        league="Mirage",
        clipboard_text="dummy",
        mode="anchor",
    )

    assert payload["price_p50"] == 18.0
    assert payload["support_count_recent"] == 40
