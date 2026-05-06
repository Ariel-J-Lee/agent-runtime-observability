"""OpenTelemetry-shaped JSON trace exporter (OTLP JSON subset).

Captures the agent's ``span_recorder`` events and assembles them into
an OTLP-JSON document that conforms to the documented subset
(:mod:`src.tracing.otlp_subset_schema`). The artifact is what the
run-capture slice commits as ``runs/<run-id>/trace.json``; this lane
ships the exporter and the validator, but commits no captured runs.

Design (per the locked GO direction):

- The exporter is a callable matching the
  ``SpanRecorder = Callable[[str, Mapping[str, Any]], None]`` shape so
  it can be passed directly as ``Agent(span_recorder=exporter)``.
- One ``agent_step`` span per ``(run_id, step_index)``. A follow-up
  emission of the same span class for the same step (the agent emits
  the failure-mode follow-up event) merges attributes into the existing
  span rather than creating a new one.
- Child spans (``llm_call``, ``tool_call``, ``policy_check``,
  ``retry_attempt``) are created per-emission and attached to the
  current ``agent_step`` via ``parentSpanId``.
- Trace ID and span IDs are deterministic when ``seed`` is supplied; a
  default ``seed=0`` produces the same byte-identical artifact across
  reruns. ``time_source`` is overridable for tests; default
  ``time.time_ns``.

Public surface:

- :class:`OtelJsonExporter` — the SpanRecorder-callable exporter
- :func:`new_exporter` — convenience factory with the standard service
  resource attributes pre-set
- :data:`SERVICE_NAME` — the canonical service identifier emitted on
  every captured trace's ``resource.attributes`` block

The exporter is **pure stdlib**: ``random``, ``time``, ``json``,
``pathlib``. No ``opentelemetry-api`` / ``opentelemetry-sdk`` runtime
dependency is added, per the locked first-proof composition deviation
set.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Optional

from src.tracing.otlp_subset_schema import (
    SUBSET_VERSION,
    validate_otlp_subset,
)

SERVICE_NAME = "agent-runtime-observability"
SCOPE_NAME = "agent-runtime-observability"

# OTLP SpanKind: 0=UNSPECIFIED, 1=INTERNAL, 2=SERVER, 3=CLIENT, 4=PRODUCER, 5=CONSUMER.
# Every span the runtime emits is INTERNAL (no inter-process tracing at v1).
SPAN_KIND_INTERNAL = 1

# The five span classes the runtime emits + the follow-up failure-mode
# event class. The failure-mode follow-up uses ``agent_step`` so it
# merges into the existing per-step span rather than creating a new one.
_SPAN_CLASSES = ("agent_step", "llm_call", "tool_call", "policy_check", "retry_attempt")


def _to_attribute_value(value: Any) -> dict[str, Any]:
    """Encode a Python scalar as an OTLP/JSON ``AnyValue``.

    Type mapping (matches OTLP/JSON):

    - ``bool`` → ``{"boolValue": <bool>}``
    - ``int`` → ``{"intValue": <stringified int>}`` (OTLP requires
      strings for 64-bit ints to survive JSON's integer-precision limit)
    - ``float`` → ``{"doubleValue": <number>}``
    - ``str`` → ``{"stringValue": <str>}``
    - other → coerced to ``str`` and emitted as ``stringValue`` (the
      conservative choice; per-attribute audit catches surprises)
    """
    # Order matters: bool is a subclass of int, so check it first.
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    return {"stringValue": str(value)}


def _attrs_dict_to_otlp(attrs: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Convert a ``{key: value}`` dict to the OTLP ``[{key, value}]`` list.

    Stable-sorted by key so two reruns with identical attrs emit
    byte-identical attribute arrays.
    """
    return [
        {"key": str(k), "value": _to_attribute_value(v)}
        for k, v in sorted(attrs.items(), key=lambda kv: kv[0])
    ]


def _merge_attribute_lists(
    base: list[dict[str, Any]],
    addition: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge an OTLP attribute list with an addition; ``addition`` overrides.

    Preserves stable sort order and drops duplicate keys (last write
    wins).
    """
    by_key: dict[str, dict[str, Any]] = {item["key"]: item for item in base}
    for item in addition:
        by_key[item["key"]] = item
    return sorted(by_key.values(), key=lambda kv: kv["key"])


class OtelJsonExporter:
    """OTLP-JSON-subset trace exporter.

    Implements ``__call__(span_class, attrs)`` so it satisfies the
    runtime's ``SpanRecorder`` shape. After the agent run completes,
    callers invoke :meth:`to_otlp_dict` for the assembled document or
    :meth:`write` to serialize to disk. :meth:`validate` round-trips
    the document through the subset schema; tests use it to lock the
    contract.

    Args:
        service_name: Resource ``service.name`` attribute. Defaults
            to :data:`SERVICE_NAME`.
        scope_name: ``scope.name`` for the single scopeSpans block.
            Defaults to :data:`SCOPE_NAME`.
        seed: Deterministic-ID seed. ``0`` (default) produces byte-
            identical artifacts across reruns; non-zero values let
            tests assert seed sensitivity.
        time_source: Callable returning current time in nanoseconds.
            Defaults to :func:`time.time_ns`. Tests pass a deterministic
            counter to lock timestamps in the captured document.
    """

    def __init__(
        self,
        *,
        service_name: str = SERVICE_NAME,
        scope_name: str = SCOPE_NAME,
        seed: int = 0,
        time_source: Optional[Callable[[], int]] = None,
    ) -> None:
        self.service_name = service_name
        self.scope_name = scope_name
        self.subset_version = SUBSET_VERSION
        self._rng = random.Random(seed)
        self._time_source = time_source or time.time_ns

        # Trace ID is set on the first event so an exporter that never
        # gets called still emits a valid (empty) OTLP document.
        self._trace_id: Optional[str] = None

        # All assembled spans, in emission order. Children always appear
        # after their parent (the runtime emits agent_step first).
        self._spans: list[dict[str, Any]] = []

        # Per-step lookup so follow-up agent_step emissions merge into
        # the existing span and child spans pick up the right parent.
        # Key: (run_id, step_index) → span dict (the same object held
        # in self._spans).
        self._step_spans: MutableMapping[tuple[str, int], dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # SpanRecorder interface
    # ------------------------------------------------------------------

    def __call__(self, span_class: str, attrs: Mapping[str, Any]) -> None:
        """Record a span event.

        Behavior:

        - First call ever → generate the trace ID.
        - ``agent_step`` for an unseen ``(run_id, step_index)`` →
          create a new span and remember it as the current step span.
        - ``agent_step`` for a known ``(run_id, step_index)`` → merge
          attributes into the existing span (the failure-mode follow-up
          path) and update ``endTimeUnixNano``.
        - Other span classes → create a new span attached to the
          current step span via ``parentSpanId``.
        """
        if self._trace_id is None:
            self._trace_id = self._new_trace_id()

        run_id = str(attrs.get("agent.run_id", ""))
        step_index_raw = attrs.get("agent.step_index", 0)
        try:
            step_index = int(step_index_raw)
        except (TypeError, ValueError):
            step_index = 0

        now = str(self._time_source())

        if span_class == "agent_step":
            key = (run_id, step_index)
            existing = self._step_spans.get(key)
            if existing is not None:
                existing["attributes"] = _merge_attribute_lists(
                    existing["attributes"],
                    _attrs_dict_to_otlp(attrs),
                )
                existing["endTimeUnixNano"] = now
                return
            span = self._make_span(
                name=span_class,
                attrs=attrs,
                start_time=now,
                end_time=now,
                parent_span_id=None,
            )
            self._step_spans[key] = span
            self._spans.append(span)
            return

        # Child span: attach to the current step's agent_step.
        parent = self._step_spans.get((run_id, step_index))
        parent_span_id = parent["spanId"] if parent is not None else None
        span = self._make_span(
            name=span_class,
            attrs=attrs,
            start_time=now,
            end_time=now,
            parent_span_id=parent_span_id,
        )
        self._spans.append(span)

    # ------------------------------------------------------------------
    # Public assembly + validation
    # ------------------------------------------------------------------

    def to_otlp_dict(self) -> dict[str, Any]:
        """Return the assembled OTLP-JSON-subset document."""
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": self.service_name},
                            },
                            {
                                "key": "agent.runtime.subset_version",
                                "value": {"stringValue": self.subset_version},
                            },
                        ],
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": self.scope_name},
                            "spans": list(self._spans),
                        }
                    ],
                }
            ]
        }

    def write(self, path: str | Path) -> Path:
        """Serialize the document to ``path`` and return the path."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_otlp_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return p

    def validate(self) -> None:
        """Validate the assembled document against the subset schema.

        Raises :class:`src.runtime._schema.SchemaError` on drift.
        """
        validate_otlp_subset(self.to_otlp_dict())

    # ------------------------------------------------------------------
    # Inspection helpers (used by tests)
    # ------------------------------------------------------------------

    @property
    def span_count(self) -> int:
        """Total number of spans assembled so far."""
        return len(self._spans)

    @property
    def trace_id(self) -> Optional[str]:
        """The trace ID assigned on first emission, or ``None`` if not used."""
        return self._trace_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _new_trace_id(self) -> str:
        """Generate a 32-hex-char trace ID using the seeded RNG."""
        return self._rng.randbytes(16).hex()

    def _new_span_id(self) -> str:
        """Generate a 16-hex-char span ID using the seeded RNG."""
        return self._rng.randbytes(8).hex()

    def _make_span(
        self,
        *,
        name: str,
        attrs: Mapping[str, Any],
        start_time: str,
        end_time: str,
        parent_span_id: Optional[str],
    ) -> dict[str, Any]:
        span: dict[str, Any] = {
            "traceId": self._trace_id,
            "spanId": self._new_span_id(),
            "name": name,
            "kind": SPAN_KIND_INTERNAL,
            "startTimeUnixNano": start_time,
            "endTimeUnixNano": end_time,
            "attributes": _attrs_dict_to_otlp(attrs),
        }
        if parent_span_id is not None:
            span["parentSpanId"] = parent_span_id
        return span


def new_exporter(
    *,
    seed: int = 0,
    time_source: Optional[Callable[[], int]] = None,
) -> OtelJsonExporter:
    """Convenience factory returning an :class:`OtelJsonExporter`.

    Equivalent to ``OtelJsonExporter(seed=seed, time_source=time_source)``;
    exists so callers can write
    ``Agent(span_recorder=new_exporter(...))`` ergonomically.
    """
    return OtelJsonExporter(seed=seed, time_source=time_source)
