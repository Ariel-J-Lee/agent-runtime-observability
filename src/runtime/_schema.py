"""Tiny in-tree JSON-Schema validator.

Covers the keyword subset the project actually uses:

- ``type`` (object, string, integer, number, boolean, array, null)
- ``required`` (object property presence)
- ``properties`` (per-key schemas)
- ``additionalProperties`` (boolean; when false, extra keys deny)
- ``items`` (array element schema)
- ``enum`` (literal allowlist)
- ``minLength`` / ``maxLength`` (string length bounds)
- ``minimum`` / ``maximum`` (numeric bounds)

This validator serves two callers:

1. ``PolicySpec.from_yaml_path()`` validates the parsed YAML against
   ``policy/v1.schema.json`` so misconfiguration surfaces at startup,
   not on the first denial.
2. ``PolicyChecker.check()`` validates per-tool arguments against the
   tool's input JSON-schema when ``arg_schema_enforcement == "strict"``;
   the ``arg_schema`` deny rule fires on validation failure.

The implementation is intentionally small: a dependency on
``jsonschema`` (or any other validator package) is out of scope for
this slice (per the GO direction's "no jsonschema" lock). If a future
slice needs a richer keyword set (``oneOf``, ``patternProperties``,
``$ref``, etc.), the validator can swap to ``jsonschema`` without
changing the public ``validate(...)`` signature.

Public surface:

- :class:`SchemaError` — typed validation failure carrying a
  JSON-pointer-style ``path`` and a human-readable ``message``
- :func:`validate` — raises :class:`SchemaError` on failure; returns
  ``None`` on success
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SchemaError(Exception):
    """A schema-validation failure.

    Attributes:
        path: JSON-pointer-style path to the offending field, e.g.
            ``"/loop_budget/max_iterations"`` or ``"/url_allowlist/0"``.
            Empty string means the failure is on the root.
        message: Short human-readable explanation, e.g.
            ``"expected integer; got str"``.
    """

    path: str
    message: str

    def __str__(self) -> str:  # pragma: no cover — Exception.__str__
        anchor = self.path or "<root>"
        return f"{anchor}: {self.message}"


# Map JSON-Schema "type" values to Python types. JSON-Schema treats
# booleans as a separate type from integers (Python's bool is a subclass
# of int, so the ordinary isinstance check would be too permissive); the
# validator below handles that explicitly.
_TYPE_TO_PYTHON = {
    "object": (dict,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list, tuple),
    "null": (type(None),),
}


def _join(path: str, segment: str) -> str:
    return f"{path}/{segment}"


def _check_type(value: Any, type_name: str, *, path: str) -> None:
    expected = _TYPE_TO_PYTHON.get(type_name)
    if expected is None:
        raise SchemaError(path=path, message=f"unknown schema type: {type_name!r}")
    if type_name in ("integer", "number") and isinstance(value, bool):
        raise SchemaError(
            path=path,
            message=f"expected {type_name}; got bool",
        )
    if not isinstance(value, expected):
        raise SchemaError(
            path=path,
            message=f"expected {type_name}; got {type(value).__name__}",
        )


def _validate(value: Any, schema: Mapping[str, Any], *, path: str) -> None:
    if "type" in schema:
        _check_type(value, schema["type"], path=path)

    if "enum" in schema:
        allowed = schema["enum"]
        if value not in allowed:
            raise SchemaError(
                path=path,
                message=f"value {value!r} not in enum {list(allowed)!r}",
            )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaError(
                path=path,
                message=f"string length {len(value)} below minLength {schema['minLength']}",
            )
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaError(
                path=path,
                message=f"string length {len(value)} above maxLength {schema['maxLength']}",
            )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(
                path=path,
                message=f"value {value} below minimum {schema['minimum']}",
            )
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(
                path=path,
                message=f"value {value} above maximum {schema['maximum']}",
            )

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        for req in required:
            if req not in value:
                raise SchemaError(
                    path=_join(path, req),
                    message="required property missing",
                )
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    raise SchemaError(
                        path=_join(path, key),
                        message="additional property not allowed",
                    )
        for key, sub_schema in properties.items():
            if key in value:
                _validate(value[key], sub_schema, path=_join(path, key))

    if isinstance(value, (list, tuple)):
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(value):
                _validate(item, items_schema, path=_join(path, str(i)))


def validate(value: Any, schema: Mapping[str, Any]) -> None:
    """Validate ``value`` against ``schema``.

    Args:
        value: The value to validate (any JSON-serializable Python type).
        schema: The schema mapping. Supports the keyword subset
            documented in the module docstring.

    Raises:
        SchemaError: When the value violates the schema. The error's
            ``path`` field gives a JSON-pointer-style locator and
            ``message`` is a one-line explanation.
    """
    _validate(value, schema, path="")
