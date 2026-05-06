"""PG3 — loop budget deny (tokens variant).

The token-budget deny is exercised against the policy checker
directly: ``check_loop_budget(tokens=...)`` returns deny with
``policy.limit_kind="tokens"`` when cumulative LLM tokens reach
``policy.loop_budget.max_tokens`` (50,000). The current ``Agent``
loop does not yet thread token counts through ``LLMOutput`` (per
PACKET-047 §2.4 the token-count field is reserved for the v1+
follow-on); the policy rule is verified at the seam, and the fixture
records the trigger_step_index so a later agent extension can wire
the loop accounting to this rule without changing the policy code.
"""

from __future__ import annotations

from src.runtime import PolicyChecker
from tests.policy_gates._stubs import STUB_TOOL_SCHEMAS
from tests.policy_gates.conftest import load_fixture


def test_pg3_loop_budget_tokens(policy_spec, tmp_path):
    fixture = load_fixture("pg3_loop_budget_tokens")
    assert fixture["scenario_class"] == "PG3"
    assert fixture["variant"] == "tokens"

    checker = PolicyChecker(policy_spec, tool_schemas=STUB_TOOL_SCHEMAS)
    max_tokens = int(policy_spec.get("loop_budget.max_tokens"))

    # Below the budget — allow.
    allow = checker.check_loop_budget(iterations=0, tokens=max_tokens - 1)
    assert allow.decision == "allow"

    # At the budget — deny with tokens kind.
    deny = checker.check_loop_budget(iterations=0, tokens=max_tokens)
    assert deny.decision == "deny"
    assert deny.rule_id == "loop_budget"
    for key in fixture["expected"]["policy_metadata_keys"]:
        assert key in deny.metadata, f"deny metadata missing {key!r}"
    assert deny.metadata["policy.limit_kind"] == "tokens"
    assert deny.metadata["policy.tokens"] == max_tokens
    assert deny.metadata["policy.max_tokens"] == max_tokens

    # Above the budget — still deny.
    over = checker.check_loop_budget(iterations=0, tokens=max_tokens + 1)
    assert over.decision == "deny"
    assert over.rule_id == "loop_budget"
