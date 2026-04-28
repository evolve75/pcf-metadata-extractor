"""CF v3 API client using httpx (replaces `cf curl`)."""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from typing import Any

import httpx

from pcf_inventory_extractor.constants import (
    CONFIG_API_INITIAL_BACKOFF,
    CONFIG_API_MAX_RETRIES,
    CONFIG_API_MAX_RETRIES_OPTIONAL,
    CONFIG_HTTPS_VERIFY,
)

FetchFn = Callable[[str, str, int], str]


def _get_cf_api_base() -> str:
    try:
        out = subprocess.check_output(
            ["cf", "api"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as e:
        raise RuntimeError("cf CLI not found in PATH") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"cf api failed: {e}") from e
    for line in out.splitlines():
        m = re.search(r"https?://[^\s]+", line)
        if m:
            return m.group(0).rstrip("/")
    raise RuntimeError("Could not parse API URL from 'cf api'. Is cf logged in?")


def _get_cf_token() -> str:
    try:
        tok = subprocess.check_output(["cf", "oauth-token"], text=True, stderr=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise RuntimeError("cf CLI not found in PATH") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError("cf oauth-token failed. Run 'cf login' first.") from e
    return tok.strip()


def _request_url(
    full_url: str, headers: dict[str, str], timeout: float, verify: bool = True
) -> tuple[int, str, str]:
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        verify=verify,
    ) as c:
        r = c.get(full_url, headers=headers)
    return r.status_code, r.text, (r.headers.get("content-type") or "")


def classify_error(response: str, error_msg: str, exit_code: int) -> str:
    try:
        import json

        data = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        data = None
    if isinstance(data, dict) and data.get("errors"):
        err = (data.get("errors") or [{}])[0]
        code = str(err.get("code", ""))
        if code in ("10002", "10003"):
            return "auth_error"
        if code in ("10004", "10010"):
            return "not_found"
        if code in ("1000", "10008"):
            return "client_error"
        return "server_error"
    el = (error_msg or "").lower()
    for pat in ("connection refused", "timeout", "network", "dns", "read error"):
        if pat in el:
            return "network_error"
    if "unauthorized" in el or "401" in el or "403" in el:
        return "auth_error"
    if "not found" in el or "404" in el:
        return "not_found"
    for pat in ("500", "502", "503", "bad gateway", "service unavailable"):
        if pat in el:
            return "server_error"
    return "server_error"


def fetch_with_retry(
    api_base: str,
    path_or_url: str,
    headers: dict[str, str],
    max_retries: int = CONFIG_API_MAX_RETRIES,
    timeout: float = 120.0,
    https_verify: bool = CONFIG_HTTPS_VERIFY,
) -> str:
    """path_or_url: either '/v3/...' or full https URL (pagination)."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        url = path_or_url
    else:
        path = path_or_url if path_or_url.startswith("/") else "/" + path_or_url
        url = api_base + path
    attempt = 0
    backoff = float(CONFIG_API_INITIAL_BACKOFF)
    last_err: str = ""
    while attempt <= max_retries:
        try:
            status, body, _ = _request_url(url, headers, timeout, verify=https_verify)
        except httpx.HTTPError as e:
            last_err = str(e)
            err_type = classify_error("", last_err, 1)
            if err_type in ("auth_error", "not_found", "client_error"):
                return "__ERROR_PERMANENT__"
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                attempt += 1
                continue
            return "__ERROR_TRANSIENT__"
        if status in (200, 201) and not _has_api_errors_field(body):
            return body
        err_type = classify_error(body, f"http {status}", status)
        last_err = f"HTTP {status}"
        if err_type in ("auth_error", "not_found", "client_error"):
            return "__ERROR_PERMANENT__"
        if err_type in ("network_error", "server_error") and attempt < max_retries:
            time.sleep(backoff)
            backoff *= 2
        elif attempt >= max_retries:
            return "__ERROR_TRANSIENT__"
        attempt += 1
    return "__ERROR_TRANSIENT__"


def _has_api_errors_field(body: str) -> bool:
    import json

    try:
        d = json.loads(body)
    except json.JSONDecodeError:
        return True
    return isinstance(d, dict) and "errors" in d and bool(d.get("errors"))


class CfApiClient:
    def __init__(self, timeout: float = 120.0) -> None:
        self._timeout = timeout
        self.api_base: str = ""
        self._headers: dict[str, str] = {}
        self._httpx_client: httpx.Client | None = None
        self._https_verify: bool = CONFIG_HTTPS_VERIFY

    def connect(self, https_verify: bool = CONFIG_HTTPS_VERIFY) -> None:
        self._https_verify = https_verify
        self.api_base = _get_cf_api_base()
        token = _get_cf_token()
        self._headers = {"Authorization": f"Bearer {token}"}
        self._httpx_client = httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
            headers=self._headers,
            verify=self._https_verify,
        )

    def connect_with_token(
        self, api_base: str, access_token: str, https_verify: bool = CONFIG_HTTPS_VERIFY
    ) -> None:
        self._https_verify = https_verify
        base = (api_base or "").strip().rstrip("/")
        if not base:
            raise RuntimeError("api_base is empty")
        tok = (access_token or "").strip()
        if not tok:
            raise RuntimeError("access_token is empty")
        self.api_base = base
        self._headers = {"Authorization": f"Bearer {tok}"}
        self._httpx_client = httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
            headers=self._headers,
            verify=self._https_verify,
        )

    def close(self) -> None:
        if self._httpx_client:
            self._httpx_client.close()
            self._httpx_client = None

    def _get(self, path_or_url: str) -> tuple[int, str]:
        assert self._httpx_client is not None
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            path = path_or_url if path_or_url.startswith("/") else "/" + path_or_url
            url = self.api_base + path
        r = self._httpx_client.get(url)
        return r.status_code, r.text

    def fetch_raw(self, path_or_url: str, max_retries: int) -> str:
        """Use internal httpx with same retry behavior as fetch_with_retry."""
        attempt = 0
        backoff = float(CONFIG_API_INITIAL_BACKOFF)
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            path = path_or_url if path_or_url.startswith("/") else "/" + path_or_url
            url = self.api_base + path
        while attempt <= max_retries:
            assert self._httpx_client is not None
            try:
                r = self._httpx_client.get(url)
            except httpx.HTTPError:
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    attempt += 1
                    continue
                return "__ERROR_TRANSIENT__"
            body = r.text
            if r.status_code in (200, 201) and not _has_api_errors_field(body):
                return body
            em = f"http {r.status_code}"
            et = classify_error(body, em, r.status_code)
            if et in ("auth_error", "not_found", "client_error"):
                return "__ERROR_PERMANENT__"
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
            else:
                return "__ERROR_TRANSIENT__"
            attempt += 1
        return "__ERROR_TRANSIENT__"

    def fetch_with_retry(
        self, path_or_url: str, max_retries: int = CONFIG_API_MAX_RETRIES
    ) -> str:
        if self._httpx_client is not None:
            return self.fetch_raw(path_or_url, max_retries)
        return fetch_with_retry(
            self.api_base, path_or_url, self._headers, max_retries, self._timeout
        )


def list_org_names_for_error(client: CfApiClient) -> str:
    """Best-effort list of org names (stderr helper)."""
    import json

    r = client.fetch_with_retry("/v3/organizations?per_page=100")
    if r.startswith("__ERROR"):
        return ""
    try:
        d = json.loads(r)
    except json.JSONDecodeError:
        return ""
    names: list[str] = []
    for res in d.get("resources") or []:
        n = (res or {}).get("name")
        if n:
            names.append(str(n))
    return "\n".join(names)


def fetch_all_pages(
    client: CfApiClient,
    initial_path: str,
    description: str,
    max_retries: int = CONFIG_API_MAX_RETRIES,
) -> dict[str, Any]:

    def fetch_fn(p: str, _d: str, _mr: int) -> str:
        return client.fetch_with_retry(p, max_retries)

    return _fetch_all_pages_impl(fetch_fn, client.api_base, initial_path, description, max_retries)


def fetch_all_pages_optional(
    client: CfApiClient, initial_path: str, description: str
) -> dict[str, Any]:

    def fetch_fn(p: str, _d: str, _mr: int) -> str:
        return client.fetch_with_retry(p, CONFIG_API_MAX_RETRIES_OPTIONAL)

    return _fetch_all_pages_impl(
        fetch_fn, client.api_base, initial_path, description, CONFIG_API_MAX_RETRIES_OPTIONAL
    )


def _fetch_all_pages_impl(
    fetch_function: FetchFn, api_base: str, initial_url: str, description: str, max_retries: int
) -> dict[str, Any]:
    import json

    page = fetch_function(initial_url, description, max_retries)
    if page.startswith("__ERROR"):
        return {"resources": [], "pagination": {"total_results": 0, "fetched_results": 0}}
    d = json.loads(page)
    all_resources: list = list(d.get("resources") or [])
    tr = d.get("pagination", {}).get("total_results", 0)
    next_href = d.get("pagination", {}).get("next")
    if isinstance(next_href, dict):
        next_url = (next_href.get("href") or "").strip()
    else:
        next_url = str(next_href or "").strip()
    if next_url and not (next_url.startswith("http://") or next_url.startswith("https://")):
        if next_url.startswith("/"):
            next_url = api_base + next_url
        else:
            next_url = api_base + "/" + next_url
    page_num = 1
    while next_url:
        page_num += 1
        p2 = fetch_function(next_url, f"{description} (page {page_num})", max_retries)
        if p2.startswith("__ERROR"):
            break
        d2 = json.loads(p2)
        all_resources.extend(d2.get("resources") or [])
        nh2 = d2.get("pagination", {}).get("next")
        if isinstance(nh2, dict):
            next_url = (nh2.get("href") or "").strip()
        else:
            next_url = str(nh2 or "").strip()
        if next_url and not (next_url.startswith("http://") or next_url.startswith("https://")):
            if next_url.startswith("/"):
                next_url = api_base + next_url
            else:
                next_url = api_base + "/" + next_url
    fetched = len(all_resources)
    if isinstance(tr, int) and tr != fetched:
        pass  # same as script debug
    return {
        "pagination": {
            "total_results": tr if isinstance(tr, int) else fetched,
            "total_pages": 1,
            "fetched_results": fetched,
        },
        "resources": all_resources,
    }


# --- add after class if missing: used by global SG pagination with safe semantics ---

def fetch_safe_body(client: CfApiClient, path: str) -> str:
    r = client.fetch_with_retry(path, CONFIG_API_MAX_RETRIES)
    if r.startswith("__ERROR"):
        return "{}"
    return r
