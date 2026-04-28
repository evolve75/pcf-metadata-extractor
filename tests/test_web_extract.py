"""Web extract endpoint form validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pcf_inventory_extractor.extraction.pipeline import sanitize_filename_component
from pcf_inventory_extractor.web import create_app


def test_sanitize_filename_component_removes_path_separators() -> None:
    """Test that path traversal sequences are removed from filenames."""
    assert sanitize_filename_component("../../../tmp/evil") == "_.._.._tmp_evil"
    assert sanitize_filename_component("..\\..\\tmp\\evil") == "_.._tmp_evil"
    assert sanitize_filename_component("normal-org-name") == "normal-org-name"
    assert sanitize_filename_component("org/name") == "org_name"
    assert sanitize_filename_component(".hidden") == "hidden"
    assert sanitize_filename_component("a:b*c?d") == "a_b_c_d"
    assert sanitize_filename_component("") == "unknown"


def test_output_path_rejects_path_traversal() -> None:
    """Test that web endpoint rejects path traversal in output_path."""
    client = TestClient(create_app())
    r = client.post(
        "/extract",
        data={
            "org_name": "testorg",
            "cf_api_url": "https://api.test",
            "cf_username": "u",
            "cf_password": "p",
            "output_path": "../../evil.csv",
        },
    )
    assert r.status_code == 400
    assert "Invalid output filename" in r.json()["detail"]


def test_output_path_rejects_absolute_paths() -> None:
    """Test that web endpoint rejects absolute paths in output_path."""
    client = TestClient(create_app())
    r = client.post(
        "/extract",
        data={
            "org_name": "testorg",
            "cf_api_url": "https://api.test",
            "cf_username": "u",
            "cf_password": "p",
            "output_path": "/tmp/evil.csv",
        },
    )
    assert r.status_code == 400
    assert "Invalid output filename" in r.json()["detail"]


def test_ssl_verify_checkbox_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that SSL verification is disabled when checkbox is checked."""
    captured_cfg = None

    def fake_run(cfg):  # type: ignore[no-untyped-def]
        nonlocal captured_cfg
        captured_cfg = cfg
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
            "output_path": "test.csv",
            "disable_ssl_verify": "on",
        },
    )
    assert r.status_code == 200
    assert captured_cfg is not None
    assert captured_cfg.https_verify is False


def test_ssl_verify_default_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that SSL verification is enabled by default when checkbox is not checked."""
    captured_cfg = None

    def fake_run(cfg):  # type: ignore[no-untyped-def]
        nonlocal captured_cfg
        captured_cfg = cfg
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
            "output_path": "test.csv",
        },
    )
    assert r.status_code == 200
    assert captured_cfg is not None
    assert captured_cfg.https_verify is True


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
    filename = "pcfusage_testorg_20260101120000.csv"

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
            "output_path": filename,
        },
    )
    assert r.status_code == 200
    cd = r.headers.get("content-disposition") or ""
    assert "attachment" in cd.lower()
    assert filename in cd
