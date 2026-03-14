from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Sequence

from poe_trade.config import settings as config_settings
from poe_trade.db import ClickHouseClient
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
    league = args.league or (
        cfg.api_league_allowlist[0] if cfg.api_league_allowlist else ""
    )
    interval = args.interval_seconds or float(cfg.scan_minutes) * 60.0
    client = ClickHouseClient.from_env(cfg.clickhouse_url)

    while True:
        run_id = scanner.run_scan_once(
            client, league=league, dry_run=bool(args.dry_run)
        )
        _ = client.execute(
            "INSERT INTO poe_trade.poe_ingest_status "
            "(queue_key, feed_kind, contract_version, league, realm, source, last_cursor, next_change_id, last_ingest_at, request_rate, error_count, stalled_since, last_error, status) VALUES "
            f"('scanner:worker','scanner',1,'{league}','pc','scanner_worker','{run_id}','{run_id}',now64(3),1.0,0,NULL,'','running')"
        )
        logging.getLogger(__name__).info("scanner cycle completed run_id=%s", run_id)
        if args.once:
            return 0
        time.sleep(max(interval, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
