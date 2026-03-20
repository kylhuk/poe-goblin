from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from ..config import settings as config_settings
from ..db import ClickHouseClient
from ..ml import workflows as ml_workflows


LOGGER = logging.getLogger(__name__)
SERVICE_NAME = "poeninja_snapshot"
MIN_REBUILD_INTERVAL_SECONDS = 1800


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=SERVICE_NAME,
        description="Ingest PoeNinja raw snapshot data for incremental derivation",
    )
    parser.add_argument(
        "--league",
        help="League label (default from config)",
    )
    parser.add_argument(
        "--snapshot-table",
        default="poe_trade.raw_poeninja_currency_overview",
        help="Table for raw PoeNinja currency snapshot (default: poe_trade.raw_poeninja_currency_overview)",
    )
    parser.add_argument(
        "--fx-table",
        default="poe_trade.ml_fx_hour_v1",
        help="Table for FX rates (default: poe_trade.ml_fx_hour_v1)",
    )
    parser.add_argument(
        "--labels-table",
        default="poe_trade.ml_price_labels_v1",
        help="Table for price labels (default: poe_trade.ml_price_labels_v1)",
    )
    parser.add_argument(
        "--dataset-table",
        default="poe_trade.ml_price_dataset_v1",
        help="Table for ML dataset (default: poe_trade.ml_price_dataset_v1)",
    )
    parser.add_argument(
        "--comps-table",
        default="poe_trade.ml_comps_v1",
        help="Table for comps (default: poe_trade.ml_comps_v1)",
    )
    parser.add_argument(
        "--model-dir",
        default="artifacts/ml/mirage_v2",
        help="Model directory (default: artifacts/ml/mirage_v2)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        help="Polling interval in seconds (default from config or 900)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one pipeline cycle and exit",
    )
    parser.add_argument(
        "--full-rebuild-backfill",
        action="store_true",
        help=(
            "Run explicit downstream full rebuild work after snapshot ingest "
            "(not used in steady-state mode)"
        ),
    )
    args = parser.parse_args(argv)

    _configure_logging()
    cfg = config_settings.get_settings()

    # Check if enabled
    if not getattr(cfg, "poe_enable_poeninja_snapshot", True):
        LOGGER.info("%s disabled via POE_ENABLE_POENINJA_SNAPSHOT=false", SERVICE_NAME)
        return 0

    # Determine league
    league = (
        args.league
        or getattr(cfg, "poe_poeninja_snapshot_league", None)
        or cfg.ml_automation_league
    )
    if not league:
        LOGGER.error(
            "No league configured. Set POE_POENINJA_SNAPSHOT_LEAGUE or POE_ML_AUTOMATION_LEAGUE"
        )
        return 1

    # Determine interval
    interval = args.interval_seconds or getattr(
        cfg, "poe_ml_dataset_rebuild_interval_seconds", 900
    )
    if not args.once and interval < MIN_REBUILD_INTERVAL_SECONDS:
        LOGGER.warning(
            "%s interval %ss below floor %ss; clamping",
            SERVICE_NAME,
            interval,
            MIN_REBUILD_INTERVAL_SECONDS,
        )
        interval = MIN_REBUILD_INTERVAL_SECONDS

    LOGGER.info(
        "%s starting league=%s once=%s interval=%ss",
        SERVICE_NAME,
        league,
        args.once,
        interval,
    )

    # Initialize ClickHouse client
    ck_client = ClickHouseClient.from_env(cfg.clickhouse_url)

    # Ensure state directory exists
    state_dir = Path(".sisyphus/state")
    state_dir.mkdir(parents=True, exist_ok=True)
    status_file = state_dir / f"{SERVICE_NAME}-last-run.json"

    try:
        while True:
            start_time = time.time()
            LOGGER.info("%s: Starting pipeline cycle", SERVICE_NAME)

            # Step 1: Snapshot PoeNinja currency data
            LOGGER.info("Step 1: Snapshot PoeNinja currency")
            snapshot_result = ml_workflows.snapshot_poeninja(
                ck_client,
                league=league,
                output_table=args.snapshot_table,
                max_iterations=1,
            )
            snapshot_rows = snapshot_result.get("rows_written", 0)
            LOGGER.info("Snapshot complete: %d rows", snapshot_rows)
            fx_rows = 0
            labels_rows = 0
            events_rows = 0
            dataset_rows = 0
            comps_rows = 0
            serving_profile_rows = 0
            serving_profile_as_of_ts = ""
            rebuild_window: dict[str, object] = {}
            previous_rebuild_window_id = ""
            rebuild_skipped = True
            rebuild_skip_reason = "steady_state_snapshot_only"
            pipeline_mode = "steady_state_snapshot_only"
            downstream_rebuild_triggered = False

            if args.full_rebuild_backfill:
                LOGGER.info(
                    "Step 2: Running explicit full rebuild backfill after snapshot ingest"
                )
                backfill_result = ml_workflows.run_full_snapshot_rebuild_backfill(
                    ck_client,
                    league=league,
                    snapshot_table=args.snapshot_table,
                    fx_table=args.fx_table,
                    labels_table=args.labels_table,
                    dataset_table=args.dataset_table,
                    comps_table=args.comps_table,
                )
                fx_rows = int(backfill_result.get("fx_rows") or 0)
                labels_rows = int(backfill_result.get("labels_rows") or 0)
                events_rows = int(backfill_result.get("events_rows") or 0)
                dataset_rows = int(backfill_result.get("dataset_rows") or 0)
                comps_rows = int(backfill_result.get("comps_rows") or 0)
                serving_profile_rows = int(backfill_result.get("serving_profile_rows") or 0)
                serving_profile_as_of_ts = str(
                    backfill_result.get("serving_profile_as_of_ts") or ""
                )
                raw_rebuild_window = backfill_result.get("rebuild_window")
                if isinstance(raw_rebuild_window, dict):
                    rebuild_window = raw_rebuild_window
                rebuild_skipped = False
                rebuild_skip_reason = ""
                pipeline_mode = "explicit_full_rebuild_backfill"
                downstream_rebuild_triggered = True
            else:
                LOGGER.info(
                    "Step 2: Running incremental v2 label repair for FX normalization gaps"
                )
                label_repair_result = ml_workflows.repair_incremental_price_labels_v2(
                    ck_client,
                    league=league,
                )
                labels_rows = int(label_repair_result.get("rows_repaired") or 0)
                LOGGER.info(
                    "Step 2: Running incremental v2 dataset repair for MV propagation gaps"
                )
                repair_result = ml_workflows.repair_incremental_price_dataset_v2(
                    ck_client,
                    league=league,
                )
                dataset_rows = int(repair_result.get("rows_repaired") or 0)

            # Write status
            elapsed = time.time() - start_time
            status = {
                "timestamp": datetime.now(UTC).isoformat(),
                "league": league,
                "snapshot_mode": pipeline_mode,
                "downstream_derivation_owner": "clickhouse_v2",
                "downstream_rebuild_triggered": downstream_rebuild_triggered,
                "snapshot_rows": snapshot_rows,
                "fx_rows": fx_rows,
                "labels_rows": labels_rows,
                "events_rows": events_rows,
                "dataset_rows": dataset_rows,
                "comps_rows": comps_rows,
                "serving_profile_rows": serving_profile_rows,
                "serving_profile_as_of_ts": serving_profile_as_of_ts,
                "rebuild_window": rebuild_window,
                "previous_rebuild_window_id": previous_rebuild_window_id,
                "rebuild_skipped": rebuild_skipped,
                "rebuild_skip_reason": rebuild_skip_reason,
                "elapsed_seconds": round(elapsed, 2),
            }
            with open(status_file, "w") as f:
                json.dump(status, f, indent=2)

            LOGGER.info("%s: Cycle complete in %.2fs", SERVICE_NAME, elapsed)

            if args.once:
                LOGGER.info("%s: --once specified, exiting", SERVICE_NAME)
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        LOGGER.info("%s: Interrupted, shutting down", SERVICE_NAME)
        return 0
    except Exception as e:
        LOGGER.exception("%s: Fatal error", SERVICE_NAME)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
