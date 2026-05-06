"""OTel-shaped JSON trace exporter for the agent runtime.

Public exports:

- :class:`OtelJsonExporter` — a callable matching the runtime's
  ``SpanRecorder`` shape; assembles OTLP-JSON-subset spans
- :func:`new_exporter` — convenience factory
- :data:`SERVICE_NAME` / :data:`SCOPE_NAME` — the canonical resource +
  scope identifiers
- :data:`OTLP_SUBSET_SCHEMA` — the subset JSON-schema dict
- :func:`validate_otlp_subset` — round-trip validator the smoke
  surface uses to fail loudly on schema drift
- :data:`SUBSET_VERSION` — stable subset-version string the manifest
  pins
"""

from src.tracing.otel_exporter import (
    SCOPE_NAME,
    SERVICE_NAME,
    OtelJsonExporter,
    new_exporter,
)
from src.tracing.otlp_subset_schema import (
    OTLP_SUBSET_SCHEMA,
    SPAN_ID_PATTERN,
    SUBSET_VERSION,
    TRACE_ID_PATTERN,
    validate_otlp_subset,
)

__all__ = [
    "OTLP_SUBSET_SCHEMA",
    "OtelJsonExporter",
    "SCOPE_NAME",
    "SERVICE_NAME",
    "SPAN_ID_PATTERN",
    "SUBSET_VERSION",
    "TRACE_ID_PATTERN",
    "new_exporter",
    "validate_otlp_subset",
]
