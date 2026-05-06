"""Failure-mode catalog for the agent runtime.

Public exports:

- :class:`FailureMode` — the typed mode constants
- :func:`classify` — pure mapping ``(exception_class, span_attrs) → FailureMode | None``
- :data:`FAILURE_MODES` — the canonical ordered tuple of all five modes
- :func:`describe` — one-line external-engineering-language description
- The five mode-name constants (``TOOL_CALL_FAILURE``, etc.)
"""

from src.fail.catalog import (
    CATALOGUED_UNHANDLED,
    CYCLE_DETECTION,
    FAILURE_MODES,
    FailureMode,
    RETRY_EXHAUSTION,
    SCHEMA_MISMATCH,
    TOOL_CALL_FAILURE,
    classify,
    describe,
    is_canonical,
)

__all__ = [
    "CATALOGUED_UNHANDLED",
    "CYCLE_DETECTION",
    "FAILURE_MODES",
    "FailureMode",
    "RETRY_EXHAUSTION",
    "SCHEMA_MISMATCH",
    "TOOL_CALL_FAILURE",
    "classify",
    "describe",
    "is_canonical",
]
