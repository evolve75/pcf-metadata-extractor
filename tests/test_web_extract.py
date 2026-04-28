"""Web extract endpoint form validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pcf_inventory_extractor.web import create_app


def test_extract_requires_cf_credentials() -> None:
    client = TestClient(create_app())
    r = client.post(
        "/extract",
        data={"org_name": "my-org", "cf_api_url": "https://api.test", "cf_username": "u"},
    )
    assert r.status_code == 422


def test_extract_success_content_disposition_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "pcfusage_testorg_20260101120000.csv"

    def fake_run(cfg):  # type: ignore[no-untyped-def]
        cfg.output_path.write_text("h1,h2\n1,2\n", encoding="utf-8")

    monkeypatch.setattr("pcf_inventory_extractor.web.run_extraction", fake_run)
    client = TestClient(create_app())
    r = client.post(
        "/extract",
        data={
            "org_name": "testorg",
            "cf_api_url": "https://api.test",
            "cf_username": "u",
            "cf_password": "p",
            "output_path": str(out),
        },
    )
    assert r.status_code == 200
    cd = r.headers.get("content-disposition") or ""
    assert "attachment" in cd.lower()
    assert out.name in cd
