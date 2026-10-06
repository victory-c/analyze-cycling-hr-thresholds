#!/usr/bin/env python3
"""Check public Strava MCP OAuth metadata without tokens or account access."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

RESOURCE = "https://mcp.strava.com/mcp"
RESOURCE_METADATA = "https://mcp.strava.com/.well-known/oauth-protected-resource"
ADVERTISED_SERVER = "https://www.strava.com/mcp-issuer"
SERVER_METADATA = (
    "https://www.strava.com/.well-known/oauth-authorization-server/mcp-issuer"
)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public_json(url: str) -> dict:
    """Fetch a bounded document with default TLS validation and no cookies."""
    opener = build_opener(NoRedirects())
    request = Request(url, headers={"Accept": "application/json"})
    with opener.open(request, timeout=15) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("Metadata exceeded the 64 KiB limit")
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError("Metadata is not a JSON object")
    return document


def classify(resource: dict, server: dict) -> dict:
    """Compare exact issuer strings; do not treat same-origin paths as equal."""
    advertised = resource.get("authorization_servers")
    issuer = server.get("issuer")
    base = {
        "resource": resource.get("resource"),
        "advertised_authorization_servers": advertised,
        "discovered_issuer": issuer,
        "authenticated": False,
        "account_eligibility": "not_checked",
        "tools_discovered": False,
    }
    if resource.get("resource") != RESOURCE:
        return {**base, "status": "unexpected_resource"}
    if advertised != [ADVERTISED_SERVER]:
        return {**base, "status": "discovery_changed_reinspect_official_metadata"}
    if not isinstance(issuer, str) or not issuer:
        return {**base, "status": "missing_issuer"}
    if issuer != ADVERTISED_SERVER:
        return {**base, "status": "issuer_mismatch"}
    for key in ("authorization_endpoint", "token_endpoint"):
        endpoint = server.get(key)
        if not isinstance(endpoint, str):
            return {**base, "status": "missing_endpoint", "field": key}
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or parsed.netloc != "www.strava.com":
            return {**base, "status": "endpoint_changed_reinspect", "field": key}
    return {**base, "status": "metadata_consistent_login_not_verified"}


def main() -> int:
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "resource_metadata_url": RESOURCE_METADATA,
        "server_metadata_url": SERVER_METADATA,
    }
    try:
        report.update(classify(fetch_public_json(RESOURCE_METADATA),
                               fetch_public_json(SERVER_METADATA)))
    except HTTPError as exc:
        report.update(status="metadata_http_error", http_status=exc.code)
    except (URLError, TimeoutError, OSError, ValueError):
        # Deliberately omit bodies, headers and exception strings: a local
        # proxy error may contain credentials even though our request has none.
        report.update(status="metadata_fetch_or_parse_error")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "metadata_consistent_login_not_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
