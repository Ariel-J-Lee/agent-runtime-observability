"""Shared helpers for the trace-export test suite.

Provides:

- :func:`make_deterministic_time_source` — monotonic counter so
  ``startTimeUnixNano`` / ``endTimeUnixNano`` are reproducible across
  test runs
- :func:`build_stub_agent` — wires a stub LLM + stub tool registry +
  the supplied exporter; mirrors the policy-gate / failure-mode
  test stub patterns so the trace-export integration test exercises
  the same code paths the canonical run will hit
- :func:`extract_span` / :func:`get_attribute` — readers that pull a
  span by name + attribute key from the assembled OTLP doc
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import (
    Agent,
    LLMInput,
    LLMOutput,
    PermissivePolicyChecker,
    ToolCall,
)


def make_deterministic_time_source(start_ns: int = 1_700_000_000_000_000_000) -> Callable[[], int]:
    """Return a callable that yields monotonically increasing nanoseconds.

    Each call returns ``start_ns + n * 1_000_000`` (1 ms apart) so the
    captured trace's timestamps are reproducible and ordered.
    """
    state = {"n": 0}

    def _now_ns() -> int:
        t = start_ns + state["n"] * 1_000_000
        state["n"] += 1
        return t

    return _now_ns


def make_canned_llm(canned_tool_calls: Sequence[Mapping[str, Any]]):
    """Return a deterministic stub LLM keyed by ``canned_tool_calls``.

    Mirrors the helper in ``tests/policy_gates/_stubs.py`` and
    ``tests/failure_modes/_stubs.py`` so the trace tests can drive the
    agent loop without depending on either suite.
    """
    by_step = {entry["step_index"]: entry for entry in canned_tool_calls}

    def _llm(inp: LLMInput) -> LLMOutput:
        entry = by_step.get(inp.step_index)
        if entry is None:
            return LLMOutput(final_answer="(no canned step)", raw_text="")
        tc = ToolCall(tool=entry["tool"], args=dict(entry.get("args") or {}))
        return LLMOutput(intended_tool_calls=(tc,), raw_text=str(entry))

    return _llm


def stub_search(*, query: str) -> dict[str, Any]:
    return {"hits": [f"doc-for-{query}"]}


def stub_fetch(*, url: str) -> dict[str, Any]:
    return {"url": url, "body": "stub"}


_DEFAULT_TOOL_REGISTRY: dict[str, Any] = {
    "search": stub_search,
    "fetch": stub_fetch,
}


def build_stub_agent(
    *,
    canned_tool_calls: Sequence[Mapping[str, Any]],
    span_recorder: Callable[[str, Mapping[str, Any]], None],
    tool_registry: Optional[Mapping[str, Any]] = None,
) -> Agent:
    """Wire a stub :class:`Agent` for the trace tests."""
    return Agent(
        llm=make_canned_llm(canned_tool_calls),
        tool_registry=dict(tool_registry or _DEFAULT_TOOL_REGISTRY),
        policy_checker=PermissivePolicyChecker(),
        span_recorder=span_recorder,
        max_iterations=10,
    )


def extract_spans_by_name(doc: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    """Return every span in the assembled OTLP doc with ``name == name``."""
    out: list[dict[str, Any]] = []
    for resource_spans in doc.get("resourceSpans", []):
        for scope_spans in resource_spans.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                if span.get("name") == name:
                    out.append(span)
    return out


def all_spans(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flat list of every span in the assembled OTLP doc."""
    out: list[dict[str, Any]] = []
    for resource_spans in doc.get("resourceSpans", []):
        for scope_spans in resource_spans.get("scopeSpans", []):
            out.extend(scope_spans.get("spans", []))
    return out


def get_attribute(span: Mapping[str, Any], key: str) -> Optional[Any]:
    """Return the OTLP-encoded value for ``key`` (the inner ``stringValue`` etc.)."""
    for kv in span.get("attributes", []):
        if kv.get("key") == key:
            value = kv.get("value", {})
            for type_key in ("stringValue", "intValue", "boolValue", "doubleValue"):
                if type_key in value:
                    return value[type_key]
            return None
    return None
