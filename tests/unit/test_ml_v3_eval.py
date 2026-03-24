from __future__ import annotations

import pytest

from poe_trade.ml.v3 import eval as v3_eval


def test_promotion_gate_auto_eligible_when_numeric_thresholds_and_windows_met() -> None:
    gate = v3_eval.promotion_gate(
        sample_count=600,
        global_fair_value_mdape=0.2,
        incumbent_fair_value_mdape=0.32,
        global_fast_sale_hit_rate=0.65,
        incumbent_fast_sale_hit_rate=0.66,
        global_sale_probability_calibration_error=0.1,
        global_confidence_calibration_error=0.12,
        global_abstain_rate=0.05,
        incumbent_abstain_rate=0.0,
        consecutive_pass_windows=3,
        worst_slice_mdape=0.35,
    )

    assert gate["passed"] is True
    assert gate["decision"] == "auto"
    assert gate["auto_promotion_eligible"] is True
    assert gate["manual_review_required"] is False
    assert gate["reason"] == "pass"


def test_promotion_gate_candidate_band_requires_manual_review() -> None:
    gate = v3_eval.promotion_gate(
        sample_count=220,
        global_fair_value_mdape=0.2,
        incumbent_fair_value_mdape=0.3,
        global_fast_sale_hit_rate=0.62,
        incumbent_fast_sale_hit_rate=0.63,
        global_sale_probability_calibration_error=0.1,
        global_confidence_calibration_error=0.1,
        global_abstain_rate=0.03,
        incumbent_abstain_rate=0.01,
        consecutive_pass_windows=3,
        worst_slice_mdape=0.3,
    )

    assert gate["passed"] is False
    assert gate["decision"] == "candidate_manual"
    assert gate["auto_promotion_eligible"] is False
    assert gate["manual_review_required"] is True
    assert gate["reason"] == "candidate_manual_review"


def test_promotion_gate_rejects_when_required_preconditions_missing() -> None:
    gate = v3_eval.promotion_gate(
        global_fair_value_mdape=0.2,
        incumbent_fair_value_mdape=0.3,
        global_fast_sale_hit_rate=0.62,
        incumbent_fast_sale_hit_rate=0.63,
        global_sale_probability_calibration_error=0.1,
        global_confidence_calibration_error=0.1,
        global_abstain_rate=0.03,
        incumbent_abstain_rate=0.01,
        worst_slice_mdape=0.3,
    )

    assert gate["passed"] is False
    assert gate["decision"] == "reject"
    assert "sample_count_required" in str(gate["reason"])
    assert "consecutive_windows_required" in str(gate["reason"])


def test_promotion_gate_enforces_abstain_absolute_cap() -> None:
    gate = v3_eval.promotion_gate(
        sample_count=600,
        global_fair_value_mdape=0.2,
        incumbent_fair_value_mdape=0.3,
        global_fast_sale_hit_rate=0.62,
        incumbent_fast_sale_hit_rate=0.63,
        global_sale_probability_calibration_error=0.1,
        global_confidence_calibration_error=0.1,
        global_abstain_rate=0.051,
        incumbent_abstain_rate=0.001,
        consecutive_pass_windows=3,
        worst_slice_mdape=0.3,
    )

    assert gate["passed"] is False
    assert "abstain_rate_absolute_cap" in str(gate["reason"])


def test_promotion_gate_handles_zero_incumbent_mdape_safely() -> None:
    gate = v3_eval.promotion_gate(
        sample_count=600,
        global_fair_value_mdape=0.01,
        incumbent_fair_value_mdape=0.0,
        global_fast_sale_hit_rate=0.62,
        incumbent_fast_sale_hit_rate=0.63,
        global_sale_probability_calibration_error=0.1,
        global_confidence_calibration_error=0.1,
        global_abstain_rate=0.03,
        incumbent_abstain_rate=0.01,
        consecutive_pass_windows=3,
        worst_slice_mdape=0.3,
    )

    assert gate["passed"] is False
    assert "incumbent_mdape_nonpositive" in str(gate["reason"])


def test_promotion_gate_accepts_exact_cutoff_values() -> None:
    gate = v3_eval.promotion_gate(
        sample_count=500,
        global_fair_value_mdape=0.3,
        incumbent_fair_value_mdape=0.36,
        global_fast_sale_hit_rate=0.6,
        incumbent_fast_sale_hit_rate=0.619,
        global_sale_probability_calibration_error=0.2,
        global_confidence_calibration_error=0.2,
        global_abstain_rate=0.05,
        incumbent_abstain_rate=0.0,
        consecutive_pass_windows=3,
        worst_slice_mdape=0.45,
    )

    assert gate["passed"] is True
    assert gate["decision"] == "auto"


def test_promotion_gate_treats_sample_count_150_as_candidate_manual() -> None:
    gate = v3_eval.promotion_gate(
        sample_count=150,
        global_fair_value_mdape=0.2,
        incumbent_fair_value_mdape=0.3,
        global_fast_sale_hit_rate=0.62,
        incumbent_fast_sale_hit_rate=0.63,
        global_sale_probability_calibration_error=0.1,
        global_confidence_calibration_error=0.1,
        global_abstain_rate=0.04,
        incumbent_abstain_rate=0.01,
        consecutive_pass_windows=3,
        worst_slice_mdape=0.3,
    )

    assert gate["passed"] is False
    assert gate["decision"] == "candidate_manual"


@pytest.mark.parametrize(
    (
        "overrides",
        "expected_reason",
    ),
    [
        ({"sample_count": 149}, "sample_count_below_candidate_min"),
        ({"consecutive_pass_windows": 2}, "insufficient_consecutive_windows"),
        ({"global_fair_value_mdape": 0.26}, "mdape_abs_improvement"),
        (
            {"global_fair_value_mdape": 0.5, "incumbent_fair_value_mdape": 0.55},
            "mdape_rel_improvement",
        ),
        ({"global_fast_sale_hit_rate": 0.61}, "fast_sale_hit_rate_degradation"),
        ({"global_sale_probability_calibration_error": 0.21}, "sale_calibration"),
        ({"global_confidence_calibration_error": 0.21}, "confidence_calibration"),
        ({"global_abstain_rate": 0.08}, "abstain_rate_increase"),
        ({"worst_slice_mdape": 0.5}, "worst_slice"),
    ],
)
def test_promotion_gate_reports_specific_failure_reasons(
    overrides: dict[str, float | int],
    expected_reason: str,
) -> None:
    kwargs: dict[str, float | int | None] = {
        "sample_count": 600,
        "global_fair_value_mdape": 0.2,
        "incumbent_fair_value_mdape": 0.3,
        "global_fast_sale_hit_rate": 0.63,
        "incumbent_fast_sale_hit_rate": 0.63,
        "global_sale_probability_calibration_error": 0.1,
        "global_confidence_calibration_error": 0.1,
        "global_abstain_rate": 0.04,
        "incumbent_abstain_rate": 0.01,
        "consecutive_pass_windows": 3,
        "worst_slice_mdape": 0.3,
    }
    kwargs.update(overrides)

    gate = v3_eval.promotion_gate(**kwargs)

    assert gate["passed"] is False
    assert gate["decision"] == "reject"
    assert expected_reason in str(gate["reason"])


def test_depromotion_gate_triggers_for_mdape_regression_two_windows() -> None:
    gate = v3_eval.depromotion_gate(
        current_fair_value_mdape=0.27,
        incumbent_fair_value_mdape=0.2,
        current_fast_sale_hit_rate=0.6,
        incumbent_fast_sale_hit_rate=0.61,
        trailing_7d_sample_count=350,
        mdape_regression_consecutive_windows=2,
        fast_sale_degradation_consecutive_windows=0,
    )

    assert gate["triggered"] is True
    assert "mdape_regression" in str(gate["reason"])


def test_depromotion_gate_triggers_for_fast_sale_degradation_two_windows() -> None:
    gate = v3_eval.depromotion_gate(
        current_fair_value_mdape=0.21,
        incumbent_fair_value_mdape=0.2,
        current_fast_sale_hit_rate=0.55,
        incumbent_fast_sale_hit_rate=0.59,
        trailing_7d_sample_count=350,
        mdape_regression_consecutive_windows=0,
        fast_sale_degradation_consecutive_windows=2,
    )

    assert gate["triggered"] is True
    assert "fast_sale_hit_rate_degradation" in str(gate["reason"])


def test_depromotion_gate_triggers_for_low_trailing_sample() -> None:
    gate = v3_eval.depromotion_gate(
        current_fair_value_mdape=0.21,
        incumbent_fair_value_mdape=0.2,
        current_fast_sale_hit_rate=0.58,
        incumbent_fast_sale_hit_rate=0.59,
        trailing_7d_sample_count=99,
        mdape_regression_consecutive_windows=0,
        fast_sale_degradation_consecutive_windows=0,
    )

    assert gate["triggered"] is True
    assert "trailing_7d_sample_count" in str(gate["reason"])


def test_depromotion_gate_exposes_latency_and_error_budget_hooks() -> None:
    gate = v3_eval.depromotion_gate(
        current_fair_value_mdape=0.21,
        incumbent_fair_value_mdape=0.2,
        current_fast_sale_hit_rate=0.58,
        incumbent_fast_sale_hit_rate=0.59,
        trailing_7d_sample_count=350,
        mdape_regression_consecutive_windows=0,
        fast_sale_degradation_consecutive_windows=0,
        latency_budget_breached=True,
        error_budget_breached=True,
    )

    assert gate["triggered"] is True
    assert gate["latency_budget_breached"] is True
    assert gate["error_budget_breached"] is True
    assert "latency_budget_breach" in str(gate["reason"])
    assert "error_budget_breach" in str(gate["reason"])


def test_depromotion_gate_not_triggered_at_exact_threshold_edges() -> None:
    gate = v3_eval.depromotion_gate(
        current_fair_value_mdape=0.25,
        incumbent_fair_value_mdape=0.2,
        current_fast_sale_hit_rate=0.56,
        incumbent_fast_sale_hit_rate=0.59,
        trailing_7d_sample_count=100,
        mdape_regression_consecutive_windows=1,
        fast_sale_degradation_consecutive_windows=1,
        latency_budget_breached=False,
        error_budget_breached=False,
    )

    assert gate["triggered"] is False
    assert gate["reason"] == "pass"


def test_evaluate_run_records_route_and_summary_rows(monkeypatch) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []

    monkeypatch.setattr(
        v3_eval,
        "_query_rows",
        lambda *_args, **_kwargs: [
            {
                "route": "sparse_retrieval",
                "strategy_family": "sparse_retrieval",
                "cohort_key": "sparse_retrieval|default|v1|rare|0|0|0",
                "sample_count": 600,
                "fair_value_mdape": 0.25,
                "fair_value_wape": 0.3,
                "fast_sale_24h_hit_rate": 0.6,
                "fast_sale_24h_mdape": 0.18,
                "sale_probability_calibration_error": 0.1,
                "confidence_calibration_error": 0.12,
            }
        ],
    )
    monkeypatch.setattr(
        v3_eval,
        "_insert_json_rows",
        lambda _client, table, rows: inserted.append((table, rows)),
    )

    payload = v3_eval.evaluate_run(
        object(),
        league="Mirage",
        run_id="run-123",
    )

    assert payload["summary"]["run_id"] == "run-123"
    assert payload["summary"]["model_version"] == "run-123"
    assert payload["summary"]["gate_passed"] == 0
    assert "consecutive_windows_required" in str(payload["summary"]["gate_reason"])
    assert payload["metrics"]["global_fast_sale_24h_mdape"] == 0.18
    assert inserted[0][0] == v3_eval.ROUTE_EVAL_TABLE
    assert inserted[1][0] == v3_eval.COHORT_EVAL_TABLE
    assert inserted[2][0] == v3_eval.EVAL_RUNS_TABLE


def test_evaluate_run_passes_gate_with_history_and_incumbent_baseline_across_run_ids(
    monkeypatch,
) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []
    stable_model_version = "ml_v3_stable_2026_03"

    def query_rows(_client, query: str):
        if f"FROM {v3_eval.PREDICTIONS_TABLE} AS pred" in query:
            return [
                {
                    "route": "sparse_retrieval",
                    "strategy_family": "sparse_retrieval",
                    "cohort_key": "sparse_retrieval|default|v1|rare|0|0|0",
                    "sample_count": 700,
                    "fair_value_mdape": 0.2,
                    "fair_value_wape": 0.25,
                    "fast_sale_24h_hit_rate": 0.7,
                    "fast_sale_24h_mdape": 0.14,
                    "sale_probability_calibration_error": 0.08,
                    "confidence_calibration_error": 0.1,
                    "engine_version": stable_model_version,
                }
            ]
        if (
            f"FROM {v3_eval.EVAL_RUNS_TABLE}" in query
            and "model_version" in query
            and "gate_passed = 1" not in query
            and f"model_version = '{stable_model_version}'" in query
        ):
            return [
                {
                    "run_id": "run-prev-2",
                    "gate_passed": 1,
                    "recorded_at": "2026-03-23 00:00:00.000",
                },
                {
                    "run_id": "run-prev-1",
                    "gate_passed": 1,
                    "recorded_at": "2026-03-22 00:00:00.000",
                },
            ]
        if f"FROM {v3_eval.EVAL_RUNS_TABLE}" in query and "gate_passed = 1" in query:
            return [
                {
                    "run_id": "incumbent-1",
                    "global_fair_value_mdape": 0.3,
                    "global_fast_sale_24h_hit_rate": 0.719,
                }
            ]
        if f"FROM {v3_eval.ROUTE_EVAL_TABLE}" in query:
            return [{"sample_count": 1000, "abstain_rate": 0.0}]
        return []

    monkeypatch.setattr(v3_eval, "_query_rows", query_rows)
    monkeypatch.setattr(
        v3_eval,
        "_insert_json_rows",
        lambda _client, table, rows: inserted.append((table, rows)),
    )

    payload = v3_eval.evaluate_run(object(), league="Mirage", run_id="run-promote")

    assert payload["summary"]["gate_passed"] == 1
    assert payload["summary"]["gate_reason"] == "pass"
    assert payload["summary"]["run_id"] == "run-promote"
    assert payload["summary"]["model_version"] == stable_model_version
    eval_rows = next(
        rows for table, rows in inserted if table == v3_eval.EVAL_RUNS_TABLE
    )
    assert eval_rows[0]["run_id"] == "run-promote"
    assert eval_rows[0]["model_version"] == stable_model_version


def test_evaluate_run_uses_incumbent_mdape_baseline_for_gate(monkeypatch) -> None:
    def query_rows(_client, query: str):
        if f"FROM {v3_eval.PREDICTIONS_TABLE} AS pred" in query:
            return [
                {
                    "route": "sparse_retrieval",
                    "strategy_family": "sparse_retrieval",
                    "cohort_key": "sparse_retrieval|default|v1|rare|0|0|0",
                    "sample_count": 700,
                    "fair_value_mdape": 0.2,
                    "fair_value_wape": 0.25,
                    "fast_sale_24h_hit_rate": 0.7,
                    "fast_sale_24h_mdape": 0.14,
                    "sale_probability_calibration_error": 0.08,
                    "confidence_calibration_error": 0.1,
                }
            ]
        if (
            f"FROM {v3_eval.EVAL_RUNS_TABLE}" in query
            and "model_version" in query
            and "gate_passed = 1" not in query
        ):
            return [
                {"gate_passed": 1, "recorded_at": "2026-03-23 00:00:00.000"},
                {"gate_passed": 1, "recorded_at": "2026-03-22 00:00:00.000"},
            ]
        if f"FROM {v3_eval.EVAL_RUNS_TABLE}" in query and "gate_passed = 1" in query:
            return [
                {
                    "run_id": "incumbent-1",
                    "global_fair_value_mdape": 0.23,
                    "global_fast_sale_24h_hit_rate": 0.71,
                }
            ]
        if f"FROM {v3_eval.ROUTE_EVAL_TABLE}" in query:
            return [{"sample_count": 1000, "abstain_rate": 0.0}]
        return []

    monkeypatch.setattr(v3_eval, "_query_rows", query_rows)
    monkeypatch.setattr(v3_eval, "_insert_json_rows", lambda *_args, **_kwargs: None)

    payload = v3_eval.evaluate_run(object(), league="Mirage", run_id="run-mdape-gap")

    assert payload["summary"]["gate_passed"] == 0
    assert "mdape_abs_improvement" in str(payload["summary"]["gate_reason"])


def test_evaluate_run_writes_cohort_eval_rows(monkeypatch) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []

    monkeypatch.setattr(
        v3_eval,
        "_query_rows",
        lambda *_args, **_kwargs: [
            {
                "route": "sparse_retrieval",
                "strategy_family": "sparse_retrieval",
                "cohort_key": "sparse_retrieval|default|v1|rare|0|0|0",
                "sample_count": 80,
                "fair_value_mdape": 0.21,
                "fair_value_wape": 0.25,
                "fast_sale_24h_hit_rate": 0.7,
                "fast_sale_24h_mdape": 0.15,
                "sale_probability_calibration_error": 0.08,
                "confidence_calibration_error": 0.1,
            },
            {
                "route": "fallback_abstain",
                "strategy_family": "fallback_abstain",
                "cohort_key": "fallback_abstain|default|v1|rare|0|0|0",
                "sample_count": 20,
                "fair_value_mdape": 0.28,
                "fair_value_wape": 0.35,
                "fast_sale_24h_hit_rate": 0.56,
                "fast_sale_24h_mdape": 0.22,
                "sale_probability_calibration_error": 0.12,
                "confidence_calibration_error": 0.14,
            },
        ],
    )
    monkeypatch.setattr(
        v3_eval,
        "_insert_json_rows",
        lambda _client, table, rows: inserted.append((table, rows)),
    )

    v3_eval.evaluate_run(object(), league="Mirage", run_id="run-456")

    cohort_rows = next(
        rows for table, rows in inserted if table == v3_eval.COHORT_EVAL_TABLE
    )
    assert len(cohort_rows) == 2
    assert cohort_rows[0]["strategy_family"] == "sparse_retrieval"
    assert cohort_rows[0]["cohort_key"] == "sparse_retrieval|default|v1|rare|0|0|0"


def test_evaluate_run_rolls_up_eval_runs_once_per_run_and_league_from_cohort_rows(
    monkeypatch,
) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []

    monkeypatch.setattr(
        v3_eval,
        "_query_rows",
        lambda *_args, **_kwargs: [
            {
                "route": "sparse_retrieval",
                "strategy_family": "sparse_retrieval",
                "cohort_key": "sparse_retrieval|default|v1|rare|0|0|0",
                "sample_count": 900,
                "fair_value_mdape": 0.2,
                "fair_value_wape": 0.24,
                "fast_sale_24h_hit_rate": 0.7,
                "fast_sale_24h_mdape": 0.14,
                "sale_probability_calibration_error": 0.08,
                "confidence_calibration_error": 0.1,
            },
            {
                "route": "sparse_retrieval",
                "strategy_family": "sparse_retrieval",
                "cohort_key": "sparse_retrieval|cluster_jewel|v1|rare|0|0|0",
                "sample_count": 100,
                "fair_value_mdape": 0.9,
                "fair_value_wape": 0.95,
                "fast_sale_24h_hit_rate": 0.7,
                "fast_sale_24h_mdape": 0.2,
                "sale_probability_calibration_error": 0.08,
                "confidence_calibration_error": 0.1,
            },
        ],
    )
    monkeypatch.setattr(
        v3_eval,
        "_insert_json_rows",
        lambda _client, table, rows: inserted.append((table, rows)),
    )

    payload = v3_eval.evaluate_run(object(), league="Mirage", run_id="run-789")

    eval_rows = next(
        rows for table, rows in inserted if table == v3_eval.EVAL_RUNS_TABLE
    )
    assert len(eval_rows) == 1
    assert eval_rows[0]["run_id"] == "run-789"
    assert eval_rows[0]["league"] == "Mirage"
    assert eval_rows[0]["total_sample_count"] == 1000
    assert eval_rows[0]["gate_passed"] == 0
    assert "worst_slice" in str(eval_rows[0]["gate_reason"])
    assert payload["summary"]["gate_passed"] == 0
    route_rows = next(
        rows for table, rows in inserted if table == v3_eval.ROUTE_EVAL_TABLE
    )
    assert len(route_rows) == 1
    assert route_rows[0]["fair_value_mdape"] == pytest.approx(0.27)


def test_evaluate_run_builds_well_formed_sql_with_prediction_contract_fields(
    monkeypatch,
) -> None:
    queries: list[str] = []

    def capture_query(_client, query: str):
        queries.append(query)
        return []

    monkeypatch.setattr(v3_eval, "_query_rows", capture_query)

    payload = v3_eval.evaluate_run(object(), league="Mirage", run_id="run-sql")

    assert payload["status"] == "no_rows"
    assert len(queries) == 1
    query = queries[0]
    assert (
        "argMax(target_sale_probability_24h, as_of_ts) AS target_sale_probability_24h,"
        in query
    )
    assert "argMax(strategy_family, as_of_ts) AS strategy_family," in query
    assert "argMax(cohort_key, as_of_ts) AS cohort_key" in query
    assert (
        "ifNull(nullIf(nullIf(pred.strategy_family, ''), '__legacy_missing_strategy_family__'), targets.strategy_family) AS strategy_family,"
        in query
    )
    assert (
        "ifNull(nullIf(nullIf(pred.cohort_key, ''), '__legacy_missing_cohort_key__'), targets.cohort_key) AS cohort_key,"
        in query
    )
    assert (
        "argMax(ifNull(nullIf(nullIf(pred.parent_cohort_key, ''), '__legacy_missing_parent_cohort_key__'), concat(ifNull(nullIf(nullIf(pred.strategy_family, ''), '__legacy_missing_strategy_family__'), targets.strategy_family), '|__legacy_missing_material_state_signature__')), pred.prediction_as_of_ts) AS parent_cohort_key,"
        in query
    )
    assert (
        "argMax(ifNull(nullIf(pred.engine_version, ''), 'ml_v3_unknown_engine'), pred.prediction_as_of_ts) AS engine_version,"
        in query
    )
    assert (
        "argMax(ifNull(pred.fallback_depth, toUInt8(0)), pred.prediction_as_of_ts) AS fallback_depth,"
        in query
    )
    assert (
        "argMax(ifNull(pred.incumbent_flag, toUInt8(0)), pred.prediction_as_of_ts) AS incumbent_flag,"
        in query
    )
    assert "GROUP BY pred.route, strategy_family, cohort_key" in query


def test_evaluate_run_sql_uses_grouped_or_aggregated_fields_only(monkeypatch) -> None:
    queries: list[str] = []

    def capture_query(_client, query: str):
        queries.append(query)
        return []

    monkeypatch.setattr(v3_eval, "_query_rows", capture_query)

    payload = v3_eval.evaluate_run(object(), league="Mirage", run_id="run-valid-sql")

    assert payload["status"] == "no_rows"
    query = queries[0]
    assert "ifNull(pred.fallback_depth, toUInt8(0)) AS fallback_depth" not in query
    assert "ifNull(pred.incumbent_flag, toUInt8(0)) AS incumbent_flag" not in query
    assert (
        "argMax(ifNull(pred.fallback_depth, toUInt8(0)), pred.prediction_as_of_ts)"
        in query
    )
    assert (
        "argMax(ifNull(pred.incumbent_flag, toUInt8(0)), pred.prediction_as_of_ts)"
        in query
    )


def test_evaluate_run_treats_legacy_sentinel_contract_values_as_missing(
    monkeypatch,
) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []

    monkeypatch.setattr(
        v3_eval,
        "_query_rows",
        lambda *_args, **_kwargs: [
            {
                "route": "sparse_retrieval",
                "strategy_family": "__legacy_missing_strategy_family__",
                "cohort_key": "__legacy_missing_cohort_key__",
                "sample_count": 42,
                "fair_value_mdape": 0.2,
                "fair_value_wape": 0.25,
                "fast_sale_24h_hit_rate": 0.7,
                "fast_sale_24h_mdape": 0.16,
                "sale_probability_calibration_error": 0.08,
                "confidence_calibration_error": 0.1,
            }
        ],
    )
    monkeypatch.setattr(
        v3_eval,
        "_insert_json_rows",
        lambda _client, table, rows: inserted.append((table, rows)),
    )

    v3_eval.evaluate_run(object(), league="Mirage", run_id="run-sentinel")

    cohort_rows = next(
        rows for table, rows in inserted if table == v3_eval.COHORT_EVAL_TABLE
    )
    assert cohort_rows[0]["strategy_family"] == "sparse_retrieval"
    assert (
        cohort_rows[0]["cohort_key"]
        == "sparse_retrieval|__legacy_missing_material_state_signature__"
    )


def test_weighted_average_skips_null_metric_rows() -> None:
    rows = [
        {"sample_count": 100, "metric": None},
        {"sample_count": 300, "metric": 0.2},
    ]

    assert v3_eval._weighted_average(rows, "metric") == pytest.approx(0.2)


def test_weighted_average_returns_none_when_metric_missing_for_all_rows() -> None:
    rows = [
        {"sample_count": 100, "metric": None},
        {"sample_count": 300, "metric": None},
    ]

    assert v3_eval._weighted_average(rows, "metric") is None


def test_evaluate_run_fails_gate_when_mdape_metrics_missing(monkeypatch) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []

    monkeypatch.setattr(
        v3_eval,
        "_query_rows",
        lambda *_args, **_kwargs: [
            {
                "route": "sparse_retrieval",
                "strategy_family": "sparse_retrieval",
                "cohort_key": "sparse_retrieval|default|v1|rare|0|0|0",
                "sample_count": 200,
                "fair_value_mdape": None,
                "fair_value_wape": 0.25,
                "fast_sale_24h_hit_rate": 0.7,
                "fast_sale_24h_mdape": 0.14,
                "sale_probability_calibration_error": 0.08,
                "confidence_calibration_error": 0.1,
            }
        ],
    )
    monkeypatch.setattr(
        v3_eval,
        "_insert_json_rows",
        lambda _client, table, rows: inserted.append((table, rows)),
    )

    payload = v3_eval.evaluate_run(object(), league="Mirage", run_id="run-null-mdape")

    summary = payload["summary"]
    assert summary["gate_passed"] == 0
    assert summary["global_fair_value_mdape"] is None
    assert summary["worst_slice_mdape"] is None
    assert "global_mdape" in str(summary["gate_reason"])
    assert "worst_slice" in str(summary["gate_reason"])


def test_evaluate_run_fail_safe_when_window_evidence_is_unavailable(
    monkeypatch,
) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []

    monkeypatch.setattr(
        v3_eval,
        "_query_rows",
        lambda *_args, **_kwargs: [
            {
                "route": "sparse_retrieval",
                "strategy_family": "sparse_retrieval",
                "cohort_key": "sparse_retrieval|default|v1|rare|0|0|0",
                "sample_count": 700,
                "fair_value_mdape": 0.2,
                "fair_value_wape": 0.25,
                "fast_sale_24h_hit_rate": 0.7,
                "fast_sale_24h_mdape": 0.14,
                "sale_probability_calibration_error": 0.08,
                "confidence_calibration_error": 0.1,
            }
        ],
    )
    monkeypatch.setattr(
        v3_eval,
        "_insert_json_rows",
        lambda _client, table, rows: inserted.append((table, rows)),
    )

    payload = v3_eval.evaluate_run(object(), league="Mirage", run_id="run-no-window")

    assert payload["summary"]["gate_passed"] == 0
    assert "consecutive_windows_required" in str(payload["summary"]["gate_reason"])
