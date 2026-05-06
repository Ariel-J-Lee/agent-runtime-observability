"""PG3 — loop budget deny (iterations variant).

When the agent loop reaches ``policy.loop_budget.max_iterations`` (10)
without a terminal answer, ``check_loop_budget()`` returns deny with
``rule_id="loop_budget"`` and ``policy.limit_kind="iterations"``.

**Known runtime gap (documented for the next runtime-side slice).**
``Agent.run()`` walks ``range(max_iterations)`` and short-circuits to
``terminal_reason="loop_budget_exhausted"`` via the for-else branch
when the loop exhausts; the implementation does not currently emit a
``policy_check`` deny span at that boundary even though the literal
type already includes ``policy_denial_terminal``. The runtime gap is
out of this lane's owned surface (per the load-bearing plan §7.2 the
``Agent`` public surface stays unchanged at this packet); a follow-on
runtime extension will wire the for-loop exhaustion to a final
``check_loop_budget`` emit so the canonical run's trace contains the
deny span.

This test asserts the load-bearing facts the policy seam already
produces:

1. The agent runs exactly ``max_iterations`` steps.
2. The agent terminates with ``terminal_reason="loop_budget_exhausted"``.
3. ``check_loop_budget(iterations=max_iterations)`` returns the
   expected deny shape on direct call (same pattern as the tokens
   variant test).
"""

from __future__ import annotations

from src.runtime import PolicyChecker
from tests.policy_gates._stubs import STUB_TOOL_SCHEMAS
from tests.policy_gates.conftest import load_fixture, run_fixture


def test_pg3_loop_runs_max_iterations_and_terminates(policy_spec, tmp_path):
    fixture, agent_result, _spans = run_fixture(
        "pg3_loop_budget",
        policy_spec_obj=policy_spec,
        tmp_path=tmp_path,
    )
    max_iter = int(policy_spec.get("loop_budget.max_iterations"))

    assert agent_result.terminal_reason == "loop_budget_exhausted"
    assert agent_result.step_count == max_iter
    assert fixture["expected"]["trigger_step_index"] == max_iter


def test_pg3_loop_budget_check_returns_deny_at_max_iterations(policy_spec):
    """The policy seam returns the documented deny shape when called directly."""
    fixture = load_fixture("pg3_loop_budget")
    checker = PolicyChecker(policy_spec, tool_schemas=STUB_TOOL_SCHEMAS)
    max_iter = int(policy_spec.get("loop_budget.max_iterations"))

    # Below max — allow.
    allow = checker.check_loop_budget(iterations=max_iter - 1)
    assert allow.decision == "allow"

    # At max — deny with iterations kind.
    deny = checker.check_loop_budget(iterations=max_iter)
    assert deny.decision == "deny"
    assert deny.rule_id == "loop_budget"
    for key in fixture["expected"]["policy_metadata_keys"]:
        assert key in deny.metadata, f"deny metadata missing {key!r}"
    assert deny.metadata["policy.limit_kind"] == "iterations"
    assert deny.metadata["policy.iterations"] == max_iter
    assert deny.metadata["policy.max_iterations"] == max_iter
