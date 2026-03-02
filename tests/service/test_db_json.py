"""Unit tests for tolerant DB JSON helpers."""

from src.services.db_json import dumps_if_dict, loads_if_str, safe_json_dict


def test_loads_if_str_decodes_json_object():
    assert loads_if_str('{"x": 1}') == {"x": 1}


def test_loads_if_str_keeps_non_string_value():
    value = {"x": 2}
    assert loads_if_str(value) is value


def test_loads_if_str_returns_original_for_invalid_json():
    raw = "{not-json"
    assert loads_if_str(raw) == raw


def test_dumps_if_dict_encodes_dict_and_leaves_other_values():
    assert dumps_if_dict({"x": 1}) == '{"x": 1}'
    assert dumps_if_dict("already-json") == "already-json"


def test_safe_json_dict_accepts_dict_input():
    value = {"location": "start"}
    assert safe_json_dict(value) == value


def test_safe_json_dict_decodes_json_string_dict():
    assert safe_json_dict('{"location": "start"}') == {"location": "start"}


def test_safe_json_dict_returns_empty_for_invalid_or_non_dict_json():
    assert safe_json_dict("not-json") == {}
    assert safe_json_dict('[1, 2, 3]') == {}
    assert safe_json_dict(None) == {}
