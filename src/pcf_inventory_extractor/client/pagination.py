"""Paginated list fetches (CF v3)."""

from __future__ import annotations

import json
from typing import Any

from pcf_inventory_extractor.client.http import CfApiClient
from pcf_inventory_extractor.constants import (
    CONFIG_API_MAX_RETRIES,
    CONFIG_API_MAX_RETRIES_OPTIONAL,
)


def _next_href(pagination: Any) -> str:
    if not isinstance(pagination, dict):
        return ""
    n = pagination.get("next")
    if isinstance(n, dict):
        return (n.get("href") or "").strip()
    if isinstance(n, str):
        return n.strip()
    return ""


def fetch_all_paged(
    client: CfApiClient,
    initial_path: str,
    description: str,
    *,
    critical: bool = True,
) -> dict[str, Any]:
    """Paginated resources and meta (bash api_fetch_all_pages)."""
    max_r = CONFIG_API_MAX_RETRIES if critical else CONFIG_API_MAX_RETRIES_OPTIONAL
    base = client.api_base
    r = client.fetch_with_retry(initial_path, max_r)
    if r.startswith("__ERROR"):
        if critical:
            raise RuntimeError(
                f"Critical error: {description} failed for {initial_path!r} "
                f"(permanent or exhausted retries)"
            )
        return {
            "resources": [],
            "pagination": {"total_results": 0, "fetched_results": 0, "next": None},
        }
    data = json.loads(r)
    all_resources: list = list(data.get("resources") or [])
    tr = (data.get("pagination") or {}).get("total_results", 0)
    next_url = _next_href(data.get("pagination") or {})
    if next_url and not (next_url.startswith("http://") or next_url.startswith("https://")):
        if next_url.startswith("/"):
            next_url = base + next_url
        else:
            next_url = base + "/" + next_url
    page_num = 1
    while next_url:
        page_num += 1
        r2 = client.fetch_with_retry(next_url, max_r)
        if r2.startswith("__ERROR"):
            if critical:
                break
            break
        d2 = json.loads(r2)
        all_resources.extend(d2.get("resources") or [])
        next_url = _next_href(d2.get("pagination") or {})
        if next_url and not (next_url.startswith("http://") or next_url.startswith("https://")):
            if next_url.startswith("/"):
                next_url = base + next_url
            else:
                next_url = base + "/" + next_url
    fetched = len(all_resources)
    return {
        "pagination": {
            "total_results": tr if isinstance(tr, int) else fetched,
            "total_pages": 1,
            "fetched_results": fetched,
        },
        "resources": all_resources,
    }
