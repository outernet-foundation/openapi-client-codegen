from typing import Any

from openapi_clientgen import downgrade_openapi_3_1_to_3_0


def test_bumps_version():
    assert downgrade_openapi_3_1_to_3_0({"openapi": "3.1.0"})["openapi"] == "3.0.3"


def test_nullable_type_array_becomes_type_plus_nullable():
    node = downgrade_openapi_3_1_to_3_0({"type": ["null", "string"]})

    assert node["type"] == "string"
    assert node["nullable"] is True


def test_multiple_non_null_types_become_anyof():
    node: dict[str, Any] = downgrade_openapi_3_1_to_3_0({"type": ["string", "integer", "null"]})

    assert "type" not in node
    assert node["nullable"] is True
    assert {"type": "string"} in node["anyOf"]
    assert {"type": "integer"} in node["anyOf"]


def test_anyof_with_single_null_member_inlines_and_sets_nullable():
    node = downgrade_openapi_3_1_to_3_0({"anyOf": [{"type": "string"}, {"type": "null"}]})

    assert "anyOf" not in node
    assert node["type"] == "string"
    assert node["nullable"] is True


def test_array_without_items_gets_empty_items():
    assert downgrade_openapi_3_1_to_3_0({"type": "array"})["items"] == {}


def test_const_becomes_single_value_enum():
    node = downgrade_openapi_3_1_to_3_0({"const": "fixed"})

    assert "const" not in node
    assert node["enum"] == ["fixed"]


def test_numeric_exclusive_minimum_becomes_bool_plus_minimum():
    node = downgrade_openapi_3_1_to_3_0({"exclusiveMinimum": 5})

    assert node["minimum"] == 5
    assert node["exclusiveMinimum"] is True


def test_binary_content_encoding_becomes_string_format_binary():
    node = downgrade_openapi_3_1_to_3_0({"contentEncoding": "binary", "contentMediaType": "application/octet-stream"})

    assert node["type"] == "string"
    assert node["format"] == "binary"
    assert "contentEncoding" not in node
    assert "contentMediaType" not in node


def test_recurses_into_nested_schemas():
    schema: dict[str, Any] = downgrade_openapi_3_1_to_3_0({
        "components": {"schemas": {"Thing": {"properties": {"name": {"type": ["null", "string"]}}}}}
    })

    name_schema = schema["components"]["schemas"]["Thing"]["properties"]["name"]
    assert name_schema["type"] == "string"
    assert name_schema["nullable"] is True
