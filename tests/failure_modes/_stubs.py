"""Shared test stubs for the failure-mode suite.

The locked decision (per the canonical plan + GO direction) is a
**shared failing-tool stub with per-fixture behavior**: one factory
that builds a tool callable configured by the fixture's
``stub_behavior`` block. The five canonical modes drive different
configurations:

- F1 ``tool_call_failure``: ``mode="fail_then_succeed"`` —
  ``ConnectionError`` on the first ``fail_count`` calls, success
  thereafter. The bounded-retry layer recovers.
- F2 ``retry_exhaustion``: ``mode="always_fail"`` —
  ``ConnectionError`` on every call; bounded retry exhausts and
  raises :class:`src.runtime.RetryExhausted`.
- F3 ``schema_mismatch``: no ``stub_behavior`` — the call's args
  fail the input JSON-schema; the policy seam denies before the
  tool runs.
- F4 ``cycle_detection``: no ``stub_behavior`` — the canned LLM
  emits the same ``(tool, args)`` pair beyond
  ``policy.cycle_detection.max_repeats``; the agent's per-run
  cycle tracker triggers deny on the offending step.
- F5 ``catalogued_unhandled``: ``mode="raise_unhandled"`` — the
  stub raises a custom :class:`_F5UnhandledError` which is a
  ``BaseException`` subclass (not ``Exception``). Bypasses
  bounded-retry's default retry predicate; the agent's
  ``except BaseException`` catch classifies via the catalog.

This module is **test-only**: never imported by runtime code.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.runtime import LLMInput, LLMOutput, ToolCall


# ---------------------------------------------------------------------------
# Stub input JSON-schemas (re-used from the policy-gate suite).
# ---------------------------------------------------------------------------

STUB_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search": {
        "type": "object",
        "required": ["query"],
        "additionalProperties": False,
        "properties": {"query": {"type": "string", "minLength": 1}},
    },
    "fetch": {
        "type": "object",
        "required": ["url"],
        "additionalProperties": False,
        "properties": {"url": {"type": "string", "minLength": 1}},
    },
    "read": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}},
    },
    "write": {
        "type": "object",
        "required": ["path", "content"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1},
            "content": {"type": "string"},
        },
    },
    "summarize": {
        "type": "object",
        "required": ["text"],
        "additionalProperties": False,
        "properties": {"text": {"type": "string", "minLength": 1}},
    },
}


# ---------------------------------------------------------------------------
# Custom non-Exception class for F5.
# ---------------------------------------------------------------------------


class _F5UnhandledError(BaseException):
    """Custom non-``Exception`` class that bypasses bounded_retry's default predicate.

    The ``_is_retryable_default`` predicate returns ``False`` for any
    ``BaseException`` that isn't an ``Exception`` subclass. Raising
    this class from a stub tool causes the bounded-retry layer to
    propagate the exception immediately rather than retrying it; the
    agent's ``except BaseException`` catch then classifies the failure
    as ``catalogued_unhandled`` (F5).

    The class lives in the test surface only. T-TOOLS' real tools never
    raise this; F5 in production would fire on (e.g.) ``MemoryError``
    or any other ``BaseException`` subclass that the default predicate
    excludes from retry.
    """


# ---------------------------------------------------------------------------
# Shared failing-tool stub factory.
# ---------------------------------------------------------------------------


def make_tool_stub(tool_name: str, behavior: Mapping[str, Any] | None = None):
    """Return a stub tool callable configured by ``behavior``.

    Args:
        tool_name: One of the five v1 tool names (``search`` / ``fetch`` /
            ``read`` / ``write`` / ``summarize``). Used only for the
            fall-through default-stub return value shape.
        behavior: ``None`` for default (always-succeeds) behavior, or a
            dict with a ``mode`` field selecting one of:
            - ``"fail_then_succeed"`` (with ``fail_count: int``)
            - ``"always_fail"``
            - ``"raise_unhandled"`` (with ``exception_class: str``)

    Returns:
        A callable matching the v1 tool shape that takes keyword
        arguments per the input schema and returns a JSON-serializable
        result (or raises per the configured behavior).
    """
    state = {"calls": 0}

    def _default_result(**kwargs: Any) -> dict[str, Any]:
        if tool_name == "search":
            return {"hits": [f"doc-for-{kwargs.get('query', '')}"]}
        if tool_name == "fetch":
            return {"url": kwargs.get("url", ""), "body": "stub body"}
        if tool_name == "read":
            return {"path": kwargs.get("path", ""), "content": "stub content"}
        if tool_name == "write":
            return {"path": kwargs.get("path", ""), "ok": True}
        if tool_name == "summarize":
            return {"summary": str(kwargs.get("text", ""))[:64]}
        return {"ok": True}

    if not behavior:
        return lambda **kwargs: _default_result(**kwargs)

    mode = behavior.get("mode", "default")

    if mode == "fail_then_succeed":
        fail_count = int(behavior.get("fail_count", 1))

        def _fail_then_succeed(**kwargs: Any) -> dict[str, Any]:
            state["calls"] += 1
            if state["calls"] <= fail_count:
                raise ConnectionError(
                    f"stub {tool_name}: deterministic failure on call {state['calls']}"
                )
            return _default_result(**kwargs)

        return _fail_then_succeed

    if mode == "always_fail":

        def _always_fail(**kwargs: Any) -> dict[str, Any]:
            state["calls"] += 1
            raise ConnectionError(
                f"stub {tool_name}: deterministic always-fail on call {state['calls']}"
            )

        return _always_fail

    if mode == "raise_unhandled":

        def _raise_unhandled(**kwargs: Any) -> dict[str, Any]:
            state["calls"] += 1
            raise _F5UnhandledError(
                f"stub {tool_name}: deterministic non-retryable failure"
            )

        return _raise_unhandled

    raise ValueError(f"unknown stub_behavior.mode: {mode!r}")


def build_tool_registry(behavior: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build the five-tool registry. ``behavior`` configures one specific tool.

    Tools other than ``behavior['tool']`` get the default succeeds-on-every-call
    stub; the named tool gets the configured behavior. ``behavior=None`` means
    every tool uses the default stub.
    """
    target_tool = behavior.get("tool") if behavior else None
    return {
        name: make_tool_stub(name, behavior if name == target_tool else None)
        for name in ("search", "fetch", "read", "write", "summarize")
    }


# ---------------------------------------------------------------------------
# Deterministic stub LLM (same shape as the policy-gate suite).
# ---------------------------------------------------------------------------


def make_canned_llm(canned_tool_calls: Sequence[Mapping[str, Any]]):
    """Return an LLM callable that emits ``canned_tool_calls`` one per step.

    Each canned entry has shape ``{"step_index": int, "tool": str, "args": dict}``.
    Steps beyond the canned list emit a terminal ``final_answer``.
    """
    by_step = {entry["step_index"]: entry for entry in canned_tool_calls}

    def _llm(inp: LLMInput) -> LLMOutput:
        entry = by_step.get(inp.step_index)
        if entry is None:
            return LLMOutput(final_answer="(no canned step)", raw_text="")
        tc = ToolCall(tool=entry["tool"], args=dict(entry.get("args") or {}))
        return LLMOutput(intended_tool_calls=(tc,), raw_text=str(entry))

    return _llm
