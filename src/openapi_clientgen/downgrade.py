# Vibe code: Gemini 3
# Convert an OpenAPI 3.1.0 schema to a 3.0.3-compatible one in place. openapi-generator
# only accepts 3.0.x, while Litestar emits 3.1.0. Handles nullable type-arrays, oneOf/anyOf
# null members, const, exclusive bounds, examples->example, and binary contentEncoding.

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | JsonDict | JsonList
type JsonDict = dict[str, JsonValue]
type JsonList = list[JsonValue]


def downgrade_openapi_3_1_to_3_0(schema: JsonDict) -> JsonDict:
    if schema.get("openapi") == "3.1.0":
        schema["openapi"] = "3.0.3"

    _process_node(schema)

    return schema


def _process_node(node: JsonValue) -> None:
    if isinstance(node, dict):
        _convert_dict_node(node)
        for value in node.values():
            _process_node(value)
    elif isinstance(node, list):
        for item in node:
            _process_node(item)


def _convert_dict_node(node: JsonDict) -> None:
    # `type: ["null", "string"]` -> `type: "string", nullable: true`
    type_value = node.get("type")
    if isinstance(type_value, list):
        types: list[str] = [t for t in type_value if isinstance(t, str)]
        has_null = "null" in types
        non_null_types = [t for t in types if t != "null"]

        if len(non_null_types) == 1:
            node["type"] = non_null_types[0]
            if has_null:
                node["nullable"] = True
        elif len(non_null_types) > 1:
            any_of_items: JsonList = []
            for t in non_null_types:
                item: JsonDict = {"type": t}
                # Array types require items in 3.0.3
                if t == "array":
                    item["items"] = {}
                any_of_items.append(item)
            del node["type"]
            node["anyOf"] = any_of_items
            if has_null:
                node["nullable"] = True
        elif has_null and len(non_null_types) == 0:
            # Only null type - use object as fallback
            node["type"] = "object"
            node["nullable"] = True

    # Ensure array types have items (required in 3.0.3)
    if node.get("type") == "array" and "items" not in node:
        node["items"] = {}

    # Handle oneOf/anyOf with {"type": "null"}
    for key in ["oneOf", "anyOf"]:
        key_value = node.get(key)
        if isinstance(key_value, list):
            items = key_value
            null_items: list[JsonDict] = [
                item for item in items if isinstance(item, dict) and item.get("type") == "null"
            ]
            non_null_items: list[JsonDict] = [
                item for item in items if isinstance(item, dict) and item.get("type") != "null"
            ]

            if null_items:
                node["nullable"] = True

                if len(non_null_items) == 0:
                    # Only had null - remove oneOf/anyOf entirely, set as nullable object
                    del node[key]
                    if "type" not in node:
                        node["type"] = "object"
                elif len(non_null_items) == 1:
                    # Single non-null item - inline it and remove oneOf/anyOf
                    del node[key]
                    single_item = non_null_items[0]
                    for k, v in single_item.items():
                        if k not in node:  # Don't overwrite nullable we just set
                            node[k] = v
                else:
                    # Multiple non-null items - keep oneOf/anyOf without null
                    node[key] = list(non_null_items)

    # Convert `examples` (3.1.0) to `example` (3.0.3), but only in schema context (no "value" key)
    examples_value = node.get("examples")
    if isinstance(examples_value, list) and len(examples_value) > 0:
        first_example = examples_value[0]
        if not isinstance(first_example, dict) or "value" not in first_example:
            node["example"] = first_example
            del node["examples"]

    # const (3.1.0) -> enum with a single value (3.0.3)
    if "const" in node:
        node["enum"] = [node["const"]]
        del node["const"]

    # In 3.1.0 exclusiveMinimum/Maximum are numbers; in 3.0.3 they are booleans paired with minimum/maximum
    exclusive_min = node.get("exclusiveMinimum")
    if isinstance(exclusive_min, (int, float)):
        node["minimum"] = exclusive_min
        node["exclusiveMinimum"] = True

    exclusive_max = node.get("exclusiveMaximum")
    if isinstance(exclusive_max, (int, float)):
        node["maximum"] = exclusive_max
        node["exclusiveMaximum"] = True

    # `contentEncoding: "binary"` (3.1) is equivalent to `{type: string, format: binary}` (3.0.3).
    # The containing response's media type already carries the `contentMediaType`, so that field is
    # just dropped.
    if node.get("contentEncoding") == "binary":
        if "format" not in node:
            node["format"] = "binary"
        if "type" not in node:
            node["type"] = "string"

    # Remove 3.1.0-only properties that aren't supported in 3.0.3
    unsupported_keys = ["contentMediaType", "contentEncoding", "$comment"]
    for key in unsupported_keys:
        if key in node:
            del node[key]
