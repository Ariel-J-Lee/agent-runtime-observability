"""PG1 — off-allowlist URL deny.

A ``fetch`` call to a host that is not in ``policy.url_allowlist``
must produce a ``policy_check`` span carrying
``decision="deny"``, ``rule_id="url_allowlist"``, and the metadata
keys named in the fixture's ``policy_metadata_keys`` list.
"""

from __future__ import annotations

from tests.policy_gates.conftest import (
    assert_universal_invariants,
    run_fixture,
)


def test_pg1_off_allowlist_url(policy_spec, tmp_path):
    fixture, agent_result, spans = run_fixture(
        "pg1_off_allowlist_url",
        policy_spec_obj=policy_spec,
        tmp_path=tmp_path,
    )

    # Universal invariants (the three §4.4 assertions from the plan)
    assert_universal_invariants(
        fixture=fixture,
        agent_result=agent_result,
        spans=spans,
        policy_version=policy_spec.version,
    )

    # Per-scenario: the deny span carries the expected metadata keys
    deny_span = next(
        attrs for sc, attrs in spans
        if sc == "policy_check" and attrs.get("agent.policy.decision") == "deny"
    )
    for key in fixture["expected"]["policy_metadata_keys"]:
        assert key in deny_span, f"deny policy_check missing {key!r}; got attrs {deny_span!r}"

    # The fetched URL is the off-allowlist test host
    assert deny_span["policy.url"] == "https://evil.test/secret"
    assert deny_span["policy.host"] == "evil.test"
    assert deny_span["policy.tool"] == "fetch"

    # The agent terminates per the fixture's expected terminal reason
    assert agent_result.terminal_reason == fixture["expected"]["terminal_reason"]
