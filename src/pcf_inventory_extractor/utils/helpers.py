"""Small utilities (ported from bash)."""

from __future__ import annotations

import sys
from typing import TextIO

from pcf_inventory_extractor.constants import CONFIG_CSV_MULTIVALUE_SEP


def util_join_with_separator(sep: str, *items: str) -> str:
    parts: list[str] = []
    for it in items:
        if it:
            parts.append(str(it))
    return sep.join(parts)


def util_append_to_list(
    existing: str, new_item: str, separator: str = CONFIG_CSV_MULTIVALUE_SEP
) -> str:
    if not new_item:
        return existing
    if existing:
        return f"{existing}{separator}{new_item}"
    return new_item


def aggregate_security_groups(
    space_g: str, org_g: str, global_g: str
) -> str:
    return util_join_with_separator(
        CONFIG_CSV_MULTIVALUE_SEP, space_g, org_g, global_g
    )


def log_debug(msg: str, debug: bool, f: TextIO = sys.stderr) -> None:
    if debug:
        f.write(f"DEBUG: {msg}\n")
        f.flush()
