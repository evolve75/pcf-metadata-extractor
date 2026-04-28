"""Obtain a CF API bearer token via UAA password grant (no cf CLI session)."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from pcf_inventory_extractor.constants import CONFIG_HTTPS_VERIFY


class CfProgrammaticAuthError(Exception):
    """Raised when API URL discovery or UAA password grant fails."""


def normalize_oauth_token_url(token_endpoint: str) -> str:
    """
    Ensure the UAA token URL ends with ``/oauth/token``.

    Some Cloud Controllers return only the UAA host as ``token_endpoint``; POSTing
    that base URL hits Spring endpoints that require CSRF and returns HTTP 403.
    """
    u = (token_endpoint or "").strip().rstrip("/")
    if not u:
        raise CfProgrammaticAuthError("Empty token_endpoint from Cloud Controller info.")
    if u.endswith("/oauth/token"):
        return u
    return u + "/oauth/token"


def normalize_api_base(url: str) -> str:
    s = (url or "").strip()
    if not s:
        raise CfProgrammaticAuthError("CF API URL is empty.")
    if not urlparse(s).scheme:
        s = "https://" + s
    p = urlparse(s)
    if p.scheme not in ("http", "https"):
        raise CfProgrammaticAuthError("CF API URL must use http or https.")
    netloc = p.netloc or ""
    if not netloc:
        raise CfProgrammaticAuthError("CF API URL is missing a host.")
    path = (p.path or "").rstrip("/")
    base = f"{p.scheme}://{netloc}{path}"
    return base.rstrip("/")


def _token_endpoint_from_cc_info(data: dict[str, Any]) -> str:
    te = data.get("token_endpoint")
    if isinstance(te, str) and te.strip():
        return normalize_oauth_token_url(te.strip())
    links = data.get("links")
    if isinstance(links, dict):
        uaa = links.get("uaa")
        if isinstance(uaa, dict):
            href = uaa.get("href")
            if isinstance(href, str) and href.strip():
                return normalize_oauth_token_url(
                    urljoin(href.strip().rstrip("/") + "/", "oauth/token")
                )
    raise CfProgrammaticAuthError(
        "Could not find token_endpoint in Cloud Controller info. "
        "Try the same API URL you use with cf login -a (e.g. https://api.example.com)."
    )


def discover_token_endpoint_with_client(api_base: str, client: httpx.Client) -> str:
    """Resolve UAA token URL from Cloud Controller (unauthenticated)."""
    base = normalize_api_base(api_base)
    paths = ("/v2/info", "/info")
    last_status: int | None = None
    for path in paths:
        url = base + path
        try:
            r = client.get(url)
        except httpx.HTTPError as e:
            raise CfProgrammaticAuthError(f"Could not reach Cloud Controller: {e}") from e
        last_status = r.status_code
        if r.status_code == 404:
            continue
        if r.status_code != 200:
            raise CfProgrammaticAuthError(
                f"Cloud Controller info request failed (HTTP {r.status_code})."
            )
        try:
            data = r.json()
        except json.JSONDecodeError as e:
            raise CfProgrammaticAuthError("Cloud Controller info response was not JSON.") from e
        if not isinstance(data, dict):
            raise CfProgrammaticAuthError("Cloud Controller info response was not an object.")
        try:
            return _token_endpoint_from_cc_info(data)
        except CfProgrammaticAuthError:
            continue
    raise CfProgrammaticAuthError(
        "Could not load /v2/info or /info from the API URL"
        + (f" (last HTTP {last_status})." if last_status is not None else ".")
    )


def discover_token_endpoint(
    api_base: str, timeout: float = 120.0, https_verify: bool = CONFIG_HTTPS_VERIFY
) -> str:
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        verify=https_verify,
    ) as client:
        return discover_token_endpoint_with_client(api_base, client)


def fetch_access_token(
    api_base: str,
    username: str,
    password: str,
    *,
    timeout: float = 120.0,
    transport: httpx.BaseTransport | None = None,
    https_verify: bool = CONFIG_HTTPS_VERIFY,
) -> str:
    """
    Return a bearer access_token for CF v3 API calls.

    Uses the same password grant as the cf CLI (client_id ``cf``).

    ``transport`` is optional (for tests); production callers omit it.
    """
    user = (username or "").strip()
    if not user:
        raise CfProgrammaticAuthError("Username is empty.")
    if password is None or password == "":
        raise CfProgrammaticAuthError("Password is empty.")
    base = normalize_api_base(api_base)
    # RFC 6749: authenticate the cf CLI client via Basic auth (same as ``cf login``).
    # Sending client_id in the form body can trigger UAA/Spring CSRF on some builds.
    basic_cf = base64.b64encode(b"cf:").decode("ascii")
    body = {
        "grant_type": "password",
        "username": user,
        "password": password,
    }
    token_headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {basic_cf}",
    }
    client_kw: dict[str, Any] = {
        "timeout": timeout,
        "follow_redirects": True,
        "verify": https_verify,
    }
    if transport is not None:
        client_kw["transport"] = transport
    with httpx.Client(**client_kw) as client:
        token_url = normalize_oauth_token_url(
            discover_token_endpoint_with_client(base, client)
        )
        try:
            r = client.post(
                token_url,
                data=body,
                headers=token_headers,
            )
        except httpx.HTTPError as e:
            raise CfProgrammaticAuthError(f"Could not reach UAA: {e}") from e
    if r.status_code == 200:
        try:
            data = r.json()
        except json.JSONDecodeError as e:
            raise CfProgrammaticAuthError("UAA token response was not JSON.") from e
        token = data.get("access_token") if isinstance(data, dict) else None
        if isinstance(token, str) and token.strip():
            return token.strip()
        raise CfProgrammaticAuthError("UAA token response did not include access_token.")
    err_detail = ""
    try:
        err = r.json()
        if isinstance(err, dict):
            err_detail = str(err.get("error_description") or err.get("error") or "")
    except json.JSONDecodeError:
        err_detail = (r.text or "")[:200]
    el = err_detail.lower()
    if r.status_code in (401, 400) and (
        "invalid_grant" in el
        or "locked" in el
        or "password" in el
        or "credentials" in el
        or "unauthorized" in el
    ):
        raise CfProgrammaticAuthError("Login failed: invalid username or password.")
    if "unsupported_grant_type" in el or "unauthorized_client" in el:
        raise CfProgrammaticAuthError(
            "This foundation may not allow password login (e.g. SSO-only). "
            "Use cf login on the host and the CLI extractor instead."
        )
    raise CfProgrammaticAuthError(
        f"UAA token request failed (HTTP {r.status_code})"
        + (f": {err_detail}" if err_detail else ".")
    )
