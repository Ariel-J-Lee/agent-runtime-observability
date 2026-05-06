"""F3 — schema mismatch (policy seam denies before the tool runs)."""

from __future__ import annotations

from src.fail import SCHEMA_MISMATCH
from tests.failure_modes.conftest import (
    find_failure_mode_span,
    run_fixture,
)


def test_schema_mismatch_classifies_from_policy_arg_schema_deny(policy_spec):
    fixture, agent_result, spans = run_fixture(
        "schema_mismatch",
        policy_spec_obj=policy_spec,
    )

    record = agent_result.records[0]
    assert record.failure_mode == SCHEMA_MISMATCH
    assert record.failure_mode == fixture["expected"]["failure_mode"]

    # The agent emits the failure_mode through the span_recorder.
    failure_span = find_failure_mode_span(spans)
    assert failure_span is not None
    assert failure_span["agent.failure_mode"] == SCHEMA_MISMATCH

    # The policy_check span that triggered the classification carries
    # the rule_id="arg_schema" attribute.
    arg_schema_denies = [
        a for sc, a in spans
        if sc == "policy_check"
        and a.get("agent.policy.decision") == "deny"
        and a.get("agent.policy.rule_id") == "arg_schema"
    ]
    assert len(arg_schema_denies) == 1, (
        f"expected exactly one arg_schema deny; got {len(arg_schema_denies)}"
    )

    # The tool was NOT invoked (the policy denied before execution).
    tool_call_spans = [a for sc, a in spans if sc == "tool_call"]
    assert tool_call_spans == [], (
        f"expected no tool_call spans (policy denied); got {tool_call_spans!r}"
    )

    # The state record's policy_decisions log captures the deny.
    deny_decisions = [
        d for d in record.policy_decisions
        if d.get("decision") == "deny" and d.get("rule_id") == "arg_schema"
    ]
    assert deny_decisions

    # Terminal reason comes from the canned LLM (next step has no
    # canned entry, so the LLM stub emits final_answer).
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
