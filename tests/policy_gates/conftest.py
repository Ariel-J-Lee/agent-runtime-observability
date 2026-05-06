"""Shared fixtures + assertion helpers for the policy-gate suite.

Provides:

- The ``policy_spec`` fixture: a single :class:`PolicySpec` loaded from
  ``policy/v1.yaml`` once per test session.
- The ``recorded_spans`` factory: a list-capturing ``span_recorder``
  callable that the agent's seam writes into.
- :func:`load_fixture`: read a fixture JSON file from
  ``tasks/policy_gates/<name>.json``.
- :func:`build_agent_for`: construct a fully wired :class:`Agent` for a
  given fixture, plumbing the canned LLM, the stub tool registry, the
  stub tool schemas, and the per-fixture sandbox-root setup.
- :func:`run_fixture`: end-to-end: build the agent, run it, return
  ``(agent_result, recorded_spans)``.
- :func:`assert_universal_invariants`: the three universal assertions
  documented in the load-bearing implementation plan §4.4 — exactly one
  ``deny`` ``policy_check`` span; every ``policy_check`` carries
  ``policy.version``; the deny's ``agent.step_index`` matches the
  ledger's record index for that step.

Tests under :mod:`tests.policy_gates.test_pg<N>` import these helpers
and add per-scenario assertions on top.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

# Allow tests to run without an editable install: include the repo root
# so ``src.runtime`` and ``tests.policy_gates._stubs`` resolve.
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
from tests.policy_gates._stubs import (
    STUB_TOOL_REGISTRY,
    STUB_TOOL_SCHEMAS,
    make_canned_llm,
)

_POLICY_YAML = _REPO_ROOT / "policy" / "v1.yaml"
_FIXTURE_DIR = _REPO_ROOT / "tasks" / "policy_gates"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_fixture(name: str) -> dict[str, Any]:
    """Load ``tasks/policy_gates/<name>.json`` as a dict."""
    path = _FIXTURE_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def policy_spec() -> PolicySpec:
    """Session-scoped :class:`PolicySpec` loaded from ``policy/v1.yaml``."""
    return PolicySpec.from_yaml_path(_POLICY_YAML)


@pytest.fixture
def recorded_spans():
    """A fresh ``[(span_class, attrs_dict), ...]`` list per test.

    Returns a tuple ``(spans_list, recorder_callable)``: the recorder
    can be passed to ``Agent(span_recorder=recorder)`` and the test
    inspects ``spans_list`` after the run.
    """
    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class: str, attrs: Mapping[str, Any]) -> None:
        spans.append((span_class, dict(attrs)))

    return spans, _recorder


# ---------------------------------------------------------------------------
# Agent wiring
# ---------------------------------------------------------------------------


def _resolve_sandbox_root(fixture: Mapping[str, Any], tmp_path: Path) -> Path | None:
    """Materialize the sandbox dir for fixtures that need it.

    Per the policy YAML's ``sandbox.path_template = "${TMPDIR:-/tmp}/
    agent-runtime-observability/<run-id>/sandbox"``, the test creates
    a concrete sandbox dir under ``tmp_path`` and points the
    ``PolicyChecker`` at it. The fixture's trigger paths live outside
    this dir so the deny event fires.
    """
    if fixture.get("sandbox_root_setup") != "default":
        return None
    sandbox = tmp_path / "agent-runtime-observability" / "test-run" / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    return sandbox.resolve()


def build_agent_for(
    fixture: Mapping[str, Any],
    *,
    policy_spec_obj: PolicySpec,
    tmp_path: Path,
    span_recorder,
    state_ledger: StateLedger | None = None,
    max_iterations: int | None = None,
) -> Agent:
    """Construct a fully wired :class:`Agent` for the given fixture.

    Args:
        fixture: The loaded fixture dict.
        policy_spec_obj: The session-scoped :class:`PolicySpec`.
        tmp_path: pytest's ``tmp_path`` for sandbox-dir setup.
        span_recorder: A list-capturing recorder (see
            :func:`recorded_spans`).
        state_ledger: Optional ledger; tests that don't inspect the
            ledger leave this ``None``.
        max_iterations: Optional override; defaults to the policy
            spec's ``loop_budget.max_iterations``.

    Returns:
        A constructed :class:`Agent` ready to ``run(question)``.
    """
    sandbox_root = _resolve_sandbox_root(fixture, tmp_path)
    checker = PolicyChecker(
        policy_spec_obj,
        sandbox_root=sandbox_root,
        tool_schemas=STUB_TOOL_SCHEMAS,
    )

    if max_iterations is None:
        max_iterations = int(policy_spec_obj.get("loop_budget.max_iterations", 10))

    return Agent(
        llm=make_canned_llm(fixture["canned_llm_tool_calls"]),
        tool_registry=STUB_TOOL_REGISTRY,
        policy_checker=checker,
        state_ledger=state_ledger,
        span_recorder=span_recorder,
        max_iterations=max_iterations,
    )


def run_fixture(
    fixture_name: str,
    *,
    policy_spec_obj: PolicySpec,
    tmp_path: Path,
) -> tuple[dict[str, Any], AgentResult, list[tuple[str, dict[str, Any]]]]:
    """End-to-end: load the fixture, build the agent, run, return triple.

    Returns:
        ``(fixture_dict, agent_result, recorded_spans_list)``.
    """
    fixture = load_fixture(fixture_name)
    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    agent = build_agent_for(
        fixture,
        policy_spec_obj=policy_spec_obj,
        tmp_path=tmp_path,
        span_recorder=_recorder,
    )
    result = agent.run(fixture["question"])
    return fixture, result, spans


# ---------------------------------------------------------------------------
# Universal invariant assertions
# ---------------------------------------------------------------------------


def assert_universal_invariants(
    *,
    fixture: Mapping[str, Any],
    agent_result: AgentResult,
    spans: list[tuple[str, dict[str, Any]]],
    policy_version: str,
) -> None:
    """The three universal assertions every PG fixture must satisfy.

    1. Exactly one ``policy_check`` span carries ``decision="deny"``
       AND its ``rule_id`` matches the fixture's expected rule_id.
    2. Every ``policy_check`` span carries ``policy.version`` equal to
       the v1 SHA-256 prefix.
    3. The deny ``policy_check`` span's ``agent.step_index`` matches
       the fixture's ``trigger_step_index``.
    """
    policy_spans = [attrs for sc, attrs in spans if sc == "policy_check"]
    deny_spans = [a for a in policy_spans if a.get("agent.policy.decision") == "deny"]

    expected_rule_id = fixture["expected"]["rule_id"]
    matching_denies = [a for a in deny_spans if a.get("agent.policy.rule_id") == expected_rule_id]

    assert len(matching_denies) == 1, (
        f"expected exactly one deny policy_check with rule_id="
        f"{expected_rule_id!r}; got {len(matching_denies)} "
        f"(all deny spans: {deny_spans!r})"
    )

    for attrs in policy_spans:
        assert attrs.get("policy.version") == policy_version, (
            f"policy_check span missing policy.version={policy_version!r}; "
            f"got {attrs.get('policy.version')!r} on attrs {attrs!r}"
        )

    assert matching_denies[0].get("agent.step_index") == fixture["expected"]["trigger_step_index"], (
        f"deny policy_check fired at step_index={matching_denies[0].get('agent.step_index')}; "
        f"fixture expected {fixture['expected']['trigger_step_index']}"
    )
