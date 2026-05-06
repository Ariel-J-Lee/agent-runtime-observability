"""PG4 — forbidden tool deny.

A tool name not present in ``policy.tool_registry.allowed`` (and not
in ``denied``) denies with ``rule_id="tool_registry"`` and
``policy.registry_match="not_in_allowlist"``.
"""

from __future__ import annotations

from tests.policy_gates.conftest import (
    assert_universal_invariants,
    run_fixture,
)


def test_pg4_forbidden_tool(policy_spec, tmp_path):
    fixture, agent_result, spans = run_fixture(
        "pg4_forbidden_tool",
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
        and attrs.get("agent.policy.rule_id") == "tool_registry"
    )
    for key in fixture["expected"]["policy_metadata_keys"]:
        assert key in deny_span
    assert deny_span["policy.requested_tool"] == "delete"
    assert deny_span["policy.registry_match"] == "not_in_allowlist"
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
