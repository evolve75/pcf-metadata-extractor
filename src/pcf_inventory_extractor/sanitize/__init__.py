"""Environment variable and JSON redaction (ported from extract-pcf-inventory.sh)."""

from __future__ import annotations

import json
import re
from typing import Any

from pcf_inventory_extractor.constants import (
    CONFIG_REDACTION_PLACEHOLDER,
    CONFIG_SENSITIVE_PATTERNS,
)

_SENSITIVE_RE = re.compile(
    "|".join(re.escape(p) for p in CONFIG_SENSITIVE_PATTERNS),
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_RE.search(key.upper()))


def json_recursive_sanitize(data: Any) -> Any:
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            if is_sensitive_key(str(k)):
                out[k] = CONFIG_REDACTION_PLACEHOLDER
            else:
                out[k] = json_recursive_sanitize(v)
        return out
    if isinstance(data, list):
        return [json_recursive_sanitize(x) for x in data]
    return data


def sanitize_env_string(key: str, value: str) -> str:
    if is_sensitive_key(key):
        return CONFIG_REDACTION_PLACEHOLDER
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value
    return json.dumps(json_recursive_sanitize(parsed), separators=(",", ":"))

def env_value_to_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def sanitize_env_vars_from_api(env_vars_json: str, validate_fn) -> str:
    """Build semicolon-separated key=value from /v3/apps/.../env body."""
    if not validate_fn(env_vars_json, "Environment variables"):
        return ""
    d = json.loads(env_vars_json)
    env_object = d.get("environment_variables")
    if not env_object or not isinstance(env_object, dict):
        return ""
    if not env_object:
        return ""
    parts: list[str] = []
    for k, v in env_object.items():
        s = env_value_to_str(v)
        parts.append(f"{k}={sanitize_env_string(str(k), s)}")
    return ";".join(parts)
