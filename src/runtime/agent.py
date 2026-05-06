"""Single-agent governed runtime entry point.

The :class:`Agent` drives the step loop documented in
``docs/runtime-model.md``. Per step:

1. Call the LLM with the prior state to produce an :class:`LLMOutput`
   carrying the next intended tool calls (or a terminal answer).
2. For each intended tool call: invoke the policy checker; on
   ``allow``, execute the tool through the bounded-retry layer; on
   ``deny``, record the deny reason and skip execution.
3. Append a :class:`StateRecord` to the JSONL ledger.
4. Emit ``agent_step``, ``llm_call``, ``tool_call``, ``policy_check``,
   and ``retry_attempt`` events through the ``span_recorder`` seam so
   the downstream T-TRACE slice can plug in the OTel-shaped JSON
   exporter without changing the agent surface.
5. When the LLM emits ``final_answer`` (or the loop budget is reached),
   stop and return :class:`AgentResult`.

The runtime is **single-agent only at v1** (per ``docs/runtime-model.md``
and the canonical first-runnable-proof plan). Multi-agent coordination
is an explicit non-goal at this scope.

Public interface:

- :class:`LLMOutput` — what an LLM callable returns each step
- :class:`ToolCall` — one intended tool invocation
- :class:`AgentResult` — the run's terminal report
- :class:`Agent` — the orchestrator

The seams the agent loop calls through:

- ``llm: Callable[[LLMInput], LLMOutput]`` — any deterministic stub or
  live-LLM adapter that satisfies the shape
- ``tool_registry: Mapping[str, Callable[..., Any]]`` — string tool
  name → invokable
- ``policy_checker: PolicyChecker`` — the policy seam
- ``state_ledger: StateLedger`` — the JSONL writer (or None for in-
  memory only)
- ``span_recorder: Callable[[str, Mapping[str, Any]], None]`` — the
  trace seam; default is a no-op so this packet does not pull in any
  trace exporter (T-TRACE adds the OTLP-JSON exporter later)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Mapping, Optional

from src.runtime.policy import (
    PermissivePolicyChecker,
    PolicyChecker,
    PolicyDecision,
)
from src.runtime.retry import (
    RetryAttemptRecord,
    RetryExhausted,
    RetryResult,
    bounded_retry,
)
from src.runtime.state import StateLedger, StateRecord

DEFAULT_MAX_ITERATIONS = 10
TerminalReasonLiteral = Literal[
    "final_answer",
    "loop_budget_exhausted",
    "retry_exhausted",
    "policy_denial_terminal",
]

SpanRecorder = Callable[[str, Mapping[str, Any]], None]


def _no_op_recorder(span_class: str, attrs: Mapping[str, Any]) -> None:
    """Default ``span_recorder``: discard every span event.

    The downstream T-TRACE slice replaces this with an OTLP-JSON
    writer. Keeping the default a no-op means this packet does not
    introduce a trace dependency.
    """
    return None


@dataclass(frozen=True)
class ToolCall:
    """One intended tool invocation produced by the LLM."""

    tool: str
    args: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMOutput:
    """The structured output the LLM emits each step.

    An LLM callable returns either a terminal ``final_answer`` (the
    loop stops and the agent reports success) or a non-empty list of
    intended tool calls (the loop executes them through the policy +
    retry seams and continues).
    """

    final_answer: Optional[str] = None
    intended_tool_calls: tuple[ToolCall, ...] = ()
    raw_text: str = ""

    def is_terminal(self) -> bool:
        return self.final_answer is not None


@dataclass(frozen=True)
class LLMInput:
    """The structured input the agent passes to the LLM each step."""

    run_id: str
    step_index: int
    user_question: str
    prior_records: tuple[StateRecord, ...] = ()


@dataclass
class AgentResult:
    """The terminal report from one agent run.

    Attributes:
        run_id: Identifier for this run.
        final_answer: The LLM's terminal answer when
            ``terminal_reason == "final_answer"``; otherwise empty.
        terminal_reason: One of the documented terminal reasons.
        step_count: Number of agent steps executed.
        records: All :class:`StateRecord` instances produced during
            the run, in step order.
    """

    run_id: str
    final_answer: str = ""
    terminal_reason: TerminalReasonLiteral = "final_answer"
    step_count: int = 0
    records: list[StateRecord] = field(default_factory=list)


class Agent:
    """Single-agent governed runtime.

    Construction does no work; ``run()`` drives the loop. The agent
    holds the seams (LLM, tools, policy, state, trace) by composition;
    none of those seams are constructed inside :class:`Agent`.

    Args:
        llm: The LLM callable. Receives an :class:`LLMInput` and
            returns an :class:`LLMOutput`.
        tool_registry: Mapping of tool name → invokable. Tools accept
            ``**kwargs`` matching their declared input schema and
            return any JSON-serializable result.
        policy_checker: A :class:`PolicyChecker`. Defaults to a
            :class:`PermissivePolicyChecker` (allow-everything) so the
            seam is exercised even when no policy spec is supplied.
        state_ledger: Optional :class:`StateLedger`. When ``None``, the
            agent runs in-memory-only and does not persist state.
        span_recorder: Trace seam callable. Default no-op.
        max_iterations: Hard cap on agent steps. Default 10.
        max_retries: Bounded-retry hard cap per tool call.
        backoff_base_ms / backoff_cap_ms: Backoff parameters; see
            :func:`src.runtime.retry.bounded_retry`.
        seed: Deterministic seed propagated into the retry layer.
    """

    def __init__(
        self,
        *,
        llm: Callable[[LLMInput], LLMOutput],
        tool_registry: Mapping[str, Callable[..., Any]],
        policy_checker: Optional[PolicyChecker] = None,
        state_ledger: Optional[StateLedger] = None,
        span_recorder: SpanRecorder = _no_op_recorder,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_retries: int = 3,
        backoff_base_ms: int = 100,
        backoff_cap_ms: int = 2000,
        seed: int = 0,
    ) -> None:
        if max_iterations < 1:
            raise ValueError(
                f"max_iterations must be positive; got {max_iterations!r}"
            )
        self.llm = llm
        self.tool_registry = dict(tool_registry)
        self.policy_checker = policy_checker or PermissivePolicyChecker()
        self.state_ledger = state_ledger
        self.span_recorder = span_recorder
        self.max_iterations = max_iterations
        self.max_retries = max_retries
        self.backoff_base_ms = backoff_base_ms
        self.backoff_cap_ms = backoff_cap_ms
        self.seed = seed

    def run(
        self,
        user_question: str,
        *,
        run_id: Optional[str] = None,
    ) -> AgentResult:
        """Execute the agent loop end-to-end and return :class:`AgentResult`."""
        run_id = run_id or uuid.uuid4().hex
        records: list[StateRecord] = []

        result = AgentResult(run_id=run_id)
        terminal_reason: Optional[TerminalReasonLiteral] = None

        for step_index in range(self.max_iterations):
            # Loop-budget pre-check (per docs/runtime-model.md): the agent
            # asks the policy seam whether to continue before issuing the
            # next LLM call.
            budget = self.policy_checker.check_loop_budget(
                iterations=step_index, tokens=0,
            )
            if budget.decision == "deny":
                self.span_recorder(
                    "policy_check",
                    self._policy_attrs(run_id, step_index, budget, tool_name=None),
                )
                terminal_reason = "loop_budget_exhausted"
                break

            self.span_recorder(
                "agent_step",
                {"agent.run_id": run_id, "agent.step_index": step_index},
            )

            llm_input = LLMInput(
                run_id=run_id,
                step_index=step_index,
                user_question=user_question,
                prior_records=tuple(records),
            )
            self.span_recorder(
                "llm_call",
                {
                    "agent.run_id": run_id,
                    "agent.step_index": step_index,
                    "agent.llm.execution_path": "stub",
                },
            )
            llm_output = self.llm(llm_input)

            record = StateRecord(
                run_id=run_id,
                step_index=step_index,
                llm_input=llm_input.user_question,
                llm_output=llm_output.raw_text or (llm_output.final_answer or ""),
                intended_tool_calls=[
                    {"tool": tc.tool, "args": dict(tc.args)}
                    for tc in llm_output.intended_tool_calls
                ],
            )

            if llm_output.is_terminal():
                terminal_reason = "final_answer"
                result.final_answer = llm_output.final_answer or ""
                self._persist(record, records)
                break

            # Per intended tool call: policy check, then (on allow) execute
            # through the bounded-retry layer.
            terminal_due_to_retry = False
            for tc in llm_output.intended_tool_calls:
                decision = self.policy_checker.check(
                    tool_name=tc.tool,
                    tool_args=tc.args,
                )
                self.span_recorder(
                    "policy_check",
                    self._policy_attrs(run_id, step_index, decision, tool_name=tc.tool),
                )
                record.policy_decisions.append(
                    {
                        "tool": tc.tool,
                        "decision": decision.decision,
                        "rule_id": decision.rule_id,
                    }
                )
                if decision.decision != "allow":
                    record.tool_results.append(
                        {"tool": tc.tool, "ok": False, "skipped_by_policy": True}
                    )
                    continue
                tool_fn = self.tool_registry.get(tc.tool)
                if tool_fn is None:
                    # Catch unregistered-tool case at the runtime boundary
                    # (the canonical PG4 fixture exercises this through the
                    # policy spec; this defensive branch handles a tool the
                    # registry simply doesn't contain).
                    record.errors.append(
                        {"tool": tc.tool, "error": "tool_not_registered"}
                    )
                    record.tool_results.append(
                        {"tool": tc.tool, "ok": False, "error": "tool_not_registered"}
                    )
                    continue

                self.span_recorder(
                    "tool_call",
                    {
                        "agent.run_id": run_id,
                        "agent.step_index": step_index,
                        "agent.tool_name": tc.tool,
                    },
                )

                def _on_attempt(attempt_record: RetryAttemptRecord) -> None:
                    self.span_recorder(
                        "retry_attempt",
                        {
                            "agent.run_id": run_id,
                            "agent.step_index": step_index,
                            "agent.retry.attempt": attempt_record.attempt,
                            "agent.retry.outcome": attempt_record.outcome,
                            "agent.retry.backoff_ms": attempt_record.backoff_ms,
                        },
                    )

                wrapped = bounded_retry(
                    max_retries=self.max_retries,
                    backoff_base_ms=self.backoff_base_ms,
                    backoff_cap_ms=self.backoff_cap_ms,
                    seed=self.seed,
                    on_attempt=_on_attempt,
                    sleep=lambda _s: None,  # in-loop sleeps disabled at v1
                )(tool_fn)

                try:
                    rr: RetryResult = wrapped(**dict(tc.args))
                except RetryExhausted as exc:
                    record.errors.append(
                        {
                            "tool": tc.tool,
                            "error": "retry_exhausted",
                            "cause": str(exc.__cause__) if exc.__cause__ else "",
                        }
                    )
                    record.tool_results.append(
                        {"tool": tc.tool, "ok": False, "error": "retry_exhausted"}
                    )
                    terminal_due_to_retry = True
                    break

                record.tool_results.append(
                    {"tool": tc.tool, "ok": True, "result": rr.value}
                )

            self._persist(record, records)

            if terminal_due_to_retry:
                terminal_reason = "retry_exhausted"
                break

        else:
            # Loop ran all the way through max_iterations without breaking
            # — that's the loop-budget terminal reason.
            terminal_reason = "loop_budget_exhausted"

        result.records = records
        result.step_count = len(records)
        result.terminal_reason = terminal_reason or "final_answer"
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _persist(self, record: StateRecord, records: list[StateRecord]) -> None:
        """Append to the in-memory list and (when present) the disk ledger."""
        records.append(record)
        if self.state_ledger is not None:
            self.state_ledger.append(record)

    def _policy_attrs(
        self,
        run_id: str,
        step_index: int,
        decision: PolicyDecision,
        *,
        tool_name: Optional[str],
    ) -> dict[str, Any]:
        """Build the ``policy_check`` span attribute set."""
        attrs: dict[str, Any] = {
            "agent.run_id": run_id,
            "agent.step_index": step_index,
            "agent.policy.decision": decision.decision,
            "policy.version": self.policy_checker.spec.version,
        }
        if decision.rule_id is not None:
            attrs["agent.policy.rule_id"] = decision.rule_id
        if tool_name is not None:
            attrs["agent.tool_name"] = tool_name
        attrs.update(decision.metadata)
        return attrs
