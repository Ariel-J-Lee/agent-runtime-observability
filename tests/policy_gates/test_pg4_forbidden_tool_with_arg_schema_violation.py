"""PG4 precedence variant — tool_registry must win over arg_schema.

When an unregistered tool is called with arguments that would also
fail the input JSON-schema, the locked first-deny-wins precedence
(plan §1.6) requires ``tool_registry`` to fire FIRST and produce
exactly one ``policy_check`` deny with ``rule_id="tool_registry"``.
The captured trace must NOT show an ``arg_schema`` deny.
"""

from __future__ import annotations

from tests.policy_gates.conftest import (
    assert_universal_invariants,
    run_fixture,
)


def test_pg4_precedence_tool_registry_wins_over_arg_schema(policy_spec, tmp_path):
    fixture, agent_result, spans = run_fixture(
        "pg4_forbidden_tool_with_arg_schema_violation",
        policy_spec_obj=policy_spec,
        tmp_path=tmp_path,
    )

    assert_universal_invariants(
        fixture=fixture,
        agent_result=agent_result,
        spans=spans,
        policy_version=policy_spec.version,
    )

    # The deny must be tool_registry, not arg_schema.
    policy_spans = [a for sc, a in spans if sc == "policy_check"]
    deny_spans = [a for a in policy_spans if a.get("agent.policy.decision") == "deny"]
    rule_ids = [a.get("agent.policy.rule_id") for a in deny_spans]
    assert "tool_registry" in rule_ids
    assert "arg_schema" not in rule_ids, (
        f"arg_schema deny fired despite earlier tool_registry deny — "
        f"first-deny-wins precedence violated. rule_ids={rule_ids!r}"
    )

    deny_span = next(
        a for a in deny_spans if a.get("agent.policy.rule_id") == "tool_registry"
    )
    assert deny_span["policy.registry_match"] == "not_in_allowlist"
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
