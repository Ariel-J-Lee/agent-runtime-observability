"""Single-agent governed runtime: orchestrator, policy seam, retry, state ledger.

This package ships the runtime skeleton documented in
``docs/runtime-model.md``: the step loop, the policy-check seam, the
bounded-retry layer, and the rerunnable JSONL state ledger. The trace
exporter, real policy rule set, real tool surface, fixture corpus, and
captured runs ship in subsequent slices.

Public exports:

- :class:`Agent` — the orchestrator
- :class:`AgentResult`, :class:`LLMInput`, :class:`LLMOutput`,
  :class:`ToolCall` — agent loop value types
- :class:`PolicySpec`, :class:`PolicyChecker`, :class:`PermissivePolicyChecker`,
  :class:`PolicyDecision` — the policy seam
- :func:`bounded_retry`, :class:`RetryExhausted`, :class:`RetryResult`,
  :class:`RetryAttemptRecord` — the retry seam
- :class:`StateLedger`, :class:`StateRecord` — the state ledger

The trace seam is a callable parameter on :class:`Agent`; this package
does not export an exporter class. Downstream slices wire a real
exporter into the same callable interface.
"""

from src.runtime.agent import (
    Agent,
    AgentResult,
    LLMInput,
    LLMOutput,
    ToolCall,
)
from src.runtime.policy import (
    PermissivePolicyChecker,
    PolicyChecker,
    PolicyDecision,
    PolicySpec,
)
from src.runtime.retry import (
    RetryAttemptRecord,
    RetryExhausted,
    RetryResult,
    bounded_retry,
)
from src.runtime.state import StateLedger, StateRecord

__all__ = [
    "Agent",
    "AgentResult",
    "LLMInput",
    "LLMOutput",
    "PermissivePolicyChecker",
    "PolicyChecker",
    "PolicyDecision",
    "PolicySpec",
    "RetryAttemptRecord",
    "RetryExhausted",
    "RetryResult",
    "StateLedger",
    "StateRecord",
    "ToolCall",
    "bounded_retry",
]
