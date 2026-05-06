"""Tests for the deterministic stub LLM."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import LLMInput, ToolCall, make_canned_llm
from src.runtime.stub_llm.canned import CannedLLM, EXHAUSTED_DEFAULT


def _llm_input(step: int) -> LLMInput:
    return LLMInput(run_id="r", step_index=step, user_question="q")


def test_emits_tool_call_at_known_step():
    llm = make_canned_llm([
        {"step_index": 0, "tool": "search", "args": {"query": "x"}},
    ])
    out = llm(_llm_input(0))
    assert out.final_answer is None
    assert out.intended_tool_calls == (ToolCall(tool="search", args={"query": "x"}),)


def test_emits_final_answer_at_canned_terminal_step():
    llm = make_canned_llm([
        {"step_index": 0, "tool": "search", "args": {"query": "x"}},
        {"step_index": 1, "final_answer": "done"},
    ])
    assert llm(_llm_input(1)).final_answer == "done"


def test_exhaustion_returns_default_final_answer_when_provided():
    llm = make_canned_llm(
        [{"step_index": 0, "tool": "search", "args": {"query": "x"}}],
        default_final_answer="no canned answer",
    )
    assert llm(_llm_input(99)).final_answer == "no canned answer"


def test_exhaustion_returns_sentinel_when_no_default_provided():
    llm = make_canned_llm([{"step_index": 0, "tool": "search", "args": {"query": "x"}}])
    assert llm(_llm_input(99)).final_answer == EXHAUSTED_DEFAULT


def test_canned_llm_is_deterministic_across_calls():
    canned = [
        {"step_index": 0, "tool": "search", "args": {"query": "x"}},
        {"step_index": 1, "tool": "fetch", "args": {"url": "file:///y"}},
    ]
    a = make_canned_llm(canned)
    b = make_canned_llm(canned)
    for step in range(3):
        assert a(_llm_input(step)) == b(_llm_input(step))


def test_canned_llm_class_alias_is_callable():
    llm = CannedLLM([{"step_index": 0, "tool": "x", "args": {"y": 1}}])
    out = llm(_llm_input(0))
    assert out.intended_tool_calls[0].tool == "x"


def test_canned_llm_handles_args_with_int_values():
    """The runtime's tool registry passes args as-is to tools; the
    stub LLM must not coerce values, so policy-gate fixtures like PG5
    that send ``query: 12345`` round-trip without mutation."""
    llm = make_canned_llm([{"step_index": 0, "tool": "search", "args": {"query": 12345}}])
    out = llm(_llm_input(0))
    assert out.intended_tool_calls[0].args == {"query": 12345}


def test_canned_llm_default_args_are_empty_dict():
    """Missing ``args`` should produce an empty kwargs dict, not raise."""
    llm = make_canned_llm([{"step_index": 0, "tool": "search"}])
    out = llm(_llm_input(0))
    assert out.intended_tool_calls[0].args == {}


def test_existing_pg_stub_re_export_drives_equivalent_behavior():
    """Lock the PACKET-053 graduation: the test-only shim under
    ``tests/policy_gates/_stubs.py`` must produce identical behavior
    to the canonical helper at ``src.runtime.stub_llm.canned``."""
    from tests.policy_gates._stubs import make_canned_llm as shim_factory

    canned = [
        {"step_index": 0, "tool": "search", "args": {"query": "alpha"}},
        {"step_index": 1, "tool": "fetch", "args": {"url": "file:///x"}},
    ]
    canonical = make_canned_llm(canned)
    shim = shim_factory(canned)
    for step in range(3):
        assert canonical(_llm_input(step)) == shim(_llm_input(step))
