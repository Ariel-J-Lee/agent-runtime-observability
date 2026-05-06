"""PG5 — argument-shape violation deny.

A registered tool called with arguments that fail its input
JSON-schema denies with ``rule_id="arg_schema"``. The deny carries
``policy.tool``, ``policy.schema_error``, and ``policy.failed_path``.

Per the plan §3.4, T-FAIL later reads ``rule_id="arg_schema"`` to set
``agent.failure_mode="schema_mismatch"`` (F3). That T-FAIL behavior
is out of scope for this lane; this test only asserts the policy-side
deny.
"""

from __future__ import annotations

from tests.policy_gates.conftest import (
    assert_universal_invariants,
    run_fixture,
)


def test_pg5_arg_schema(policy_spec, tmp_path):
    fixture, agent_result, spans = run_fixture(
        "pg5_arg_schema",
        policy_spec_obj=policy_spec,
        tmp_path=tmp_path,
    )

    assert_universal_invariants(
        fixture=fixture,
        agent_result=agent_result,
        spans=spans,
        policy_version=policy_spec.version,
    )

    deny_span = next(
        attrs for sc, attrs in spans
        if sc == "policy_check"
        and attrs.get("agent.policy.decision") == "deny"
        and attrs.get("agent.policy.rule_id") == "arg_schema"
    )
    for key in fixture["expected"]["policy_metadata_keys"]:
        assert key in deny_span
    assert deny_span["policy.tool"] == "search"
    assert "policy.schema_error" in deny_span
    # Validation hits the integer-where-string-expected at /query
    assert deny_span["policy.failed_path"] == "/query"
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
