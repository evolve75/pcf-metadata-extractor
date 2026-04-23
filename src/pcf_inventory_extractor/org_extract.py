"""Org and global security groups (ported from extract-pcf-inventory.sh)."""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib.parse import quote

from pcf_inventory_extractor.cf_client import list_org_names_for_error
from pcf_inventory_extractor.constants import CONFIG_API_MAX_RETRIES
from pcf_inventory_extractor.pagination import fetch_all_paged
from pcf_inventory_extractor.types import ExtractorLike


def extract_org_guid(ex: ExtractorLike) -> str:
    path = f"/v3/organizations?names={quote(ex.org_name)}"
    r = ex.client.fetch_with_retry(path, CONFIG_API_MAX_RETRIES)
    if r.startswith("__ERROR"):
        print(f"Organization {ex.org_name!r} not found.", file=sys.stderr)
        names = list_org_names_for_error(ex.client)
        if names:
            print("Available orgs:\n" + names, file=sys.stderr)
        raise SystemExit(1)
    data = json.loads(r)
    res = (data.get("resources") or [])
    g = (res[0].get("guid") if res else "") or ""
    if not g:
        print(f"Organization {ex.org_name!r} not found.", file=sys.stderr)
        raise SystemExit(1)
    print(f"Organization: {ex.org_name} ({g})", file=sys.stderr)
    return str(g)


def org_security_groups(_ex: ExtractorLike, _org_guid: str) -> str:
    return ""


def _fmt_global_line(prefix: str, d: dict[str, Any]) -> str:
    out: list[str] = []
    for res in d.get("resources") or []:
        name = (res or {}).get("name") or ""
        s = f"{prefix}{name}"
        if len(s) > 16:
            out.append(s)
    return ";".join(out)


def global_security_groups(ex: ExtractorLike) -> str:
    dr = fetch_all_paged(
        ex.client,
        "/v3/security_groups?globally_enabled_running=true",
        "Global running security groups",
        critical=False,
    )
    ds = fetch_all_paged(
        ex.client,
        "/v3/security_groups?globally_enabled_staging=true",
        "Global staging security groups",
        critical=False,
    )
    a = _fmt_global_line("global-running:", dr)
    b = _fmt_global_line("global-staging:", ds)
    if a and b:
        return a + ";" + b
    return a or b


def extract_spaces(ex: ExtractorLike) -> None:
    from pcf_inventory_extractor import app_extract

    path = f"/v3/spaces?organization_guids={ex.org_guid}"
    spaces_json = fetch_all_paged(
        ex.client, path, f"Spaces listing for org {ex.org_name!r}", critical=True
    )
    sc = int((spaces_json.get("pagination") or {}).get("total_results", 0) or 0)
    print(f"Found {sc} space(s) in org {ex.org_name!r}", file=sys.stderr)
    if not sc:
        print(f"No spaces found in org {ex.org_name!r}", file=sys.stderr)
        return
    o_sg = org_security_groups(ex, ex.org_guid)
    g_sg = ex.global_sg
    for res in spaces_json.get("resources") or []:
        sg = str((res or {}).get("guid", "") or "")
        sn = str((res or {}).get("name", "") or "")
        print(f"Processing space: {sn} ({sg})", file=sys.stderr)
        app_extract.extract_apps_in_space(
            ex, sg, sn, "", o_sg, g_sg
        )
