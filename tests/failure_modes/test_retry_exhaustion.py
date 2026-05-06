"""F2 — retry exhaustion (bounded retry's max_retries reached)."""

from __future__ import annotations

from src.fail import RETRY_EXHAUSTION
from tests.failure_modes.conftest import (
    find_failure_mode_span,
    run_fixture,
)


def test_retry_exhaustion_terminates_run(policy_spec):
    fixture, agent_result, spans = run_fixture(
        "retry_exhaustion",
        policy_spec_obj=policy_spec,
        max_retries=3,
    )

    record = agent_result.records[0]
    assert record.failure_mode == RETRY_EXHAUSTION
    assert record.failure_mode == fixture["expected"]["failure_mode"]

    failure_span = find_failure_mode_span(spans)
    assert failure_span is not None
    assert failure_span["agent.failure_mode"] == RETRY_EXHAUSTION

    # The run terminates via the retry-exhausted terminal reason.
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]

    # The error record names the catalog mode.
    error_records = [e for e in record.errors if e.get("error") == "retry_exhausted"]
    assert error_records, f"expected a retry_exhausted error; got {record.errors!r}"

    # The retry_attempt history shows transient_failure attempts followed
    # by an exhausted attempt.
    retry_spans = [a for sc, a in spans if sc == "retry_attempt"]
    outcomes = [a.get("agent.retry.outcome") for a in retry_spans]
    assert "exhausted" in outcomes
    assert outcomes.count("transient_failure") >= 1
