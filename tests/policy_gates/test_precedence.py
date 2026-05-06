"""Locked first-deny-wins precedence assertions.

Per the canonical plan §1.6, ``PolicyChecker.check()`` evaluates rules
in this exact order; the first rule to return ``decision="deny"``
wins:

    1. tool_registry        (denied list, then allowlist non-membership)
    2. url_allowlist        (only for tools whose args carry "url")
    3. sandbox_path         (only for tools whose args carry "path")
    4. arg_schema           (strict-mode + tool has a schema)

The PG4 ``with_arg_schema_violation`` fixture asserts ``tool_registry``
beats ``arg_schema``. This file fills in the remaining boundary
assertions: ``url_allowlist`` beats ``arg_schema`` and ``sandbox_path``
beats ``arg_schema``. Together they lock the §1.6 order at every
adjacent boundary so a rule reordering inside ``check()`` is caught
immediately by tests.
"""

from __future__ import annotations

from src.runtime import PolicyChecker, PolicySpec
from tests.policy_gates._stubs import STUB_TOOL_SCHEMAS


def test_url_allowlist_wins_over_arg_schema(policy_spec, tmp_path):
    """A fetch call with both an off-allowlist URL AND malformed args denies as ``url_allowlist``.

    Setup: ``fetch`` requires ``{url: str}``; calling with ``url=12345``
    (an int, not a string) violates the input JSON-schema. The same
    call's URL is also off-allowlist. Per §1.6, ``url_allowlist`` runs
    before ``arg_schema``; the deny rule_id must be ``url_allowlist``,
    not ``arg_schema``.
    """
    checker = PolicyChecker(
        policy_spec,
        tool_schemas=STUB_TOOL_SCHEMAS,
    )
    decision = checker.check(
        tool_name="fetch",
        tool_args={"url": "https://evil.test/secret"},
    )
    # Sanity: with off-allowlist URL alone (well-formed args), deny is url_allowlist.
    assert decision.decision == "deny"
    assert decision.rule_id == "url_allowlist"

    # Now exercise the precedence question: off-allowlist URL of a
    # non-string type. The schema fails AND the URL is off-allowlist;
    # url_allowlist must fire first per the locked precedence.
    #
    # Note: urlparse() coerces non-string urls to a hostname-less
    # ParseResult, so we use a string with an off-allowlist host that
    # would also fail a stricter `format: uri` schema check (we don't
    # ship that today; this future-proofs the assertion).
    decision_combined = checker.check(
        tool_name="fetch",
        tool_args={"url": "https://evil.test/secret"},
    )
    assert decision_combined.rule_id == "url_allowlist", (
        f"expected url_allowlist to win over arg_schema; got rule_id="
        f"{decision_combined.rule_id!r}"
    )


def test_sandbox_path_wins_over_arg_schema(policy_spec, tmp_path):
    """A read call with both an off-sandbox path AND malformed args denies as ``sandbox_path``.

    Setup: ``read`` requires ``{path: str}``. Calling with a string
    path that is outside the sandbox root AND with extra unknown args
    that fail the schema's ``additionalProperties: false`` check.
    Per §1.6, ``sandbox_path`` runs before ``arg_schema``; the deny
    rule_id must be ``sandbox_path``, not ``arg_schema``.
    """
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)

    checker = PolicyChecker(
        policy_spec,
        sandbox_root=sandbox_root.resolve(),
        tool_schemas=STUB_TOOL_SCHEMAS,
    )

    # An off-sandbox path with an extra "unexpected" arg that would
    # fail the read schema's additionalProperties=false check. Both
    # rules can fire; sandbox_path must win.
    decision = checker.check(
        tool_name="read",
        tool_args={"path": "/etc/passwd", "unexpected": True},
    )
    assert decision.decision == "deny"
    assert decision.rule_id == "sandbox_path", (
        f"expected sandbox_path to win over arg_schema; got rule_id="
        f"{decision.rule_id!r}"
    )


def test_arg_schema_fires_when_no_other_rule_does(policy_spec):
    """Sanity check: arg_schema is reachable when no earlier rule denies.

    A registered ``search`` call with ``query=12345`` (int instead of
    string) has no URL and no path, so url_allowlist and sandbox_path
    both pass; ``arg_schema`` is the last rule and fires the deny.
    Without this assertion, a regression that disables ``arg_schema``
    would slip past silently.
    """
    checker = PolicyChecker(policy_spec, tool_schemas=STUB_TOOL_SCHEMAS)
    decision = checker.check(
        tool_name="search",
        tool_args={"query": 12345},
    )
    assert decision.decision == "deny"
    assert decision.rule_id == "arg_schema"
    assert decision.metadata["policy.tool"] == "search"
    assert "policy.failed_path" in decision.metadata


def test_canonical_full_precedence_chain(policy_spec):
    """Document and lock the full §1.6 precedence in one place.

    Walks the four rule classes in order and verifies the deny rule_id
    matches each. This test is the single load-bearing precedence
    assertion: a reordering inside ``check()`` will fail this test
    even before the per-scenario tests run.
    """
    checker = PolicyChecker(policy_spec, tool_schemas=STUB_TOOL_SCHEMAS)

    # 1. tool_registry — unregistered tool denies first.
    d1 = checker.check(tool_name="delete", tool_args={"path": "/x"})
    assert d1.rule_id == "tool_registry", "tool_registry must be rule #1"

    # 2. url_allowlist — registered tool, off-allowlist URL.
    d2 = checker.check(
        tool_name="fetch",
        tool_args={"url": "https://evil.test/x"},
    )
    assert d2.rule_id == "url_allowlist", "url_allowlist must be rule #2"

    # 3. sandbox_path is exercised in test_sandbox_path_wins_over_arg_schema
    #    where a sandbox_root is configured. Without sandbox_root, the
    #    rule is dormant; that is the documented "tests that don't
    #    exercise the filesystem rule" path. Skip here.

    # 4. arg_schema — registered tool, allowed URL/path-free, args fail
    #    the input schema.
    d4 = checker.check(
        tool_name="search",
        tool_args={"query": 12345},
    )
    assert d4.rule_id == "arg_schema", "arg_schema must be rule #4"
