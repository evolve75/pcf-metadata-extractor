"""Run extraction and return the output path."""

from __future__ import annotations

from pathlib import Path

from pcf_inventory_extractor.cf_client import CfApiClient
from pcf_inventory_extractor.inventory import ExtractConfig, InventoryExtractor


def run_extraction(cfg: ExtractConfig) -> Path:
    client = CfApiClient()
    InventoryExtractor(client, cfg).run()
    return Path(cfg.output_path)
