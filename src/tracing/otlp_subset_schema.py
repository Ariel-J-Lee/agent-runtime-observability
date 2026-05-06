"""OTLP-JSON subset schema for the v1 trace artifact.

This module pins the **subset** of the OTLP/JSON specification the v1
trace exporter writes. The subset target is "what Jaeger 1.52+ and
Grafana Tempo 2.4+ accept on file import" per the runtime proof plan
§3.4. Adding more OTLP fields later (``traceState``, ``flags``,
``events``, ``links``, ``status``, ``droppedAttributesCount``) is
non-breaking for those viewers, so the subset is conservative on
purpose.

The schema is enforced by :func:`validate_otlp_subset`, which calls
into the in-tree validator at :mod:`src.runtime._schema`. No
third-party schema library is added at this slice.

Public surface:

- :data:`OTLP_SUBSET_SCHEMA` — the JSON-schema dict
- :func:`validate_otlp_subset` — raises :class:`SchemaError` on drift
- :data:`SUBSET_VERSION` — a stable version string the manifest can pin

The validator covers the v1 attribute set bound by the proof plan §3.3:

- ``agent.run_id``, ``agent.step_index``
- ``agent.tool_name``
- ``agent.policy.decision``, ``agent.policy.rule_id``, ``policy.version``
- ``agent.retry.attempt``, ``agent.retry.outcome``, ``agent.retry.backoff_ms``
- ``agent.failure_mode``
- ``agent.llm.execution_path``

The OTLP/JSON attribute encoding is ``[{key, value: {<typeKey>: <value>}}]``.
Supported type keys at v1: ``stringValue``, ``intValue``, ``boolValue``,
``doubleValue``. Other type keys (``arrayValue``, ``kvlistValue``,
``bytesValue``) are not used by the v1 trace and not validated.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.runtime._schema import SchemaError, validate

SUBSET_VERSION = "v1.0"

# Hex-string formats per W3C trace-context: traceId is 32 lowercase hex chars,
# spanId is 16 lowercase hex chars. The OTLP/JSON spec serializes both as
# strings (not byte arrays at this transport).
TRACE_ID_PATTERN = "^[0-9a-f]{32}$"
SPAN_ID_PATTERN = "^[0-9a-f]{16}$"
UNIX_NANO_PATTERN = "^[0-9]+$"  # OTLP emits times as numeric strings.

_ATTRIBUTE_VALUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "stringValue": {"type": "string"},
        "intValue": {"type": "string", "pattern": "^-?[0-9]+$"},
        "boolValue": {"type": "boolean"},
        "doubleValue": {"type": "number"},
    },
}

_KEY_VALUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["key", "value"],
    "additionalProperties": False,
    "properties": {
        "key": {"type": "string", "minLength": 1},
        "value": _ATTRIBUTE_VALUE_SCHEMA,
    },
}

_SPAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "traceId",
        "spanId",
        "name",
        "kind",
        "startTimeUnixNano",
        "endTimeUnixNano",
        "attributes",
    ],
    # parentSpanId is optional (omitted on top-level spans). Other
    # fields stay closed so additions surface as schema drift in tests.
    "additionalProperties": False,
    "properties": {
        "traceId": {"type": "string", "pattern": TRACE_ID_PATTERN},
        "spanId": {"type": "string", "pattern": SPAN_ID_PATTERN},
        "parentSpanId": {"type": "string", "pattern": SPAN_ID_PATTERN},
        "name": {"type": "string", "minLength": 1},
        "kind": {"type": "integer", "minimum": 0, "maximum": 5},
        "startTimeUnixNano": {"type": "string", "pattern": UNIX_NANO_PATTERN},
        "endTimeUnixNano": {"type": "string", "pattern": UNIX_NANO_PATTERN},
        "attributes": {"type": "array", "items": _KEY_VALUE_SCHEMA},
    },
}

_SCOPE_SPANS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["scope", "spans"],
    "additionalProperties": False,
    "properties": {
        "scope": {
            "type": "object",
            "required": ["name"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "minLength": 1},
            },
        },
        "spans": {"type": "array", "items": _SPAN_SCHEMA},
    },
}

_RESOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["attributes"],
    "additionalProperties": False,
    "properties": {
        "attributes": {"type": "array", "items": _KEY_VALUE_SCHEMA},
    },
}

_RESOURCE_SPANS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["resource", "scopeSpans"],
    "additionalProperties": False,
    "properties": {
        "resource": _RESOURCE_SCHEMA,
        "scopeSpans": {"type": "array", "items": _SCOPE_SPANS_SCHEMA},
    },
}

OTLP_SUBSET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["resourceSpans"],
    "additionalProperties": False,
    "properties": {
        "resourceSpans": {"type": "array", "items": _RESOURCE_SPANS_SCHEMA},
    },
}


def validate_otlp_subset(doc: Mapping[str, Any]) -> None:
    """Validate ``doc`` against :data:`OTLP_SUBSET_SCHEMA`.

    Raises :class:`src.runtime._schema.SchemaError` on the first
    violation. The error's ``path`` field gives a JSON-pointer-style
    locator (e.g., ``/resourceSpans/0/scopeSpans/0/spans/3/traceId``)
    so the schema-drift test can pinpoint the offending field.
    """
    validate(doc, OTLP_SUBSET_SCHEMA)


__all__ = [
    "OTLP_SUBSET_SCHEMA",
    "SPAN_ID_PATTERN",
    "SUBSET_VERSION",
    "TRACE_ID_PATTERN",
    "UNIX_NANO_PATTERN",
    "SchemaError",
    "validate_otlp_subset",
]
