"""F1 — tool-call failure (transient; retry recovers).

A tool that fails on the first ``fail_count`` attempts then succeeds
should leave ``record.failure_mode = "tool_call_failure"`` on the
recovered step. The bounded-retry layer absorbs the transient
failures; the run itself terminates with the LLM's terminal answer
on the next step, not via a failure-mode terminal path.
"""

from __future__ import annotations

from src.fail import TOOL_CALL_FAILURE
from tests.failure_modes.conftest import (
    find_failure_mode_span,
    run_fixture,
)


def test_tool_call_failure_recovers_via_retry(policy_spec):
    fixture, agent_result, spans = run_fixture(
        "tool_call_failure",
        policy_spec_obj=policy_spec,
        max_retries=3,
    )

    # The step record carries the catalogued mode.
    record = agent_result.records[0]
    assert record.failure_mode == TOOL_CALL_FAILURE
    assert record.failure_mode == fixture["expected"]["failure_mode"]

    # The agent emits the failure_mode through the span_recorder.
    failure_span = find_failure_mode_span(spans)
    assert failure_span is not None
    assert failure_span["agent.failure_mode"] == TOOL_CALL_FAILURE

    # Bounded retry recorded the transient failures + the success.
    retry_spans = [a for sc, a in spans if sc == "retry_attempt"]
    transient_count = sum(
        1 for a in retry_spans if a.get("agent.retry.outcome") == "transient_failure"
    )
    success_count = sum(
        1 for a in retry_spans if a.get("agent.retry.outcome") == "success"
    )
    assert transient_count == fixture["expected"]["transient_failure_count"]
    assert success_count == 1

    # The tool ultimately succeeded; record carries an ok=true result.
    tool_results = [r for r in record.tool_results if r.get("tool") == "fetch"]
    assert tool_results
    assert tool_results[0]["ok"] is True

    # The run terminates with the LLM's final answer (next-step terminal),
    # not via a failure-mode-driven terminal path.
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
