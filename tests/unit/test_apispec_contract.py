from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml


def _load_spec() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(Path("apispec.yml").read_text(encoding="utf-8")))


def _response_schema_ref(
    spec: dict[str, Any], path: str, status_code: str = "200", method: str = "get"
) -> str:
    paths = cast(dict[str, Any], spec["paths"])
    path_item = cast(dict[str, Any], paths[path])
    operation = cast(dict[str, Any], path_item[method])
    responses = cast(dict[str, Any], operation["responses"])
    response = cast(dict[str, Any], responses[status_code])
    content = cast(dict[str, Any], response["content"])
    json_content = cast(dict[str, Any], content["application/json"])
    schema = cast(dict[str, Any], json_content["schema"])
    return cast(str, schema["$ref"])


def _response_description(
    spec: dict[str, Any], path: str, status_code: str = "200", method: str = "get"
) -> str:
    paths = cast(dict[str, Any], spec["paths"])
    path_item = cast(dict[str, Any], paths[path])
    operation = cast(dict[str, Any], path_item[method])
    responses = cast(dict[str, Any], operation["responses"])
    response = cast(dict[str, Any], responses[status_code])
    return cast(str, response["description"])


def test_apispec_includes_canonical_stash_lifecycle_routes() -> None:
    text = Path("apispec.yml").read_text(encoding="utf-8")
    spec = _load_spec()
    paths = cast(dict[str, Any], spec["paths"])

    assert "/api/v1/stash/scan/result" in paths
    assert "/api/v1/stash/scan/status" in paths
    assert "/api/v1/stash/scan/valuations/start" in paths
    assert "/api/v1/stash/scan/valuations/status" in paths
    assert "/api/v1/stash/scan/valuations/result" in paths
    assert "StashTabsResponse" in text
    assert "StashScanValuationsResponse" in text
    assert "StashScanStatusResponse" in text
    assert "priceBand" in text
    assert "priceEvaluation" in text
    assert "priceDeltaChaos" in text

    tabs_route = paths["/api/v1/stash/tabs"]["get"]
    assert tabs_route["deprecated"] is True
    assert tabs_route["summary"] == "Get stash scan result (legacy alias)"

    valuations_legacy_route = paths["/api/v1/stash/scan/valuations"]["post"]
    assert valuations_legacy_route["deprecated"] is True
    assert valuations_legacy_route["summary"] == "Get stash valuation result (legacy alias)"

    scan_result_ref = _response_schema_ref(spec, "/api/v1/stash/scan/result")
    assert scan_result_ref == "#/components/schemas/StashTabsResponse"

    assert _response_description(spec, "/api/v1/stash/scan/result") == "Published stash tabs/items payload"
    assert _response_description(spec, "/api/v1/stash/scan/start", status_code="202", method="post") == "Scan started"
    assert _response_description(spec, "/api/v1/stash/scan/status") == "Scan status payload"
    assert _response_description(spec, "/api/v1/stash/scan/valuations/result") == "Valuation payload"

    for route in [
        "/api/v1/stash/scan/result",
        "/api/v1/stash/scan/start",
        "/api/v1/stash/scan/status",
        "/api/v1/stash/scan/valuations/start",
        "/api/v1/stash/scan/valuations/status",
        "/api/v1/stash/scan/valuations/result",
    ]:
        path_item = cast(dict[str, Any], paths[route])
        parameters = cast(
            list[dict[str, Any]],
            path_item["get"]["parameters"] if "get" in path_item else path_item["post"]["parameters"],
        )
        assert {"$ref": "#/components/parameters/LeagueQuery"} in parameters
        assert {"$ref": "#/components/parameters/Realm"} in parameters

    scan_status_responses = cast(
        dict[str, Any], paths["/api/v1/stash/scan/status"]["get"]["responses"]
    )
    assert "503" in scan_status_responses

    valuations_result_ref = _response_schema_ref(
        spec, "/api/v1/stash/scan/valuations/result"
    )
    assert valuations_result_ref == "#/components/schemas/StashScanValuationsResponse"

    status_route_ref = _response_schema_ref(
        spec, "/api/v1/stash/scan/valuations/status"
    )
    assert status_route_ref == "#/components/schemas/StashScanStatusResponse"
    assert (
        _response_description(spec, "/api/v1/stash/scan/valuations/status")
        == "Current scan status"
    )

    start_route_ref = _response_schema_ref(
        spec,
        "/api/v1/stash/scan/valuations/start",
        status_code="202",
        method="post",
    )
    assert start_route_ref == "#/components/schemas/StashScanStatusResponse"
    assert (
        _response_description(
            spec,
            "/api/v1/stash/scan/valuations/start",
            status_code="202",
            method="post",
        )
        == "Valuation refresh started"
    )

    stash_status_responses = cast(
        dict[str, Any], paths["/api/v1/stash/status"]["get"]["responses"]
    )
    assert "503" in stash_status_responses

    legacy_route = cast(dict[str, Any], paths["/api/v1/stash/scan/valuations"]["post"])
    assert legacy_route["deprecated"] is True

    history_route = cast(
        dict[str, Any], paths["/api/v1/stash/items/{fingerprint}/history"]["get"]
    )
    history_limit = next(
        param for param in history_route["parameters"] if param.get("name") == "limit"
    )
    assert "50" in history_limit["description"]
    assert "bounded" in history_limit["description"]


def test_apispec_describes_published_stash_result_fields() -> None:
    spec = _load_spec()
    stash_tabs_schema = cast(
        dict[str, Any], spec["components"]["schemas"]["StashTabsResponse"]
    )

    assert "properties" in stash_tabs_schema
    properties = cast(dict[str, Any], stash_tabs_schema["properties"])
    assert {"scanId", "publishedAt", "isStale", "scanStatus", "stashTabs", "tabsMeta", "numTabs"}.issubset(properties)


def test_apispec_describes_valuation_refresh_lifecycle_metadata() -> None:
    spec = _load_spec()
    status_schema = cast(
        dict[str, Any], spec["components"]["schemas"]["StashScanStatusResponse"]
    )

    assert "properties" in status_schema
    properties = cast(dict[str, Any], status_schema["properties"])
    assert "scanKind" in properties
    assert "sourceScanId" in properties


def test_apispec_describes_item_history_price_quality_fields() -> None:
    spec = _load_spec()
    history_schema = cast(
        dict[str, Any], spec["components"]["schemas"]["StashItemHistoryResponse"]
    )

    assert "properties" in history_schema
    properties = cast(dict[str, Any], history_schema["properties"])
    assert "fingerprint" in properties
    assert "item" in properties
    assert "history" in properties
    history_items = properties["history"]["items"]["properties"]
    assert "priceBand" in history_items
    assert "priceEvaluation" in history_items
    assert "priceBandVersion" in history_items
