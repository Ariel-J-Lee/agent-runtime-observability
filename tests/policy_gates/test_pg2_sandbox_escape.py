"""PG2 — sandbox escape deny.

A ``read`` (or ``write``) call whose target ``os.path.realpath`` lies
outside the sandbox dir denies with ``rule_id="sandbox_path"`` and
metadata pointing at the offending path. The fixture lists multiple
trigger paths (per ``docs/policy-gates.md`` §3.1); this test asserts
the canonical path resolves correctly and additionally exercises each
listed trigger path against the policy checker directly so the rule
behaves consistently for every documented escape shape.
"""

from __future__ import annotations

from src.runtime import PolicyChecker
from tests.policy_gates._stubs import STUB_TOOL_SCHEMAS
from tests.policy_gates.conftest import (
    _resolve_sandbox_root,
    assert_universal_invariants,
    load_fixture,
    run_fixture,
)


def test_pg2_sandbox_escape_canonical_path(policy_spec, tmp_path):
    fixture, agent_result, spans = run_fixture(
        "pg2_sandbox_escape",
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
        if sc == "policy_check" and attrs.get("agent.policy.decision") == "deny"
    )
    for key in fixture["expected"]["policy_metadata_keys"]:
        assert key in deny_span

    assert deny_span["policy.target_path"] == "/etc/passwd"
    assert deny_span["policy.tool"] == "read"
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]


def test_pg2_sandbox_escape_all_documented_trigger_paths(policy_spec, tmp_path):
    """Every path in the fixture's ``trigger_paths`` list denies with the same rule."""
    fixture = load_fixture("pg2_sandbox_escape")
    sandbox_root = _resolve_sandbox_root(fixture, tmp_path)
    assert sandbox_root is not None

    checker = PolicyChecker(
        policy_spec,
        sandbox_root=sandbox_root,
        tool_schemas=STUB_TOOL_SCHEMAS,
    )

    for path in fixture["trigger_paths"]:
        decision = checker.check(tool_name="read", tool_args={"path": path})
        assert decision.decision == "deny", f"{path!r} did not deny"
        assert decision.rule_id == "sandbox_path"
