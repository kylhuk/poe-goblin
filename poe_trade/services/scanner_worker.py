from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Sequence
from datetime import datetime, timezone

from poe_trade.config import settings as config_settings
from poe_trade.db import ClickHouseClient, ClickHouseClientError
from poe_trade.ingestion import StatusReporter
from poe_trade.strategy import scanner

SERVICE_NAME = "scanner_worker"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=SERVICE_NAME, description="Run scanner worker service"
    )
    _ = parser.add_argument("--league", default=None)
    _ = parser.add_argument("--once", action="store_true")
    _ = parser.add_argument("--dry-run", action="store_true")
    _ = parser.add_argument("--interval-seconds", type=float, default=None)
    args = parser.parse_args(argv)

    _configure_logging()
    cfg = config_settings.get_settings()
    league: str = args.league or (
        cfg.api_league_allowlist[0] if cfg.api_league_allowlist else ""
    )
    interval_seconds_arg = args.interval_seconds
    interval: float = (
        float(interval_seconds_arg)
        if interval_seconds_arg is not None
        else float(cfg.scan_minutes) * 60.0
    )
    once_mode = bool(args.once)
    dry_run = bool(args.dry_run)
    client = ClickHouseClient.from_env(cfg.clickhouse_url)
    status = StatusReporter(client, SERVICE_NAME)
    logger = logging.getLogger(__name__)

    while True:
        try:
            run_id = scanner.run_scan_once(client, league=league, dry_run=dry_run)
        except ClickHouseClientError as exc:
            if getattr(exc, "retryable", False):
                logger.warning("Transient scanner cycle failure: %s", exc)
                if once_mode:
                    return 1
                time.sleep(max(interval, 1.0))
                continue
            raise

        status.report(
            queue_key="scanner:worker",
            feed_kind="scanner",
            contract_version=1,
            league=league,
            realm="pc",
            cursor=run_id,
            next_change_id=run_id,
            last_ingest_at=datetime.now(timezone.utc),
            request_rate=1.0,
            status="running",
        )
        logger.info("scanner cycle completed run_id=%s", run_id)
        if once_mode:
            return 0
        time.sleep(max(interval, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
