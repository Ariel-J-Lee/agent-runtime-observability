"""Shared test stubs for the policy-gate suite.

The policy-gate tests need:

1. **Stub input JSON-schemas** for the five v1 tools so
   ``PolicyChecker(arg_schema_enforcement="strict")`` can validate
   tool calls without the real :mod:`tools` package shipping yet.
2. **Stub tool implementations** so the agent loop has something to
   invoke when a call passes policy.
3. **A deterministic stub LLM** keyed by a fixture's
   ``canned_llm_tool_calls`` array so the loop walks a known sequence.

This module is **test-only**: it lives under ``tests/policy_gates/``
and is never imported by runtime code. T-TOOLS later ships the real
tool implementations under :mod:`tools` and the real input schemas;
T-FIXTURES later ships the deterministic stub LLM under
``src/runtime/stub_llm/``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.runtime import LLMInput, LLMOutput, ToolCall


# ---------------------------------------------------------------------------
# Stub input JSON-schemas for the five v1 tools.
# ---------------------------------------------------------------------------
#
# The shapes are intentionally minimal — just enough to drive the PG5
# argument-shape rule. T-TOOLS replaces these with the real per-tool
# input schemas at execution time.

STUB_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search": {
        "type": "object",
        "required": ["query"],
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 1},
        },
    },
    "fetch": {
        "type": "object",
        "required": ["url"],
        "additionalProperties": False,
        "properties": {
            "url": {"type": "string", "minLength": 1},
        },
    },
    "read": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1},
        },
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
        "properties": {
            "text": {"type": "string", "minLength": 1},
        },
    },
}


# ---------------------------------------------------------------------------
# Stub tool implementations.
# ---------------------------------------------------------------------------


def stub_search(*, query: str) -> dict[str, Any]:
    return {"hits": [f"doc-for-{query}"]}


def stub_fetch(*, url: str) -> dict[str, Any]:
    return {"url": url, "body": "stub body"}


def stub_read(*, path: str) -> dict[str, Any]:
    return {"path": path, "content": "stub content"}


def stub_write(*, path: str, content: str) -> dict[str, Any]:
    return {"path": path, "ok": True}


def stub_summarize(*, text: str) -> dict[str, Any]:
    return {"summary": text[:64]}


STUB_TOOL_REGISTRY: dict[str, Any] = {
    "search": stub_search,
    "fetch": stub_fetch,
    "read": stub_read,
    "write": stub_write,
    "summarize": stub_summarize,
}


# ---------------------------------------------------------------------------
# Deterministic stub LLM keyed by canned_llm_tool_calls.
# ---------------------------------------------------------------------------


def make_canned_llm(canned_tool_calls: Sequence[Mapping[str, Any]]):
    """Return an LLM callable that emits ``canned_tool_calls`` one per step.

    Each canned entry has shape ``{"step_index": int, "tool": str,
    "args": dict, "tokens"?: int}``. The LLM emits a single tool call per
    step and never emits a terminal ``final_answer`` until the canned
    list is exhausted (then signals "no answer reached"). For loop-budget
    tests the canned list is intentionally longer than the budget; for
    other tests the canned list ends with the trigger step and the loop
    terminates due to policy denial.

    The optional ``tokens`` field on each entry surfaces in the
    ``LLMOutput.raw_text`` as a token count marker the test driver can
    pass into the agent's loop-budget checker (the current ``Agent``
    doesn't propagate token counts; tests for the tokens variant drive
    ``PolicyChecker.check_loop_budget(tokens=...)`` directly).
    """
    by_step = {entry["step_index"]: entry for entry in canned_tool_calls}

    def _llm(inp: LLMInput) -> LLMOutput:
        entry = by_step.get(inp.step_index)
        if entry is None:
            return LLMOutput(final_answer="(no canned step for this index)", raw_text="")
        tc = ToolCall(tool=entry["tool"], args=dict(entry.get("args") or {}))
        return LLMOutput(intended_tool_calls=(tc,), raw_text=str(entry))

    return _llm
