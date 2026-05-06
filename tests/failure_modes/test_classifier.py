"""Pure-mapping tests for :func:`src.fail.classify`.

The classifier is a pure function: ``(exception_class, span_attrs,
retry_outcome) → Optional[FailureMode]``. These tests fix the mapping
contract independent of the agent-loop integration. Combined with
the per-mode integration tests in this directory, they lock the F1–F5
behavior end-to-end.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.fail import (
    CATALOGUED_UNHANDLED,
    CYCLE_DETECTION,
    FAILURE_MODES,
    RETRY_EXHAUSTION,
    SCHEMA_MISMATCH,
    TOOL_CALL_FAILURE,
    classify,
    describe,
    is_canonical,
)


def test_no_signal_returns_none():
    assert classify() is None
    assert classify(span_attrs={}) is None
    assert classify(span_attrs={"agent.policy.decision": "allow"}) is None


def test_schema_mismatch_from_arg_schema_deny():
    attrs = {"agent.policy.decision": "deny", "agent.policy.rule_id": "arg_schema"}
    assert classify(span_attrs=attrs) == SCHEMA_MISMATCH


def test_cycle_detection_from_cycle_detection_deny():
    attrs = {"agent.policy.decision": "deny", "agent.policy.rule_id": "cycle_detection"}
    assert classify(span_attrs=attrs) == CYCLE_DETECTION


def test_url_allowlist_deny_does_not_classify():
    """Per the catalog: only arg_schema and cycle_detection denies map to a failure mode.

    A url_allowlist or sandbox_path deny is a policy-side denial that
    isn't part of the failure-mode catalog; the classifier returns
    ``None`` so the agent's policy_decisions record carries the deny
    without setting ``failure_mode``.
    """
    attrs = {"agent.policy.decision": "deny", "agent.policy.rule_id": "url_allowlist"}
    assert classify(span_attrs=attrs) is None
    attrs2 = {"agent.policy.decision": "deny", "agent.policy.rule_id": "sandbox_path"}
    assert classify(span_attrs=attrs2) is None


def test_retry_exhaustion_from_exception_class():
    assert classify(exception_class="RetryExhausted") == RETRY_EXHAUSTION


def test_retry_exhaustion_from_retry_outcome():
    assert classify(retry_outcome="exhausted") == RETRY_EXHAUSTION


def test_tool_call_failure_from_transient_failure():
    assert classify(retry_outcome="transient_failure") == TOOL_CALL_FAILURE


def test_catalogued_unhandled_from_arbitrary_exception():
    assert classify(exception_class="ValueError") == CATALOGUED_UNHANDLED
    assert classify(exception_class="MemoryError") == CATALOGUED_UNHANDLED
    assert classify(exception_class="_F5UnhandledError") == CATALOGUED_UNHANDLED


def test_policy_signal_takes_precedence_over_exception():
    """A policy-side deny is the proximate cause; classify on it first."""
    attrs = {"agent.policy.decision": "deny", "agent.policy.rule_id": "arg_schema"}
    assert (
        classify(exception_class="ValueError", span_attrs=attrs) == SCHEMA_MISMATCH
    )


def test_retry_signal_takes_precedence_over_generic_exception():
    """RetryExhausted is more specific than the catch-all."""
    assert (
        classify(exception_class="RetryExhausted", retry_outcome="exhausted")
        == RETRY_EXHAUSTION
    )


def test_canonical_set_size_is_five():
    assert len(FAILURE_MODES) == 5


def test_canonical_set_contents():
    assert set(FAILURE_MODES) == {
        TOOL_CALL_FAILURE,
        RETRY_EXHAUSTION,
        SCHEMA_MISMATCH,
        CYCLE_DETECTION,
        CATALOGUED_UNHANDLED,
    }


def test_is_canonical_recognizes_locked_modes():
    for mode in FAILURE_MODES:
        assert is_canonical(mode)
    assert not is_canonical("unknown_mode")


def test_describe_returns_external_engineering_language():
    """No internal control-plane vocabulary in mode descriptions."""
    forbidden = ("Tier ", "evidence ladder", "captured-evidence", "PM/QA")
    for mode in FAILURE_MODES:
        d = describe(mode)
        for word in forbidden:
            assert word not in d, f"description for {mode!r} contains {word!r}"
