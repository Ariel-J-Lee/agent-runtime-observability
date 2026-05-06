"""Deterministic stub LLM canonical to ``agent-runtime-observability``.

Provides a deterministic, fixture-driven LLM callable matching the
runtime's ``Callable[[LLMInput], LLMOutput]`` shape. The canonical
demo task at ``tasks/canonical/v1.json`` and the adversarial fixtures
at ``tasks/policy_gates/`` and ``tasks/failure_modes/`` all consume
this stub via the ``canned_llm_tool_calls`` array convention.

Public surface:

- :func:`make_canned_llm` — factory producing the LLM callable
- :class:`CannedLLM` — the callable implementation (testing only)
"""

from src.runtime.stub_llm.canned import CannedLLM, make_canned_llm

__all__ = ["CannedLLM", "make_canned_llm"]
