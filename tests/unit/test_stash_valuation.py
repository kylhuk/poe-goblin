from __future__ import annotations

from typing import Any, cast

from poe_trade import stash_valuation


def test_fingerprint_prefers_item_id_when_present() -> None:
    item = {"id": "abc", "name": "Chaos Orb", "x": 0, "y": 0}
    assert (
        stash_valuation.fingerprint_item(item, account_name="qa", tab_id="t1")
        == "item:abc"
    )


def test_fingerprint_falls_back_to_deterministic_content_hash() -> None:
    item = {"name": "Hubris Circlet", "typeLine": "Hubris Circlet", "x": 1, "y": 2}
    value = stash_valuation.fingerprint_item(item, account_name="qa", tab_id="t2")
    assert value.startswith("fp:")


def test_stash_prediction_contract_keeps_price_confidence_and_band_fields() -> None:
    result = stash_valuation.normalize_stash_prediction(
        {
            "predictedValue": 10.0,
            "confidence": 82.0,
            "interval": {"p10": 8.0, "p90": 14.0},
        }
    )
    assert result.price_p10 == 8.0
    assert result.price_p90 == 14.0
    assert result.confidence == 82.0


def test_serialize_stash_item_to_predict_one_clipboard_contains_name_and_mod_lines() -> (
    None
):
    item = {
        "name": "Grim Bane",
        "typeLine": "Hubris Circlet",
        "explicitMods": ["+93 to maximum Life"],
    }
    clipboard = stash_valuation.serialize_stash_item_to_clipboard(item)
    assert "Grim Bane" in clipboard
    assert "Hubris Circlet" in clipboard
    assert "+93 to maximum Life" in clipboard


def test_estimate_item_uses_fetch_predict_one_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        stash_valuation,
        "_fetch_predict_one",
        lambda *_args, **_kwargs: {
            "predictedValue": 12.0,
            "confidence": 77.0,
            "interval": {"p10": 9.0, "p90": 16.0},
        },
    )
    result = stash_valuation.estimate_item(
        client=cast(Any, object()), league="Mirage", item_text="Rarity: Rare"
    )
    assert result.predicted_price == 12.0
    assert result.price_p90 == 16.0
