"""Bounded retry with deterministic exponential backoff.

The retry seam wraps a tool call and emits one ``retry_attempt`` record
per attempt. On exhaustion of ``max_retries`` the wrapper raises
:class:`RetryExhausted`; downstream :mod:`src.fail.catalog` will map
that exception class to ``agent.failure_mode = retry_exhaustion`` (see
``failure_modes.md``).

Backoff schedule per ``docs/runtime-model.md``:

    backoff_ms = min(base * 2^attempt, cap)

Default values mirror the v1 plan: ``base=100``, ``cap=2000``,
``max_retries=3``. A deterministic jitter is applied via the seed so
two reviewers running the same fixture see byte-identical retry
histories. The jitter range is ``±20%`` of the computed backoff.

This slice does NOT actually sleep when called from tests — the
default ``sleep`` callable is :func:`time.sleep`, but tests pass a
no-op so deterministic verification is fast. Production callers leave
the default sleep so the backoff schedule is observed for real.

Public interface:

- :func:`bounded_retry` — decorator factory wrapping any callable
- :class:`RetryExhausted` — raised after the final attempt fails
- :class:`RetryAttemptRecord` — one attempt's structured trace record
- :class:`RetryResult` — the wrapped call's outcome plus the attempt history

The ``transient_failure`` predicate decides which exceptions are
retryable. The default treats every :class:`Exception` subclass as
retryable except :class:`KeyboardInterrupt`, :class:`SystemExit`, and
:class:`MemoryError`. Callers can pass a narrower predicate when only
a subset of exceptions should retry (e.g., only HTTP-shaped failures).
"""

from __future__ import annotations

import functools
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, TypeVar

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_MS = 100
DEFAULT_BACKOFF_CAP_MS = 2000
DEFAULT_JITTER_FRACTION = 0.20

OutcomeLiteral = Literal["success", "transient_failure", "exhausted"]

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when a wrapped call exhausts ``max_retries`` without succeeding.

    Carries the last underlying exception as ``__cause__`` so callers
    can inspect both the exhaustion event and the failure that caused
    it. The agent loop catches this class and maps it to the
    ``retry_exhaustion`` failure-mode catalog entry downstream.
    """


@dataclass(frozen=True)
class RetryAttemptRecord:
    """Structured record for one attempt; one record per ``retry_attempt`` span.

    Field names match ``docs/runtime-model.md`` ``retry_attempt`` span
    attribute set so a downstream :mod:`src.tracing.otel_exporter` can
    emit each record as one span without renaming.
    """

    attempt: int
    outcome: OutcomeLiteral
    backoff_ms: int
    error_class: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RetryResult:
    """The result of a :func:`bounded_retry`-wrapped call.

    Attributes:
        value: The wrapped function's return value (set when
            ``outcome=="success"``).
        attempts: Ordered list of attempt records, including the
            successful one when present.
        outcome: ``"success"`` or ``"exhausted"`` (never
            ``"transient_failure"`` at the top level — that's a
            per-attempt outcome).
    """

    attempts: list[RetryAttemptRecord] = field(default_factory=list)
    outcome: OutcomeLiteral = "success"
    value: Any = None


def _is_retryable_default(exc: BaseException) -> bool:
    """Default predicate: every Exception is retryable except a few hard-fails."""
    if isinstance(exc, (KeyboardInterrupt, SystemExit, MemoryError)):
        return False
    return isinstance(exc, Exception)


def _backoff_ms(
    attempt: int,
    *,
    base_ms: int,
    cap_ms: int,
    seed: int,
    jitter_fraction: float = DEFAULT_JITTER_FRACTION,
) -> int:
    """Return the backoff in milliseconds for ``attempt`` (1-indexed).

    Applies a deterministic ±jitter_fraction jitter using a per-attempt
    PRNG seeded from ``seed`` so reruns produce byte-identical
    histories.
    """
    raw = min(base_ms * (2 ** max(0, attempt - 1)), cap_ms)
    # random.Random accepts only int / float / str / bytes seeds in
    # Python 3.12; hash the (seed, attempt) pair to a stable string so
    # the deterministic-jitter contract holds across Python versions.
    rng = random.Random(f"{seed}-{attempt}")
    delta = rng.uniform(-jitter_fraction, jitter_fraction) * raw
    return max(0, int(raw + delta))


def bounded_retry(
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_ms: int = DEFAULT_BACKOFF_BASE_MS,
    backoff_cap_ms: int = DEFAULT_BACKOFF_CAP_MS,
    seed: int = 0,
    is_retryable: Callable[[BaseException], bool] = _is_retryable_default,
    on_attempt: Optional[Callable[[RetryAttemptRecord], None]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[..., T]], Callable[..., RetryResult]]:
    """Return a decorator that wraps any callable with bounded retry.

    Args:
        max_retries: Hard cap on attempts. Default 3 per v1 plan.
        backoff_base_ms: Backoff base in ms (``base * 2^(attempt-1)``).
        backoff_cap_ms: Backoff ceiling in ms.
        seed: Deterministic jitter seed; reruns produce identical
            backoff schedules.
        is_retryable: Predicate distinguishing retryable from terminal
            exceptions. Default treats every :class:`Exception` as
            retryable except :class:`KeyboardInterrupt`,
            :class:`SystemExit`, and :class:`MemoryError`.
        on_attempt: Optional callback invoked with each
            :class:`RetryAttemptRecord` after the attempt completes.
            The agent loop wires this to the ``span_recorder`` seam so
            every attempt becomes a ``retry_attempt`` span.
        sleep: Sleep function (default :func:`time.sleep`). Tests pass
            a no-op for fast verification.

    Returns:
        A decorator factory that wraps a function and returns a
        :class:`RetryResult`. Note the wrapper's return shape differs
        from the wrapped function's; callers read ``.value`` for the
        successful return.

    Raises (from the wrapper):
        :class:`RetryExhausted` after ``max_retries`` failed attempts.
        Any non-retryable exception propagates immediately.
    """
    if max_retries < 0:
        raise ValueError(f"max_retries must be non-negative; got {max_retries!r}")
    if backoff_base_ms < 0:
        raise ValueError(f"backoff_base_ms must be non-negative; got {backoff_base_ms!r}")
    if backoff_cap_ms < 0:
        raise ValueError(f"backoff_cap_ms must be non-negative; got {backoff_cap_ms!r}")

    def decorator(func: Callable[..., T]) -> Callable[..., RetryResult]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> RetryResult:
            result = RetryResult()
            last_exc: Optional[BaseException] = None
            for attempt in range(1, max_retries + 2):  # 1-indexed; +1 for the initial try
                try:
                    value = func(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001 — re-raise non-retryable below
                    last_exc = exc
                    if not is_retryable(exc):
                        raise
                    if attempt > max_retries:
                        record = RetryAttemptRecord(
                            attempt=attempt,
                            outcome="exhausted",
                            backoff_ms=0,
                            error_class=type(exc).__name__,
                            error_message=str(exc),
                        )
                        result.attempts.append(record)
                        if on_attempt is not None:
                            on_attempt(record)
                        result.outcome = "exhausted"
                        raise RetryExhausted(
                            f"max_retries={max_retries} exhausted; "
                            f"last error: {type(exc).__name__}: {exc}"
                        ) from exc
                    delay_ms = _backoff_ms(
                        attempt,
                        base_ms=backoff_base_ms,
                        cap_ms=backoff_cap_ms,
                        seed=seed,
                    )
                    record = RetryAttemptRecord(
                        attempt=attempt,
                        outcome="transient_failure",
                        backoff_ms=delay_ms,
                        error_class=type(exc).__name__,
                        error_message=str(exc),
                    )
                    result.attempts.append(record)
                    if on_attempt is not None:
                        on_attempt(record)
                    if delay_ms > 0:
                        sleep(delay_ms / 1000.0)
                    continue
                else:
                    record = RetryAttemptRecord(
                        attempt=attempt,
                        outcome="success",
                        backoff_ms=0,
                    )
                    result.attempts.append(record)
                    if on_attempt is not None:
                        on_attempt(record)
                    result.outcome = "success"
                    result.value = value
                    return result

            # Defensive: the loop always returns or raises above.
            raise RuntimeError(
                "bounded_retry: control fell out of the retry loop without "
                "returning or raising; this is a bug"
            )

        return wrapper

    return decorator
