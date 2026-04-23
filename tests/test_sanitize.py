import json

from pcf_inventory_extractor import sanitize


def test_is_sensitive() -> None:
    assert sanitize.is_sensitive_key("DB_PASSWORD")
    assert not sanitize.is_sensitive_key("PORT")


def test_sanitize_json_recursive() -> None:
    d = json.loads('{"a":1,"DB_PASSWORD":"x"}')
    o = sanitize.json_recursive_sanitize(d)
    assert o["a"] == 1
    assert o["DB_PASSWORD"] == "<REDACTED>"
