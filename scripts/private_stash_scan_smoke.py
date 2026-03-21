from __future__ import annotations

import argparse
import json
import os

from poe_trade.api.auth_session import resolve_account_name
from poe_trade.config import settings as config_settings
from poe_trade.ingestion.poe_client import PoeClient
from poe_trade.ingestion.rate_limit import RateLimitPolicy

_PRIVATE_STASH_ITEMS_URL = "https://www.pathofexile.com/character-window/get-stash-items"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test the private stash endpoint without printing secrets"
    )
    parser.add_argument("--league", required=True)
    parser.add_argument("--realm", default="pc")
    parser.add_argument("--account-name")
    args = parser.parse_args()

    poe_session_id = os.environ.get("POESESSID", "").strip()
    if not poe_session_id:
        raise SystemExit("POESESSID environment variable is required")

    settings = config_settings.get_settings()
    account_name = args.account_name or resolve_account_name(
        settings, poe_session_id=poe_session_id
    )
    policy = RateLimitPolicy(
        settings.rate_limit_max_retries,
        settings.rate_limit_backoff_base,
        settings.rate_limit_backoff_max,
        settings.rate_limit_jitter,
    )
    client = PoeClient(
        settings.poe_api_base_url,
        policy,
        settings.poe_user_agent,
        settings.poe_request_timeout,
    )
    payload = client.request(
        "GET",
        _PRIVATE_STASH_ITEMS_URL,
        params={
            "accountName": account_name,
            "realm": args.realm,
            "league": args.league,
            "tabs": "1",
            "tabIndex": "0",
        },
        headers={"Cookie": f"POESESSID={poe_session_id}"},
    )

    raw_tabs = payload.get("tabs") if isinstance(payload, dict) else []
    tabs = raw_tabs if isinstance(raw_tabs, list) else []
    ordered_tabs = [
        {
            "id": str(tab.get("id") or ""),
            "index": int(tab.get("i") or 0),
            "name": str(tab.get("n") or tab.get("name") or ""),
            "type": str(tab.get("type") or "normal"),
        }
        for tab in tabs
        if isinstance(tab, dict)
    ]
    print(
        json.dumps(
            {
                "accountName": account_name,
                "league": args.league,
                "realm": args.realm,
                "tabCount": len(ordered_tabs),
                "tabs": ordered_tabs,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
