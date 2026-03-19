"""ML data pipeline service - FX snapshots and dataset rebuild."""

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


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_previous_rebuild_window_id(status_file: Path, *, league: str) -> str:
    if not status_file.exists():
        return ""
    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    if str(payload.get("league") or "") != league:
        return ""
    rebuild_window = payload.get("rebuild_window")
    if not isinstance(rebuild_window, dict):
        return ""
    return str(rebuild_window.get("window_id") or "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=SERVICE_NAME,
        description="Orchestrate ML data pipeline: FX snapshots and dataset rebuild",
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
        default="artifacts/ml/mirage_v1",
        help="Model directory (default: artifacts/ml/mirage_v1)",
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
            previous_rebuild_window_id = _load_previous_rebuild_window_id(
                status_file,
                league=league,
            )

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

            # Step 2: Build FX rates
            LOGGER.info("Step 2: Build FX rates")
            fx_result = ml_workflows.build_fx(
                ck_client,
                league=league,
                output_table=args.fx_table,
                snapshot_table=args.snapshot_table,
            )
            fx_rows = fx_result.get("rows_written", 0)
            LOGGER.info("FX built: %d rows", fx_rows)

            # Step 3: Normalize prices
            LOGGER.info("Step 3: Normalize prices")
            labels_result = ml_workflows.normalize_prices(
                ck_client,
                league=league,
                output_table=args.labels_table,
                fx_table=args.fx_table,
            )
            labels_rows = labels_result.get("rows_written", 0)
            LOGGER.info("Normalization complete: %d rows", labels_rows)

            rebuild_window = ml_workflows.dataset_rebuild_window(
                ck_client,
                league=league,
                labels_table=args.labels_table,
            )
            if not isinstance(rebuild_window, dict):
                rebuild_window = {}
            current_rebuild_window_id = str(rebuild_window.get("window_id") or "")
            rebuild_skipped = bool(
                previous_rebuild_window_id
                and current_rebuild_window_id
                and previous_rebuild_window_id == current_rebuild_window_id
            )
            rebuild_skip_reason = ""

            if rebuild_skipped:
                rebuild_skip_reason = "unchanged_snapshot_window"
                LOGGER.info(
                    "Step 4-6: Skipping listing events/dataset/comps rebuild "
                    "reason=%s window_id=%s",
                    rebuild_skip_reason,
                    current_rebuild_window_id,
                )
                events_rows = 0
                dataset_rows = 0
                comps_rows = 0
            else:
                if previous_rebuild_window_id and current_rebuild_window_id:
                    LOGGER.info(
                        "Snapshot window changed; rebuilding downstream tables "
                        "previous_window_id=%s current_window_id=%s",
                        previous_rebuild_window_id,
                        current_rebuild_window_id,
                    )
                else:
                    LOGGER.info(
                        "Snapshot window baseline unavailable; rebuilding downstream tables"
                    )

                # Step 4: Build listing events and labels
                LOGGER.info("Step 4: Build listing events and labels")
                events_result = ml_workflows.build_listing_events_and_labels(
                    ck_client,
                    league=league,
                )
                events_rows = events_result.get(
                    "rows_written",
                    events_result.get("listing_rows", 0),
                )
                LOGGER.info("Events built: %d rows", events_rows)

                # Step 5: Build dataset
                LOGGER.info("Step 5: Build dataset")
                as_of_ts = datetime.now(UTC).isoformat()
                dataset_result = ml_workflows.build_dataset(
                    ck_client,
                    league=league,
                    as_of_ts=as_of_ts,
                    output_table=args.dataset_table,
                )
                dataset_rows = dataset_result.get("rows_written", 0)
                LOGGER.info("Dataset built: %d rows", dataset_rows)

                # Step 6: Build comps (optional)
                LOGGER.info("Step 6: Build comps")
                comps_result = ml_workflows.build_comps(
                    ck_client,
                    league=league,
                    dataset_table=args.dataset_table,
                    output_table=args.comps_table,
                )
                comps_rows = comps_result.get("rows_written", 0)
                LOGGER.info("Comps built: %d rows", comps_rows)

            LOGGER.info("Step 7: Refresh serving profile aggregates")
            serving_profile_result = ml_workflows.build_serving_profile(
                ck_client,
                league=league,
                dataset_table=args.dataset_table,
                snapshot_window_id=current_rebuild_window_id,
            )
            serving_profile_rows = serving_profile_result.get("rows_written", 0)
            serving_profile_as_of_ts = serving_profile_result.get(
                "profile_as_of_ts", ""
            )
            LOGGER.info("Serving profile refreshed: %d rows", serving_profile_rows)

            # Write status
            elapsed = time.time() - start_time
            status = {
                "timestamp": datetime.now(UTC).isoformat(),
                "league": league,
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
