"""F4 — cycle detection (same (tool, args) repeated beyond max_repeats)."""

from __future__ import annotations

from src.fail import CYCLE_DETECTION
from tests.failure_modes.conftest import (
    find_failure_mode_span,
    run_fixture,
)


def test_cycle_detection_terminates_with_policy_denial(policy_spec):
    fixture, agent_result, spans = run_fixture(
        "cycle_detection",
        policy_spec_obj=policy_spec,
    )

    # The trigger fires on the (max_repeats + 1)th attempt of the
    # repeated (tool, args) pair. With max_repeats=3 in the canonical
    # policy, the 4th attempt (step_index=3) is the one that denies.
    expected_step = fixture["expected"]["trigger_step_index"]
    assert agent_result.step_count == expected_step + 1, (
        f"expected the agent to terminate at step {expected_step}; "
        f"step_count={agent_result.step_count}"
    )

    deny_record = agent_result.records[expected_step]
    assert deny_record.failure_mode == CYCLE_DETECTION
    assert deny_record.failure_mode == fixture["expected"]["failure_mode"]

    failure_span = find_failure_mode_span(spans)
    assert failure_span is not None
    assert failure_span["agent.failure_mode"] == CYCLE_DETECTION
    assert failure_span["agent.step_index"] == expected_step

    # The terminal reason is policy_denial_terminal — the literal
    # was reserved in PACKET-047's type union and is wired up here
    # for F4 only per the locked GO direction.
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
    assert agent_result.terminal_reason == "policy_denial_terminal"

    # The policy_check deny carries the cycle_detection rule_id.
    cycle_denies = [
        a for sc, a in spans
        if sc == "policy_check"
        and a.get("agent.policy.decision") == "deny"
        and a.get("agent.policy.rule_id") == "cycle_detection"
    ]
    assert len(cycle_denies) == 1


def test_cycle_key_uses_json_sorted_keys(policy_spec):
    """Two args dicts with identical content but different key order share a cycle key.

    The locked cycle key is ``(tool, json.dumps(args, sort_keys=True))``,
    so ``{"a": 1, "b": 2}`` and ``{"b": 2, "a": 1}`` count as the same
    pair. Without ``sort_keys=True`` they would count as distinct.
    """
    from src.runtime import Agent
    from tests.failure_modes._stubs import (
        STUB_TOOL_SCHEMAS,
        build_tool_registry,
        make_canned_llm,
    )
    from src.runtime import PolicyChecker

    canned = [
        {"step_index": i, "tool": "search", "args": {"a": 1, "b": 2} if i % 2 == 0
         else {"b": 2, "a": 1}}
        for i in range(4)
    ]
    spans: list = []

    def _recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    agent = Agent(
        llm=make_canned_llm(canned),
        tool_registry=build_tool_registry(None),
        policy_checker=PolicyChecker(policy_spec, tool_schemas=STUB_TOOL_SCHEMAS),
        span_recorder=_recorder,
    )
    result = agent.run("normalized cycle key test")

    # If the cycle key normalized correctly, the 4th attempt (step 3)
    # denies just like the regular cycle test.
    assert result.terminal_reason == "policy_denial_terminal"
    assert result.records[-1].failure_mode == CYCLE_DETECTION
