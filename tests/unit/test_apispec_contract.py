from __future__ import annotations

from pathlib import Path


def test_apispec_includes_canonical_stash_lifecycle_routes() -> None:
    text = Path("apispec.yml").read_text(encoding="utf-8")

    assert "/api/v1/stash/scan/result:" in text
    assert "/api/v1/stash/scan/valuations/start:" in text
    assert "/api/v1/stash/scan/valuations/status:" in text
    assert "/api/v1/stash/scan/valuations/result:" in text
    assert "StashTabsResponse" in text
    assert "StashScanValuationsResponse" in text

    tabs_block = text.split("  /api/v1/stash/tabs:")[1].split(
        "  /api/v1/stash/scan/result:"
    )[0]
    assert "deprecated: true" in tabs_block

    scan_result_block = text.split("  /api/v1/stash/scan/result:")[1].split(
        "  /api/v1/stash/status:"
    )[0]
    assert "LeagueQuery" not in scan_result_block
    assert "StashTabIndex" not in scan_result_block

    valuations_result_block = text.split("  /api/v1/stash/scan/valuations/result:")[
        1
    ].split("  /api/v1/auth/login:")[0]
    assert "LeagueQuery" not in valuations_result_block
    assert "StashScanValuationScanId" not in valuations_result_block

    legacy_block = text.split("  /api/v1/stash/scan/valuations:")[1].split(
        "  /api/v1/stash/scan/valuations/start:"
    )[0]
    assert "deprecated: true" in legacy_block
