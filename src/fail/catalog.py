"""Failure-mode classifier for the runtime catalog.

The agent runtime classifies every observed failure into one of five
canonical modes documented in ``failure_modes.md`` and in
``docs/failure-modes.md``. The classifier is a pure mapping from
``(exception_class, span_attrs)`` to a :class:`FailureMode`; it has
no side effects and no I/O.

The five locked modes:

- :data:`TOOL_CALL_FAILURE` — a tool execution returned an error or
  raised a transient exception that is still within the retry budget.
  The runtime records the failed attempt without terminating the run.
- :data:`RETRY_EXHAUSTION` — a tool's bounded-retry layer exhausted
  its budget; :class:`src.runtime.RetryExhausted` was raised.
- :data:`SCHEMA_MISMATCH` — a tool call's arguments failed the input
  JSON-schema; the policy layer denied with ``rule_id="arg_schema"``
  before the tool ran.
- :data:`CYCLE_DETECTION` — the agent observed the same
  ``(tool, normalized_args)`` pair more than
  ``policy.cycle_detection.max_repeats`` times; the policy layer
  denied with ``rule_id="cycle_detection"``.
- :data:`CATALOGUED_UNHANDLED` — a tool raised a non-retryable,
  non-classifiable exception. This is the catch-all that ensures
  every observed failure has a documented entry.

Public surface:

- :class:`FailureMode` — the typed string-enum-shape constant set
- :func:`classify` — pure mapping ``(exception_class, span_attrs) → FailureMode | None``
- :data:`FAILURE_MODES` — the canonical ordered list of all five modes
"""

from __future__ import annotations

from typing import Any, Iterable, Literal, Mapping, Optional

# ---------------------------------------------------------------------------
# Canonical mode names (locked by PACKET-046 §5)
# ---------------------------------------------------------------------------

TOOL_CALL_FAILURE: Literal["tool_call_failure"] = "tool_call_failure"
RETRY_EXHAUSTION: Literal["retry_exhaustion"] = "retry_exhaustion"
SCHEMA_MISMATCH: Literal["schema_mismatch"] = "schema_mismatch"
CYCLE_DETECTION: Literal["cycle_detection"] = "cycle_detection"
CATALOGUED_UNHANDLED: Literal["catalogued_unhandled"] = "catalogued_unhandled"

FailureMode = Literal[
    "tool_call_failure",
    "retry_exhaustion",
    "schema_mismatch",
    "cycle_detection",
    "catalogued_unhandled",
]

FAILURE_MODES: tuple[FailureMode, ...] = (
    TOOL_CALL_FAILURE,
    RETRY_EXHAUSTION,
    SCHEMA_MISMATCH,
    CYCLE_DETECTION,
    CATALOGUED_UNHANDLED,
)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def classify(
    *,
    exception_class: Optional[str] = None,
    span_attrs: Optional[Mapping[str, Any]] = None,
    retry_outcome: Optional[str] = None,
) -> Optional[FailureMode]:
    """Map a runtime observation to a :class:`FailureMode`.

    The classifier evaluates inputs in this order:

    1. **Schema mismatch** — when ``span_attrs`` carries a
       ``policy_check`` deny with ``agent.policy.rule_id="arg_schema"``,
       return :data:`SCHEMA_MISMATCH`.
    2. **Cycle detection** — when ``span_attrs`` carries a
       ``policy_check`` deny with ``agent.policy.rule_id="cycle_detection"``,
       return :data:`CYCLE_DETECTION`.
    3. **Retry exhaustion** — when ``exception_class == "RetryExhausted"``
       OR when ``retry_outcome == "exhausted"``, return
       :data:`RETRY_EXHAUSTION`.
    4. **Tool-call failure** — when ``retry_outcome == "transient_failure"``
       (a single retry attempt failed but the budget hasn't been exhausted),
       return :data:`TOOL_CALL_FAILURE`.
    5. **Catalogued unhandled** — when an ``exception_class`` is
       supplied that doesn't match any of the above (any non-empty
       string that isn't ``RetryExhausted``), return
       :data:`CATALOGUED_UNHANDLED`.

    Returns ``None`` when no classification applies (no exception, no
    retry signal, and no policy deny in the supplied span attrs).

    Args:
        exception_class: The Python class name of the exception that
            escaped the runtime (e.g., ``"RetryExhausted"``,
            ``"ValueError"``). ``None`` when no exception was raised.
        span_attrs: The attribute dict of the most recent
            ``policy_check`` span (or any span carrying
            ``agent.policy.rule_id``). ``None`` when no policy event
            is being classified.
        retry_outcome: The outcome of the most recent
            :class:`src.runtime.RetryAttemptRecord`. One of
            ``"success"``, ``"transient_failure"``, ``"exhausted"``,
            or ``None``.

    Returns:
        The classified :class:`FailureMode`, or ``None`` if none of
        the five modes apply.
    """
    # 1. Policy-side classifications (precedence over exceptions because
    #    a policy deny is the proximate cause; the exception class would
    #    be derivative).
    if span_attrs is not None:
        decision = span_attrs.get("agent.policy.decision")
        rule_id = span_attrs.get("agent.policy.rule_id")
        if decision == "deny":
            if rule_id == "arg_schema":
                return SCHEMA_MISMATCH
            if rule_id == "cycle_detection":
                return CYCLE_DETECTION

    # 2. Retry-side classifications (RetryExhausted is the most specific
    #    exception class we know about, but a caller could also signal
    #    via retry_outcome).
    if exception_class == "RetryExhausted":
        return RETRY_EXHAUSTION
    if retry_outcome == "exhausted":
        return RETRY_EXHAUSTION
    if retry_outcome == "transient_failure":
        return TOOL_CALL_FAILURE

    # 3. Catch-all: any other exception class is catalogued_unhandled.
    if exception_class:
        return CATALOGUED_UNHANDLED

    return None


def is_canonical(mode: str) -> bool:
    """Return ``True`` if ``mode`` is one of the five canonical modes."""
    return mode in FAILURE_MODES


def describe(mode: FailureMode) -> str:
    """Return a one-line external-engineering-language description of a mode."""
    return _DESCRIPTIONS[mode]


_DESCRIPTIONS: dict[FailureMode, str] = {
    TOOL_CALL_FAILURE: (
        "A tool call failed transiently and was recorded; "
        "the bounded-retry layer is still within budget."
    ),
    RETRY_EXHAUSTION: (
        "A tool call's bounded-retry budget was exhausted; the run "
        "terminates with terminal_reason=retry_exhausted."
    ),
    SCHEMA_MISMATCH: (
        "A tool call's arguments failed the input JSON-schema; the "
        "policy layer denied with rule_id=arg_schema before the tool ran."
    ),
    CYCLE_DETECTION: (
        "The agent observed the same (tool, normalized_args) pair more "
        "than policy.cycle_detection.max_repeats times; the policy "
        "layer denied with rule_id=cycle_detection."
    ),
    CATALOGUED_UNHANDLED: (
        "A tool raised a non-retryable, non-classifiable exception; "
        "the catch-all entry guarantees every observed failure has "
        "a documented mode."
    ),
}
