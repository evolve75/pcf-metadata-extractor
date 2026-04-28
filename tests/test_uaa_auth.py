"""Tests for UAA password grant and API URL normalization."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from pcf_inventory_extractor.client.http import CfApiClient
from pcf_inventory_extractor.client.uaa_auth import (
    CfProgrammaticAuthError,
    discover_token_endpoint_with_client,
    fetch_access_token,
    normalize_api_base,
    normalize_oauth_token_url,
)
from pcf_inventory_extractor.extraction.pipeline import (
    ExtractConfig,
    _programmatic_login_complete,
    _programmatic_login_partial,
    _programmatic_login_requested,
)


def test_connect_with_token() -> None:
    c = CfApiClient(timeout=5.0)
    c.connect_with_token("https://api.example.com", "access-token-value")
    assert c.api_base == "https://api.example.com"
    c.close()


def test_normalize_api_base_adds_https() -> None:
    assert normalize_api_base("api.example.com") == "https://api.example.com"


def test_normalize_api_base_strips_trailing_slash() -> None:
    assert normalize_api_base("https://api.example.com/") == "https://api.example.com"


def test_normalize_api_base_empty_raises() -> None:
    with pytest.raises(CfProgrammaticAuthError, match="empty"):
        normalize_api_base("")


def test_normalize_oauth_token_url_appends_path() -> None:
    assert normalize_oauth_token_url("https://uaa.example.com") == "https://uaa.example.com/oauth/token"


def test_normalize_oauth_token_url_idempotent() -> None:
    u = "https://uaa.example.com/oauth/token"
    assert normalize_oauth_token_url(u) == u


def test_discover_token_endpoint_from_v2_info() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/info":
            return httpx.Response(
                200,
                json={"token_endpoint": "https://login.test"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, follow_redirects=True) as client:
        te = discover_token_endpoint_with_client("https://api.test", client)
    assert te == "https://login.test/oauth/token"


def test_discover_token_endpoint_links_uaa_href() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/info":
            return httpx.Response(
                200,
                json={"links": {"uaa": {"href": "https://login.test/uaa"}}},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, follow_redirects=True) as client:
        te = discover_token_endpoint_with_client("https://api.test", client)
    assert te == "https://login.test/uaa/oauth/token"


def test_discover_token_endpoint_fallback_to_info_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/info":
            return httpx.Response(404)
        if request.url.path == "/info":
            return httpx.Response(
                200, json={"token_endpoint": "https://login.test/oauth/token"}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, follow_redirects=True) as client:
        te = discover_token_endpoint_with_client("https://api.test", client)
    assert te == "https://login.test/oauth/token"


def test_fetch_access_token_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/info":
            return httpx.Response(
                200, json={"token_endpoint": "https://login.test/oauth/token"}
            )
        if request.url.path == "/oauth/token" and request.method == "POST":
            return httpx.Response(200, json={"access_token": "tok-abc", "token_type": "bearer"})
        return httpx.Response(404, text=str(request.url))

    transport = httpx.MockTransport(handler)
    tok = fetch_access_token(
        "https://api.test", "user1", "secret1", timeout=30.0, transport=transport
    )
    assert tok == "tok-abc"


def test_fetch_access_token_invalid_password() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/info":
            return httpx.Response(
                200, json={"token_endpoint": "https://login.test/oauth/token"}
            )
        if request.url.path == "/oauth/token":
            return httpx.Response(
                401,
                json={"error": "invalid_grant", "error_description": "Bad credentials"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with pytest.raises(CfProgrammaticAuthError, match="invalid username or password"):
        fetch_access_token("https://api.test", "u", "wrong", timeout=30.0, transport=transport)


def test_extract_config_programmatic_flags() -> None:
    cli = ExtractConfig(
        org_name="o",
        output_path=Path("/tmp/x.csv"),
    )
    assert not _programmatic_login_requested(cli)
    assert not _programmatic_login_complete(cli)
    assert not _programmatic_login_partial(cli)

    partial = ExtractConfig(
        org_name="o",
        output_path=Path("/tmp/x.csv"),
        cf_api_url="https://api.test",
    )
    assert _programmatic_login_requested(partial)
    assert not _programmatic_login_complete(partial)
    assert _programmatic_login_partial(partial)

    full = ExtractConfig(
        org_name="o",
        output_path=Path("/tmp/x.csv"),
        cf_api_url="https://api.test",
        cf_username="u",
        cf_password="p",
    )
    assert _programmatic_login_requested(full)
    assert _programmatic_login_complete(full)
    assert not _programmatic_login_partial(full)
