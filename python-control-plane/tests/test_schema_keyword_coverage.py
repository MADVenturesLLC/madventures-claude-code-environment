from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madclaude.errors import PolicyViolation
from madclaude.schemas import (
    META_KEYWORDS,
    SCHEMAS,
    SUPPORTED_KEYWORDS,
    assert_supported_keywords,
    export_schemas,
    iter_schema_keywords,
    validate_instance,
)

SHIPPED_SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


class SchemaKeywordCoverageTests(unittest.TestCase):
    def test_all_used_keywords_supported(self) -> None:
        self.assertTrue(SCHEMAS)
        for name, schema in SCHEMAS.items():
            with self.subTest(schema=name):
                assert_supported_keywords(schema, name)
                for _, keyword in iter_schema_keywords(schema):
                    self.assertIn(keyword, SUPPORTED_KEYWORDS | META_KEYWORDS)

    def test_shipped_schemas_match_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            export_schemas(destination)
            for shipped in sorted(SHIPPED_SCHEMAS.glob("*.schema.json")):
                with self.subTest(schema=shipped.name):
                    exported = destination / shipped.name
                    self.assertTrue(exported.exists(), f"missing export for {shipped.name}")
                    self.assertEqual(
                        shipped.read_bytes(),
                        exported.read_bytes(),
                        f"shipped schema {shipped.name} is not byte-equal to export_schemas output",
                    )

    def test_unsupported_keyword_fails_gate(self) -> None:
        for keyword in ("maxItems", "minLength", "maxLength", "exclusiveMinimum", "format", "title"):
            with self.subTest(keyword=keyword):
                schema = {"type": "array", keyword: 3}
                with self.assertRaises(PolicyViolation):
                    assert_supported_keywords(schema, "hostile")

    def test_walker_catches_nested_unsupported_keyword(self) -> None:
        nested = {
            "type": "object",
            "properties": {
                "outer": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 5},
                }
            },
        }
        with self.assertRaises(PolicyViolation):
            assert_supported_keywords(nested, "nested")

    def test_meta_keywords_are_not_validation(self) -> None:
        self.assertNotIn("$schema", SUPPORTED_KEYWORDS)
        assert_supported_keywords({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"})

    def test_minimum_typing_pins(self) -> None:
        # int below minimum is an error.
        self.assertTrue(validate_instance(1, {"minimum": 2}))
        self.assertFalse(validate_instance(2, {"minimum": 2}))
        # bool subclasses int, so minimum currently applies to booleans too.
        self.assertTrue(validate_instance(True, {"minimum": 2}))
        self.assertTrue(validate_instance(False, {"minimum": 1}))
        # float values are ignored by the int-typed minimum check.
        self.assertFalse(validate_instance(1.5, {"minimum": 2}))
        self.assertFalse(validate_instance(0.1, {"minimum": 2}))

    def test_integer_and_number_exclude_bool(self) -> None:
        self.assertTrue(validate_instance(True, {"type": "integer"}))
        self.assertTrue(validate_instance(True, {"type": "number"}))
        self.assertFalse(validate_instance(1, {"type": "integer"}))
        self.assertFalse(validate_instance(1.5, {"type": "number"}))
        self.assertFalse(validate_instance(True, {"type": "boolean"}))


if __name__ == "__main__":
    unittest.main()
