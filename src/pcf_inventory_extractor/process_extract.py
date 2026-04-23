"""Process rows and stats (ported from extract-pcf-inventory.sh)."""

from __future__ import annotations

import json
import sys

from pcf_inventory_extractor import csv_out
from pcf_inventory_extractor.constants import CONFIG_API_MAX_RETRIES_OPTIONAL
from pcf_inventory_extractor.helpers import aggregate_security_groups
from pcf_inventory_extractor.pagination import fetch_all_paged
from pcf_inventory_extractor.types import ExtractorLike


def _process_stats(
    ex: ExtractorLike, process_guid: str, app_name: str, process_type: str
) -> tuple[str, str]:
    sj = ex.client.fetch_with_retry(
        f"/v3/processes/{process_guid}/stats", CONFIG_API_MAX_RETRIES_OPTIONAL
    )
    if sj.startswith("__ERROR") or not ex._validate(
        sj, f"Process stats for {app_name}:{process_type}"
    ):
        ex._debug(f"Stats unavailable for {app_name}:{process_type}")
        return "", ""
    try:
        data = json.loads(sj)
    except json.JSONDecodeError:
        return "", ""
    resources = data.get("resources") or []
    if not resources:
        return "", ""
    inst0 = resources[0] or {}
    usage = (inst0.get("usage") or {}) if isinstance(inst0, dict) else {}
    mem_b = int(usage.get("mem") or 0)
    disk_b = int(usage.get("disk") or 0)
    mem_mb = str((mem_b + 1048575) // 1048576) if mem_b > 0 else ""
    disk_mb = str((disk_b + 1048575) // 1048576) if disk_b > 0 else ""
    return mem_mb, disk_mb


def extract_processes(
    ex: ExtractorLike,
    app_guid: str,
    app_name: str,
    app_state: str,
    buildpacks: str,
    buildpack_details: str,
    runtime_version: str,
    routes: str,
    domains: str,
    service_instances: str,
    service_bindings: str,
    volume_services: str,
    volume_size: str,
    env_vars: str,
    space_name: str,
    space_security_groups: str,
    org_security_groups: str,
    global_security_groups: str,
) -> None:
    proc_json = fetch_all_paged(
        ex.client,
        f"/v3/processes?app_guids={app_guid}",
        f"Processes for app {app_name!r}",
        critical=True,
    )
    pc = (proc_json.get("pagination") or {}).get("total_results", 0)
    if not pc:
        print(f"      No processes for app {app_name!r}", file=sys.stderr)
        return
    org_name = ex.org_name
    for res in proc_json.get("resources") or []:
        if not isinstance(res, dict):
            continue
        proc_guid = str(res.get("guid", "") or "")
        proc_type = str(res.get("type", "") or "")
        instances = int(res.get("instances") or 0)
        mem = int(res.get("memory_in_mb") or 0)
        disk = int(res.get("disk_in_mb") or 0)
        mem_u, disk_u = _process_stats(ex, proc_guid, app_name, proc_type)
        total_disk = ""
        if disk_u not in ("", None):
            try:
                total_disk = str(int(disk_u) * instances)
            except (TypeError, ValueError):
                total_disk = ""
        all_sg = aggregate_security_groups(
            space_security_groups, org_security_groups, global_security_groups
        )
        csv_out.write_row(
            ex._fd(),
            org_name,
            space_name,
            app_name,
            proc_type,
            instances,
            mem,
            disk,
            mem_u,
            disk_u,
            total_disk,
            app_state,
            buildpacks,
            buildpack_details,
            runtime_version,
            routes,
            domains,
            service_instances,
            service_bindings,
            volume_services,
            volume_size,
            env_vars,
            all_sg,
        )
