from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from poe_trade.strategy import policy


def _candidate(
    *,
    key: str,
    ts: datetime,
    league: str = "Mirage",
    expected_profit_chaos: float | None = 10.0,
    expected_roi: float | None = 0.4,
    confidence: float | None = 0.8,
    sample_count: int | None = 30,
    legacy_keys: tuple[str, ...] = (),
) -> policy.CandidateRow:
    return policy.CandidateRow(
        strategy_id="bulk_essence",
        league=league,
        item_or_market_key=key,
        candidate_ts=ts,
        expected_profit_chaos=expected_profit_chaos,
        expected_roi=expected_roi,
        confidence=confidence,
        sample_count=sample_count,
        legacy_item_or_market_keys=legacy_keys,
    )


def test_evaluate_candidates_respects_minima_boundaries() -> None:
    base_ts = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    strategy_policy = policy.StrategyPolicy(
        min_expected_profit_chaos=10.0,
        min_expected_roi=0.3,
        min_confidence=0.8,
        min_sample_count=20,
    )
    exact = _candidate(key="k-exact", ts=base_ts)
    below_profit = _candidate(key="k-profit", ts=base_ts, expected_profit_chaos=9.99)
    below_roi = _candidate(key="k-roi", ts=base_ts, expected_roi=0.29)
    below_conf = _candidate(key="k-conf", ts=base_ts, confidence=0.79)
    below_samples = _candidate(key="k-samples", ts=base_ts, sample_count=19)

    evaluation = policy.evaluate_candidates(
        [exact, below_profit, below_roi, below_conf, below_samples],
        policy=strategy_policy,
        requested_league="Mirage",
    )

    assert [row.item_or_market_key for row in evaluation.eligible] == ["k-exact"]
    reasons = {
        decision.candidate.item_or_market_key: decision.reason
        for decision in evaluation.decisions
        if not decision.accepted
    }
    assert reasons["k-profit"] == policy.REJECTED_MIN_EXPECTED_PROFIT
    assert reasons["k-roi"] == policy.REJECTED_MIN_EXPECTED_ROI
    assert reasons["k-conf"] == policy.REJECTED_MIN_CONFIDENCE
    assert reasons["k-samples"] == policy.REJECTED_MIN_SAMPLE_COUNT


def test_evaluate_candidates_filters_league_and_requires_journal_state() -> None:
    base_ts = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    candidate = _candidate(key="sem:essence:deafening_anger", ts=base_ts)
    off_league = _candidate(key="sem:other", ts=base_ts, league="Standard")

    league_eval = policy.evaluate_candidates(
        [candidate, off_league],
        policy=policy.StrategyPolicy(),
        requested_league="Mirage",
    )
    assert [row.item_or_market_key for row in league_eval.eligible] == [
        "sem:essence:deafening_anger"
    ]
    rejected = [
        decision
        for decision in league_eval.decisions
        if decision.reason == policy.REJECTED_LEAGUE
    ]
    assert len(rejected) == 1
    assert rejected[0].candidate.item_or_market_key == "sem:other"

    journal_policy = policy.StrategyPolicy(requires_journal=True)
    no_journal_eval = policy.evaluate_candidates(
        [candidate],
        policy=journal_policy,
        requested_league="Mirage",
        journal_active_keys=set(),
    )
    assert no_journal_eval.eligible == ()
    assert no_journal_eval.decisions[0].reason == policy.REJECTED_JOURNAL_REQUIRED

    with_journal_eval = policy.evaluate_candidates(
        [_candidate(key="sem:new", ts=base_ts, legacy_keys=("legacy-hash",))],
        policy=journal_policy,
        requested_league="Mirage",
        journal_active_keys={"legacy-hash"},
    )
    assert [row.item_or_market_key for row in with_journal_eval.eligible] == ["sem:new"]


def test_evaluate_candidates_replays_cooldown_against_candidate_timestamp() -> None:
    previous_alert = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
    strategy_policy = policy.StrategyPolicy(cooldown_minutes=180)
    too_soon = _candidate(
        key="semantic-key",
        ts=previous_alert + timedelta(minutes=179),
        legacy_keys=("legacy-hash",),
    )
    after_window = _candidate(
        key="semantic-key-2",
        ts=previous_alert + timedelta(minutes=181),
        legacy_keys=("legacy-hash-2",),
    )

    evaluation = policy.evaluate_candidates(
        [too_soon, after_window],
        policy=strategy_policy,
        requested_league="Mirage",
        last_alerted_at_by_key={
            "semantic-key": previous_alert,
            "legacy-hash-2": previous_alert,
        },
    )

    assert [row.item_or_market_key for row in evaluation.eligible] == ["semantic-key-2"]
    cooldown_rejections = [
        decision
        for decision in evaluation.decisions
        if decision.reason == policy.REJECTED_COOLDOWN_ACTIVE
    ]
    assert len(cooldown_rejections) == 1
    assert cooldown_rejections[0].candidate.item_or_market_key == "semantic-key"
    assert cooldown_rejections[0].blocked_by_key == "semantic-key"


def test_evaluate_candidates_cooldown_blocks_against_legacy_history() -> None:
    previous_alert = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
    strategy_policy = policy.StrategyPolicy(cooldown_minutes=180)
    candidate = _candidate(
        key="sem:legacy-block",
        ts=previous_alert + timedelta(minutes=179),
        legacy_keys=("legacy-hash",),
    )

    evaluation = policy.evaluate_candidates(
        [candidate],
        policy=strategy_policy,
        requested_league="Mirage",
        last_alerted_at_by_key={"legacy-hash": previous_alert},
    )

    assert evaluation.eligible == ()
    rejection = next(
        decision
        for decision in evaluation.decisions
        if decision.reason == policy.REJECTED_COOLDOWN_ACTIVE
    )
    assert rejection.candidate.item_or_market_key == "sem:legacy-block"
    assert rejection.blocked_by_key == "legacy-hash"


def test_dedupe_candidates_is_deterministic_with_tie_breaks() -> None:
    base_ts = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    high_profit = _candidate(key="dup", ts=base_ts, expected_profit_chaos=20.0)
    low_profit = _candidate(key="dup", ts=base_ts, expected_profit_chaos=5.0)
    high_profit_newer = _candidate(
        key="dup",
        ts=base_ts + timedelta(minutes=1),
        expected_profit_chaos=20.0,
    )

    first_pass = policy.dedupe_candidates([low_profit, high_profit, high_profit_newer])
    second_pass = policy.dedupe_candidates([high_profit_newer, high_profit, low_profit])
    assert [row.item_or_market_key for row in first_pass] == ["dup"]
    assert [row.item_or_market_key for row in second_pass] == ["dup"]
    assert first_pass[0].candidate_ts == high_profit_newer.candidate_ts
    assert second_pass[0].candidate_ts == high_profit_newer.candidate_ts

    evaluated = policy.evaluate_candidates(
        [low_profit, high_profit, high_profit_newer],
        policy=policy.StrategyPolicy(),
        requested_league="Mirage",
    )
    duplicate_reasons = [
        decision.reason for decision in evaluated.decisions if not decision.accepted
    ]
    assert duplicate_reasons.count(policy.REJECTED_DUPLICATE) == 2


def test_normalize_compatibility_keys_and_evidence_snapshot() -> None:
    keys = policy.normalize_compatibility_keys(
        "semantic", ["", "legacy-a", "legacy-a", "semantic", "legacy-b"]
    )
    assert keys == ("semantic", "legacy-a", "legacy-b")

    ts = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    candidate = policy.CandidateRow(
        strategy_id="bulk_essence",
        league="Mirage",
        item_or_market_key="semantic",
        candidate_ts=ts,
        expected_profit_chaos=12.0,
        expected_roi=0.5,
        confidence=0.9,
        sample_count=40,
        legacy_item_or_market_keys=("legacy-a",),
        evidence={"summary": "bulk spread", "league": "Mirage-override"},
    )

    snapshot = policy.build_evidence_snapshot(candidate)
    assert snapshot["summary"] == "bulk spread"
    assert snapshot["league"] == "Mirage-override"
    assert snapshot["item_or_market_key"] == "semantic"
    assert snapshot["legacy_item_or_market_keys"] == ["legacy-a"]
    assert snapshot["time_bucket"] == ts.isoformat()


def test_candidate_from_source_row_uses_semantic_key_as_canonical_identity() -> None:
    candidate = policy.candidate_from_source_row(
        "bulk_essence",
        {
            "time_bucket": "2026-03-15 12:00:00",
            "league": "Mirage",
            "semantic_key": "semantic-key",
            "item_or_market_key": "source-key",
            "expected_profit_chaos": 12.0,
            "expected_roi": 0.5,
            "confidence": 0.8,
            "bulk_listing_count": 44,
            "legacy_item_or_market_keys": ["legacy-extra", "source-key"],
            "legacy_hashed_item_or_market_key": "legacy-hash",
        },
    )

    assert candidate.item_or_market_key == "semantic-key"
    assert candidate.sample_count == 44
    assert candidate.legacy_item_or_market_keys == (
        "source-key",
        "legacy-hash",
        "legacy-extra",
    )
    assert policy.candidate_cooldown_keys(candidate) == (
        "semantic-key",
        "source-key",
        "legacy-hash",
        "legacy-extra",
    )
    assert candidate.evidence["legacy_hashed_item_or_market_key"] == "legacy-hash"
    assert candidate.evidence["source_row_json"]

    snapshot = policy.build_evidence_snapshot(candidate)
    assert snapshot["item_or_market_key"] == "semantic-key"
    assert snapshot["source_item_or_market_key"] == "source-key"
    assert snapshot["legacy_item_or_market_keys"] == [
        "source-key",
        "legacy-hash",
        "legacy-extra",
    ]


@pytest.mark.parametrize(
    "source_row",
    [
        {"time_bucket": "2026-03-15 12:00:00", "league": "Mirage"},
        {
            "time_bucket": "2026-03-15 12:00:00",
            "league": "Mirage",
            "semantic_key": "   ",
        },
    ],
)
def test_candidate_from_source_row_rejects_missing_or_blank_semantic_key(
    source_row: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="candidate row missing semantic_key"):
        _ = policy.candidate_from_source_row("bulk_essence", source_row)


def test_public_pack_and_candidate_helpers_preserve_runtime_compatibility() -> None:
    pack = type(
        "Pack",
        (),
        {
            "min_expected_profit_chaos": "10.5",
            "min_expected_roi": "0.2",
            "min_confidence": "0.7",
            "min_sample_count": "12",
            "cooldown_minutes": "180",
            "requires_journal": False,
        },
    )()
    strategy_policy = policy.policy_from_pack(pack)
    assert strategy_policy.min_expected_profit_chaos == 10.5
    assert strategy_policy.min_sample_count == 12
    assert strategy_policy.cooldown_minutes == 180
