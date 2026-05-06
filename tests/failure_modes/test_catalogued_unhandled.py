"""F5 — catalogued unhandled (tool raises a non-retryable exception)."""

from __future__ import annotations

from src.fail import CATALOGUED_UNHANDLED
from tests.failure_modes.conftest import (
    find_failure_mode_span,
    run_fixture,
)


def test_catalogued_unhandled_classifies_arbitrary_exception(policy_spec):
    fixture, agent_result, spans = run_fixture(
        "catalogued_unhandled",
        policy_spec_obj=policy_spec,
    )

    record = agent_result.records[0]
    assert record.failure_mode == CATALOGUED_UNHANDLED
    assert record.failure_mode == fixture["expected"]["failure_mode"]

    failure_span = find_failure_mode_span(spans)
    assert failure_span is not None
    assert failure_span["agent.failure_mode"] == CATALOGUED_UNHANDLED

    # The error record names the exception class so a reviewer reading
    # state.jsonl can see what raised, even though the runtime didn't
    # have a more-specific catalog mode for it.
    error_records = [
        e for e in record.errors if e.get("error") == "catalogued_unhandled"
    ]
    assert error_records
    assert error_records[0]["exception_class"] == fixture["expected"]["exception_class"]

    # The run terminates via the retry-exhausted terminal reason — the
    # F5 catch shares the terminal path with F2 since both abandon
    # tool execution. The fine-grained F5 vs F2 distinction is in
    # ``record.failure_mode``.
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
