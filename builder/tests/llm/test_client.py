import json

from specbuilder.llm.client import _strict_schema


def test_strict_schema_drops_discriminator_but_keeps_one_of():
    schema = {
        "type": "object",
        "properties": {
            "visual": {
                "oneOf": [{"$ref": "#/$defs/A"}, {"$ref": "#/$defs/B"}],
                "discriminator": {"propertyName": "type"},
            }
        },
    }

    strict = json.dumps(_strict_schema(schema))

    assert "discriminator" not in strict
    assert "oneOf" in strict
