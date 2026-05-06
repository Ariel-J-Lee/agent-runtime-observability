"""Shared fixtures + helpers for the failure-mode suite.

Mirrors the policy-gate suite's conftest: session-scoped
:class:`PolicySpec` from ``policy/v1.yaml``; per-test ``recorded_spans``
factory; ``load_fixture`` / ``run_fixture`` helpers; per-mode universal
invariant assertions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import (
    Agent,
    AgentResult,
    PolicyChecker,
    PolicySpec,
    StateLedger,
)
from tests.failure_modes._stubs import (
    STUB_TOOL_SCHEMAS,
    build_tool_registry,
    make_canned_llm,
)

_POLICY_YAML = _REPO_ROOT / "policy" / "v1.yaml"
_FIXTURE_DIR = _REPO_ROOT / "tasks" / "failure_modes"


def load_fixture(name: str) -> dict[str, Any]:
    """Load ``tasks/failure_modes/<name>.json`` as a dict."""
    return json.loads((_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def policy_spec() -> PolicySpec:
    return PolicySpec.from_yaml_path(_POLICY_YAML)


@pytest.fixture
def recorded_spans():
    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class: str, attrs: Mapping[str, Any]) -> None:
        spans.append((span_class, dict(attrs)))

    return spans, _recorder


def build_agent_for(
    fixture: Mapping[str, Any],
    *,
    policy_spec_obj: PolicySpec,
    span_recorder,
    state_ledger: StateLedger | None = None,
    max_iterations: int | None = None,
    max_retries: int = 3,
) -> Agent:
    """Build an :class:`Agent` wired with the failure-mode stub registry."""
    tool_registry = build_tool_registry(fixture.get("stub_behavior"))
    checker = PolicyChecker(
        policy_spec_obj,
        tool_schemas=STUB_TOOL_SCHEMAS,
    )
    if max_iterations is None:
        max_iterations = int(policy_spec_obj.get("loop_budget.max_iterations", 10))

    return Agent(
        llm=make_canned_llm(fixture["canned_llm_tool_calls"]),
        tool_registry=tool_registry,
        policy_checker=checker,
        state_ledger=state_ledger,
        span_recorder=span_recorder,
        max_iterations=max_iterations,
        max_retries=max_retries,
    )


def run_fixture(
    fixture_name: str,
    *,
    policy_spec_obj: PolicySpec,
    max_retries: int = 3,
) -> tuple[dict[str, Any], AgentResult, list[tuple[str, dict[str, Any]]]]:
    """End-to-end: load fixture, build agent, run, return ``(fixture, result, spans)``."""
    fixture = load_fixture(fixture_name)
    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class: str, attrs: Mapping[str, Any]) -> None:
        spans.append((span_class, dict(attrs)))

    agent = build_agent_for(
        fixture,
        policy_spec_obj=policy_spec_obj,
        span_recorder=_recorder,
        max_retries=max_retries,
    )
    result = agent.run(fixture["question"])
    return fixture, result, spans


def find_failure_mode_span(spans: list[tuple[str, dict[str, Any]]]) -> dict[str, Any] | None:
    """Locate the follow-up ``agent_step`` span that carries ``agent.failure_mode``.

    The agent emits a follow-up ``agent_step`` event with the
    ``agent.failure_mode`` attribute when ``record.failure_mode`` is
    set on a step. The trace seam plugs into this so T-TRACE later
    folds the attribute into the captured trace.
    """
    for span_class, attrs in spans:
        if span_class == "agent_step" and "agent.failure_mode" in attrs:
            return attrs
    return None
