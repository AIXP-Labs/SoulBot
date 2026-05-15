#!/usr/bin/env python3
"""json_schema_validator.py — JSON Schema strict validation for Engine cache files.

Non-invasive audit & validation library.

Dual-use:
  - Library: from json_schema_validator import validate_cache_file
  - CLI:     python json_schema_validator.py --file=<path> --schema=<_index|node_cache|conversation_context>

stdlib only — no external dependencies. Implements a subset of JSON Schema
Draft 2020-12 sufficient for SoulBot's cache file structures:
  - type (str, list of allowed types)
  - required (list of required keys)
  - enum
  - properties + additionalProperties
  - pattern (regex)
  - minimum / maximum
  - minLength / maxLength
  - items (homogeneous array element type)
  - oneOf (limited support)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCHEMA_DIR = Path(__file__).parent / "schemas"
_SCHEMA_FILES = {
    "_index": "_index.schema.json",
    "node_cache": "node_cache.schema.json",
    "conversation_context": "conversation_context.schema.json",
}

# Type name -> Python type tuple
_TYPE_MAP = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


class SchemaValidator:
    """Minimal JSON Schema Draft 2020-12 validator (subset for SoulBot cache)."""

    def __init__(self, schema: dict):
        self.schema = schema

    def validate(self, data: Any) -> list[str]:
        """Return list of error messages. Empty list = valid."""
        errors: list[str] = []
        self._check(data, self.schema, path="$", errors=errors)
        return errors

    # ----- internal -----

    def _check(self, data: Any, schema: Any, path: str, errors: list[str]) -> None:
        if not isinstance(schema, dict):
            return  # malformed schema, ignore

        # oneOf — try each, succeed if exactly one passes
        if "oneOf" in schema:
            sub_errs = []
            passes = 0
            for sub_schema in schema["oneOf"]:
                local: list[str] = []
                self._check(data, sub_schema, path, local)
                if not local:
                    passes += 1
                else:
                    sub_errs.append(local)
            if passes != 1:
                errors.append(
                    f"{path}: oneOf expected exactly 1 match, got {passes} "
                    f"(branch errors: {sub_errs})"
                )
            return

        # type
        if "type" in schema:
            allowed = schema["type"]
            if isinstance(allowed, str):
                allowed = [allowed]
            if not self._type_match(data, allowed):
                errors.append(
                    f"{path}: type mismatch, expected {allowed}, got {type(data).__name__}"
                )
                return  # other checks pointless once type wrong

        # enum
        if "enum" in schema:
            if data not in schema["enum"]:
                errors.append(
                    f"{path}: enum violation, value {data!r} not in {schema['enum']}"
                )

        # string-specific
        if isinstance(data, str):
            if "pattern" in schema:
                if not re.search(schema["pattern"], data):
                    errors.append(
                        f"{path}: pattern mismatch, value {data!r} does not match {schema['pattern']!r}"
                    )
            if "minLength" in schema and len(data) < schema["minLength"]:
                errors.append(f"{path}: minLength={schema['minLength']}, got {len(data)}")
            if "maxLength" in schema and len(data) > schema["maxLength"]:
                errors.append(f"{path}: maxLength={schema['maxLength']}, got {len(data)}")

        # number-specific
        if isinstance(data, (int, float)) and not isinstance(data, bool):
            if "minimum" in schema and data < schema["minimum"]:
                errors.append(f"{path}: minimum={schema['minimum']}, got {data}")
            if "maximum" in schema and data > schema["maximum"]:
                errors.append(f"{path}: maximum={schema['maximum']}, got {data}")

        # object-specific
        if isinstance(data, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in data:
                    errors.append(f"{path}: missing required key '{key}'")

            properties = schema.get("properties", {})
            additional_ok = schema.get("additionalProperties", True)
            additional_schema = (
                additional_ok if isinstance(additional_ok, dict) else None
            )

            for key, value in data.items():
                if key in properties:
                    self._check(value, properties[key], f"{path}.{key}", errors)
                elif additional_schema is not None:
                    self._check(value, additional_schema, f"{path}.{key}", errors)
                elif additional_ok is False:
                    errors.append(f"{path}: unexpected key '{key}' (additionalProperties=false)")

        # array-specific
        if isinstance(data, list):
            items_schema = schema.get("items")
            if items_schema is not None:
                for i, item in enumerate(data):
                    self._check(item, items_schema, f"{path}[{i}]", errors)
            if "minItems" in schema and len(data) < schema["minItems"]:
                errors.append(f"{path}: minItems={schema['minItems']}, got {len(data)}")
            if "maxItems" in schema and len(data) > schema["maxItems"]:
                errors.append(f"{path}: maxItems={schema['maxItems']}, got {len(data)}")

    @staticmethod
    def _type_match(value: Any, allowed: list[str]) -> bool:
        for type_name in allowed:
            if type_name == "boolean":
                if isinstance(value, bool):
                    return True
                continue
            if type_name == "integer":
                # bool is subclass of int — exclude
                if isinstance(value, int) and not isinstance(value, bool):
                    return True
                continue
            expected = _TYPE_MAP.get(type_name)
            if expected and isinstance(value, expected):
                return True
        return False


def _load_schema(schema_type: str) -> dict:
    """Load a built-in schema by short name."""
    if schema_type not in _SCHEMA_FILES:
        raise ValueError(
            f"Unknown schema type {schema_type!r}. Available: {list(_SCHEMA_FILES.keys())}"
        )
    schema_path = _SCHEMA_DIR / _SCHEMA_FILES[schema_type]
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def validate_cache_file(file_path: Path | str, schema_type: str) -> dict:
    """Validate a cache file against its schema.

    Args:
        file_path: Path to the JSON file to validate.
        schema_type: One of '_index', 'node_cache', 'conversation_context'.

    Returns:
        {
          "valid": bool,
          "file": str,
          "schema": str,
          "errors": [str, ...],          # schema violation messages
          "raw_parseable": bool,          # whether json.load() succeeded at all
          "parse_error": str | None,      # JSONDecodeError message if any
        }
    """
    file_path = Path(file_path)
    result: dict = {
        "valid": False,
        "file": str(file_path),
        "schema": schema_type,
        "errors": [],
        "raw_parseable": False,
        "parse_error": None,
    }

    # 1. Raw JSON parsing
    try:
        with open(file_path, encoding="utf-8-sig") as f:
            data = json.load(f)
        result["raw_parseable"] = True
    except json.JSONDecodeError as e:
        result["parse_error"] = f"{e.msg} (line {e.lineno} col {e.colno})"
        result["errors"].append(f"INVALID_JSON: {result['parse_error']}")
        return result
    except OSError as e:
        result["parse_error"] = f"OSError: {e}"
        result["errors"].append(f"IO_ERROR: {e}")
        return result

    # 2. Schema validation
    try:
        schema = _load_schema(schema_type)
    except (ValueError, FileNotFoundError) as e:
        result["errors"].append(f"SCHEMA_LOAD_ERROR: {e}")
        return result

    validator = SchemaValidator(schema)
    errors = validator.validate(data)
    result["errors"] = errors
    result["valid"] = not errors
    return result


def validate_data(data: Any, schema_type: str) -> list[str]:
    """Validate an in-memory Python dict against a schema. Returns error list."""
    schema = _load_schema(schema_type)
    return SchemaValidator(schema).validate(data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SoulBot cache file against JSON Schema.")
    parser.add_argument("--file", required=True, help="Path to JSON file.")
    parser.add_argument(
        "--schema",
        required=True,
        choices=list(_SCHEMA_FILES.keys()),
        help="Schema short name.",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print result code, no detail.")
    parser.add_argument("--json", action="store_true", help="Output result as JSON.")
    args = parser.parse_args()

    result = validate_cache_file(Path(args.file), args.schema)
    if args.quiet:
        pass
    elif args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        marker = "OK" if result["valid"] else "FAIL"
        print(f"[{marker}] {result['file']}  (schema={result['schema']})")
        if not result["raw_parseable"]:
            print(f"  parse_error: {result['parse_error']}")
        for err in result["errors"]:
            print(f"  - {err}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
