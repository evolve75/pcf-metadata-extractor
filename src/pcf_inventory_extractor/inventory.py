"""PCF v3 org inventory run (orchestrates org_extract + app + process)."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from pcf_inventory_extractor import csv_out, org_extract
from pcf_inventory_extractor.cf_client import CfApiClient
from pcf_inventory_extractor.constants import CONFIG_CSV_TIMESTAMP_FORMAT, CONFIG_OUTPUT_PREFIX
from pcf_inventory_extractor.helpers import log_debug


def default_output_name(org: str) -> str:
    ts = datetime.now().strftime(CONFIG_CSV_TIMESTAMP_FORMAT)
    return f"{CONFIG_OUTPUT_PREFIX}_{org}_{ts}.csv"


@dataclass
class ExtractConfig:
    org_name: str
    output_path: Path
    debug: bool = False


def validate_cf_environment() -> None:
    try:
        subprocess.run(
            ["cf", "version"],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as e:
        print("cf CLI not found in PATH", file=sys.stderr)
        raise SystemExit(1) from e
    except subprocess.CalledProcessError as e:
        print("cf version failed", file=sys.stderr)
        raise SystemExit(1) from e
    r = subprocess.run(
        ["cf", "target"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("Not logged in to Cloud Foundry. Run 'cf login' first.", file=sys.stderr)
        raise SystemExit(1)


class InventoryExtractor:
    def __init__(self, client: CfApiClient, cfg: ExtractConfig) -> None:
        self.client = client
        self.cfg = cfg
        self.org_name = cfg.org_name
        self.org_guid = ""
        self.org_sg = ""
        self.global_sg = ""
        self.debug = cfg.debug
        self.warning_count = 0
        self._out: TextIO | None = None

    def _fd(self) -> TextIO:
        if self._out is None:
            raise RuntimeError("output file not open")
        return self._out

    def _debug(self, msg: str) -> None:
        log_debug(msg, self.debug)

    def _validate(self, j: str, context: str) -> bool:
        if (not j) or (j.strip() == "{}"):
            self._debug(f"empty API response {context}")
            self.warning_count += 1
            return False
        import json
        try:
            json.loads(j)
        except json.JSONDecodeError:
            self._debug(f"invalid JSON {context}")
            self.warning_count += 1
            return False
        return True

    def run(self) -> None:
        validate_cf_environment()
        self.client.connect()
        try:
            self._out = open(
                self.cfg.output_path, "w", encoding="utf-8", newline=""
            )
            try:
                csv_out.write_header(self._out)
                self.org_guid = org_extract.extract_org_guid(self)
                self.org_sg = org_extract.org_security_groups(
                    self, self.org_guid
                )
                self.global_sg = org_extract.global_security_groups(self)
                org_extract.extract_spaces(self)
            finally:
                if self._out:
                    self._out.close()
                    self._out = None
            print(
                f"Report generated: {self.cfg.output_path}",
                file=sys.stderr,
            )
            if self.warning_count:
                print(
                    f"Data quality: {self.warning_count} warning(s) — "
                    "some data may be incomplete",
                    file=sys.stderr,
                )
            else:
                print("Data quality: no warnings.", file=sys.stderr)
        finally:
            self.client.close()
