from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from poe_trade.config import settings as config_settings
from poe_trade.db import ClickHouseClient
from poe_trade.ml import workflows
from poe_trade.ml.v3 import backfill as v3_backfill
from poe_trade.ml.v3 import eval as v3_eval
from poe_trade.ml.v3 import train as v3_train

SERVICE_NAME = "ml_trainer"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _write_status(payload: dict[str, object]) -> None:
    status_path = Path(".sisyphus/state/qa/ml-trainer-last-run.json")
    status_path.parent.mkdir(parents=True, exist_ok=True)
    _ = status_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_stage(
    *,
    league: str,
    stage: str,
    status: str,
    details: dict[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {
        "league": league,
        "stage": stage,
        "status": status,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    if details:
        payload["details"] = details
    _write_status(payload)


def _query_rows(client: ClickHouseClient, query: str) -> list[dict[str, object]]:
    payload = client.execute(query).strip()
    if not payload:
        return []
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


def _assert_stage_completed(*, stage: str, payload: dict[str, object]) -> None:
    raw_status = payload.get("status")
    status = str(raw_status or "").strip().lower()
    if not status:
        if stage == "train_models":
            trained_count = payload.get("trained_count")
            has_results = isinstance(payload.get("results"), list)
            if has_results:
                return
            try:
                if trained_count is not None and int(str(trained_count)) >= 0:
                    return
            except (TypeError, ValueError):
                pass
        if stage == "evaluate_models":
            run_id = str(payload.get("run_id") or "").strip()
            has_summary = isinstance(payload.get("summary"), dict)
            has_metrics = isinstance(payload.get("metrics"), dict)
            if run_id and (has_summary or has_metrics):
                return
        raise RuntimeError(f"{stage} failed with missing status")
    if status not in {"completed", "success", "succeeded", "ok"}:
        raise RuntimeError(f"{stage} failed with status={status}")


def _refresh_v3_training_examples(
    client: ClickHouseClient, *, league: str
) -> dict[str, object]:
    source_rows = _query_rows(
        client,
        " ".join(
            [
                "SELECT max(observed_at) AS latest_source_at",
                "FROM poe_trade.silver_v3_item_observations",
                f"WHERE league = '{league}'",
                "FORMAT JSONEachRow",
            ]
        ),
    )
    train_rows = _query_rows(
        client,
        " ".join(
            [
                "SELECT max(as_of_ts) AS latest_training_at",
                "FROM poe_trade.ml_v3_listing_episodes",
                f"WHERE league = '{league}'",
                "FORMAT JSONEachRow",
            ]
        ),
    )
    latest_source_at = str(
        (source_rows[0] if source_rows else {}).get("latest_source_at") or ""
    )
    latest_training_at = str(
        (train_rows[0] if train_rows else {}).get("latest_training_at") or ""
    )
    if not latest_source_at:
        return {
            "status": "completed",
            "latest_source_at": None,
            "latest_training_at": latest_training_at or None,
            "replayed_days": [],
        }

    source_day = latest_source_at.split(" ", 1)[0]
    training_day = latest_training_at.split(" ", 1)[0] if latest_training_at else ""
    replayed_days: list[str] = []
    if not training_day or source_day >= training_day:
        start_rows = _query_rows(
            client,
            " ".join(
                [
                    "SELECT min(toDate(observed_at)) AS first_day",
                    "FROM poe_trade.silver_v3_item_observations",
                    f"WHERE league = '{league}'",
                    "FORMAT JSONEachRow",
                ]
            ),
        )
        first_source_day = str(
            (start_rows[0] if start_rows else {}).get("first_day") or ""
        )
        start_day = first_source_day
        if training_day:
            try:
                next_day = datetime.strptime(
                    training_day, "%Y-%m-%d"
                ).date() + timedelta(days=1)
                start_day = next_day.isoformat()
            except ValueError:
                start_day = training_day
        if start_day and start_day <= source_day:
            v3_backfill_result = v3_backfill.backfill_range(
                client,
                league=league,
                start_day=start_day,
                end_day=source_day,
            )
            requested_days = int(v3_backfill_result.get("days_requested") or 0)
            processed_days = int(v3_backfill_result.get("days_processed") or 0)
            if requested_days and processed_days < requested_days:
                raise RuntimeError(
                    "replay backfill incomplete "
                    f"league={league} requested={requested_days} processed={processed_days}"
                )
            replayed_days = [
                str(row.get("day") or "")
                for row in v3_backfill_result.get("results", [])
                if str(row.get("day") or "")
            ]

    return {
        "status": "completed",
        "latest_source_at": latest_source_at,
        "latest_training_at": latest_training_at or None,
        "replayed_days": replayed_days,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=SERVICE_NAME, description="Run autonomous ML trainer service"
    )
    _ = parser.add_argument("--league", default=None)
    _ = parser.add_argument("--model-dir", default="artifacts/ml/mirage_v3")
    _ = parser.add_argument("--once", action="store_true")
    _ = parser.add_argument("--interval-seconds", type=int, default=None)
    args = parser.parse_args(argv)

    _configure_logging()
    cfg = config_settings.get_settings()
    if not cfg.ml_automation_enabled:
        logging.getLogger(__name__).info("%s disabled", SERVICE_NAME)
        return 0
    workflows._ensure_non_legacy_model_dir(str(args.model_dir))
    league = args.league or cfg.ml_automation_league
    interval = args.interval_seconds or cfg.ml_automation_interval_seconds
    client = ClickHouseClient.from_env(cfg.clickhouse_url)
    try:
        workflows.warmup_active_models(client, league=league)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "ml trainer warmup failed for league=%s: %s",
            league,
            exc,
        )
    while True:
        try:
            _write_stage(
                league=league, stage="refresh_training_examples", status="running"
            )
            data_refresh = _refresh_v3_training_examples(client, league=league)
            _assert_stage_completed(
                stage="refresh_training_examples", payload=data_refresh
            )
            _write_stage(
                league=league,
                stage="refresh_training_examples",
                status="completed",
                details={"replayed_days": data_refresh.get("replayed_days")},
            )

            _write_stage(league=league, stage="train_models", status="running")
            v3_result = v3_train.train_all_routes_v3(
                client,
                league=league,
                model_dir=str(args.model_dir),
            )
            _assert_stage_completed(stage="train_models", payload=v3_result)
            _write_stage(
                league=league,
                stage="train_models",
                status="completed",
                details={
                    "run_id": v3_result.get("run_id"),
                    "trained_count": v3_result.get("trained_count"),
                },
            )

            eval_result: dict[str, object] | None = None
            run_id = str(v3_result.get("run_id") or "")
            eval_prediction_rows = int(v3_result.get("eval_prediction_rows") or 0)
            if run_id and eval_prediction_rows > 0:
                _write_stage(
                    league=league,
                    stage="evaluate_models",
                    status="running",
                    details={"run_id": run_id, "rows": eval_prediction_rows},
                )
                eval_result = v3_eval.evaluate_run(
                    client,
                    league=league,
                    run_id=run_id,
                )
                _assert_stage_completed(stage="evaluate_models", payload=eval_result)
                _write_stage(
                    league=league,
                    stage="evaluate_models",
                    status="completed",
                    details={"run_id": run_id},
                )
            result = {
                "status": "completed",
                "stop_reason": "v3_train_cycle",
                "active_model_version": "v3",
                "v3": v3_result,
                "data_refresh": data_refresh,
                "evaluation": eval_result,
            }
            _write_status(
                {
                    "league": league,
                    "stage": "train_cycle",
                    "status": str(result.get("status") or "completed"),
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "result": result,
                }
            )
            logging.getLogger(__name__).info(
                "ml trainer cycle status=%s stop_reason=%s",
                result.get("status"),
                result.get("stop_reason"),
            )
            if args.once:
                return 0
        except Exception as exc:
            _write_stage(
                league=league,
                stage="train_cycle",
                status="failed",
                details={"error": str(exc)},
            )
            logging.getLogger(__name__).exception(
                "ml trainer cycle failed for league=%s: %s",
                league,
                exc,
            )
            if args.once:
                return 1
        time.sleep(max(interval, 1))


if __name__ == "__main__":
    raise SystemExit(main())
