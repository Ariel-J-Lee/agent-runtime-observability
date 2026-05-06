"""Per-step state ledger persisted as JSONL.

Writes one JSON object per agent step in the order the loop produced
them. Each record carries the step index, the LLM input/output, the
intended tool calls, the policy decisions, the tool results, and any
errors. The ledger is rerunnable: feeding ``state.jsonl[0..k]`` back
into the runtime as prior context produces the same
``state.jsonl[k+1]`` (deterministic given the LLM and tool stubs).

The schema matches ``docs/runtime-model.md`` and the run-artifact layout
documented for the canonical run.

Public interface:

- :class:`StateRecord` — typed record shape (one per agent step)
- :class:`StateLedger` — append-only JSONL writer + replay reader

The writer writes one record per ``append()`` call so a run that
crashes mid-loop leaves a partial-but-honest ledger that can be
inspected without losing the prior step.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional


@dataclass
class StateRecord:
    """One agent-step record on the rerunnable JSONL ledger.

    Fields mirror the schema documented in ``docs/runtime-model.md``.
    Empty lists are valid: a step with no tool calls keeps an empty
    ``intended_tool_calls`` list rather than omitting the field.
    """

    run_id: str
    step_index: int
    llm_input: str = ""
    llm_output: str = ""
    intended_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    policy_decisions: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    # The catalogued failure mode (if any) the agent loop classified for
    # this step; one of the five locked modes from
    # :mod:`src.fail.catalog` or ``None`` when no classified failure
    # occurred. Set by the agent loop on the offending step record so
    # the same value can flow into the ``agent.failure_mode`` span
    # attribute when the trace exporter reads the ledger.
    failure_mode: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for one ledger line."""
        return asdict(self)


class StateLedger:
    """Append-only JSONL writer + replay reader for the agent loop.

    The ledger opens its file lazily on the first ``append()`` and
    closes it on ``close()`` (or on context-manager exit). Each
    ``append`` flushes immediately so a crash mid-loop leaves a
    recoverable partial ledger.

    Args:
        path: Filesystem path where the JSONL file lives. The parent
            directory is created on first append.

    Example:
        >>> ledger = StateLedger("runs/demo/state.jsonl")
        >>> ledger.append(StateRecord(run_id="r1", step_index=0))
        >>> ledger.close()
        >>> records = list(StateLedger.replay("runs/demo/state.jsonl"))
        >>> records[0].step_index
        0
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._file = None  # type: ignore[assignment]
        self._count = 0

    @property
    def count(self) -> int:
        """Number of records written so far."""
        return self._count

    def __enter__(self) -> "StateLedger":
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.close()

    def append(self, record: StateRecord) -> None:
        """Append one record to the ledger; flushes on every write."""
        if self._file is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self.path.open("a", encoding="utf-8")
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()
        self._count += 1

    def close(self) -> None:
        """Close the underlying file if open."""
        if self._file is not None:
            self._file.close()
            self._file = None

    @staticmethod
    def replay(path: str | Path) -> Iterator[StateRecord]:
        """Read a previously-written JSONL ledger as :class:`StateRecord`.

        Empty / whitespace-only lines are skipped. Each non-empty line is
        parsed as JSON and validated against :class:`StateRecord`'s
        constructor; a malformed line raises a :class:`json.JSONDecodeError`
        or :class:`TypeError` (for an unknown field).

        Args:
            path: Filesystem path to ``state.jsonl``.

        Yields:
            One :class:`StateRecord` per non-empty line.
        """
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                yield StateRecord(**payload)


def load_state_jsonl(path: str | Path) -> list[StateRecord]:
    """Convenience: eager replay returning a list."""
    return list(StateLedger.replay(path))
