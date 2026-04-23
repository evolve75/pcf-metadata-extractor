"""CSV output helpers (RFC 4180 via stdlib csv)."""

from __future__ import annotations

import csv
import io
from typing import TextIO

from pcf_inventory_extractor.constants import CONFIG_CSV_COLUMNS, CONFIG_CSV_DELIMITER


def write_header(f: TextIO) -> None:
    line = CONFIG_CSV_DELIMITER.join(CONFIG_CSV_COLUMNS)
    f.write(line + "\n")
    f.flush()


def write_row(
    f: TextIO,
    org: str,
    space: str,
    app: str,
    proc_type: str,
    instances: int,
    mem: int,
    disk: int,
    mem_u: int | str,
    disk_u: int | str,
    total_disk_u: int | str,
    state: str,
    buildpacks: str,
    bpd: str,
    runtime: str,
    routes: str,
    domains: str,
    svc_i: str,
    svc_b: str,
    vol_s: str,
    vol_g: str,
    env: str,
    sgs: str,
) -> None:
    out = io.StringIO()
    w = csv.writer(
        out,
        delimiter=CONFIG_CSV_DELIMITER,
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True,
        lineterminator="",
    )
    w.writerow(
        [
            org,
            space,
            app,
            proc_type,
            instances,
            mem,
            disk,
            mem_u,
            disk_u,
            total_disk_u,
            state,
            buildpacks,
            bpd,
            runtime,
            routes,
            domains,
            svc_i,
            svc_b,
            vol_s,
            vol_g,
            env,
            sgs,
        ]
    )
    f.write(out.getvalue() + "\n")
    f.flush()
