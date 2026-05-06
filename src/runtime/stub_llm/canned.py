"""Canonical deterministic stub LLM keyed by ``canned_llm_tool_calls``.

The fixture convention all canonical and adversarial fixtures use:

- ``canned_llm_tool_calls`` is a list of step entries. Each entry has
  shape ``{"step_index": int, "tool": str, "args": dict, "tokens"?: int}``
  to drive a tool call, OR ``{"step_index": int, "final_answer": str}``
  to terminate the run with an explicit answer.
- The LLM emits one entry per step, looked up by ``LLMInput.step_index``.
- When the canned list is exhausted (``step_index`` not present in the
  table), the LLM emits the optional ``default_final_answer`` (when
  the factory was constructed with one) or a placeholder terminal
  string indicating exhaustion.

This stub graduates the test-only ``make_canned_llm`` previously held
under ``tests/policy_gates/_stubs.py``: same input contract, same
``LLMOutput`` shape, plus first-class ``final_answer`` step entries
and an explicit exhaustion answer parameter.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from src.runtime.agent import LLMInput, LLMOutput, ToolCall

EXHAUSTED_DEFAULT = "(stub LLM exhausted: no canned step for this index)"


class CannedLLM:
    """Deterministic stub LLM callable.

    Args:
        canned_tool_calls: Sequence of step entries. Each entry must
            carry ``step_index`` (int) plus either ``tool`` + ``args``
            (a tool-call step) or ``final_answer`` (a terminal step).
        default_final_answer: Optional terminal answer emitted when
            ``LLMInput.step_index`` is not in the canned table. When
            ``None``, exhaustion emits :data:`EXHAUSTED_DEFAULT`.
    """

    def __init__(
        self,
        canned_tool_calls: Sequence[Mapping[str, Any]],
        *,
        default_final_answer: Optional[str] = None,
    ) -> None:
        self._by_step: dict[int, Mapping[str, Any]] = {
            int(entry["step_index"]): entry for entry in canned_tool_calls
        }
        self._default_final_answer = default_final_answer

    def __call__(self, inp: LLMInput) -> LLMOutput:
        entry = self._by_step.get(int(inp.step_index))
        if entry is None:
            return LLMOutput(
                final_answer=(
                    self._default_final_answer
                    if self._default_final_answer is not None
                    else EXHAUSTED_DEFAULT
                ),
                raw_text="exhausted",
            )

        if "final_answer" in entry:
            return LLMOutput(
                final_answer=str(entry["final_answer"]),
                raw_text=str(entry),
            )

        tool_call = ToolCall(
            tool=str(entry["tool"]),
            args=dict(entry.get("args") or {}),
        )
        return LLMOutput(intended_tool_calls=(tool_call,), raw_text=str(entry))


def make_canned_llm(
    canned_tool_calls: Sequence[Mapping[str, Any]],
    *,
    default_final_answer: Optional[str] = None,
) -> Callable[[LLMInput], LLMOutput]:
    """Return a deterministic LLM callable bound to ``canned_tool_calls``.

    The returned callable matches the runtime's
    ``Callable[[LLMInput], LLMOutput]`` shape so it can be passed
    directly as ``Agent(llm=...)``.
    """
    return CannedLLM(
        canned_tool_calls,
        default_final_answer=default_final_answer,
    )


__all__ = ["CannedLLM", "EXHAUSTED_DEFAULT", "make_canned_llm"]
