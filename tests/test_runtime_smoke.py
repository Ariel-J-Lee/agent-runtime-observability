"""Pytest smoke for the runtime skeleton.

Pure-stdlib + pytest: no model download, no network, no third-party
dependency at the test path. The smoke covers the four runtime
modules (state, policy, retry, agent) and the seams the canonical
plan exposes for the downstream T-POLICY / T-FAIL / T-TRACE / T-TOOLS
slices.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Allow the tests to run without an editable install: include the repo
# root so ``src.runtime`` resolves.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import (
    Agent,
    AgentResult,
    LLMInput,
    LLMOutput,
    PermissivePolicyChecker,
    PolicyChecker,
    PolicyDecision,
    PolicySpec,
    RetryAttemptRecord,
    RetryExhausted,
    RetryResult,
    StateLedger,
    StateRecord,
    ToolCall,
    bounded_retry,
)


# ---------------------------------------------------------------------------
# StateLedger
# ---------------------------------------------------------------------------


def test_state_ledger_round_trips_jsonl(tmp_path):
    """One append → one JSONL line → parsed back to the same StateRecord."""
    path = tmp_path / "state.jsonl"
    with StateLedger(path) as ledger:
        ledger.append(StateRecord(run_id="r1", step_index=0, llm_input="hi"))
        ledger.append(StateRecord(run_id="r1", step_index=1, llm_input="bye"))

    records = list(StateLedger.replay(path))
    assert len(records) == 2
    assert records[0].step_index == 0
    assert records[0].llm_input == "hi"
    assert records[1].step_index == 1
    assert records[1].llm_input == "bye"


def test_state_ledger_skips_blank_lines_on_replay(tmp_path):
    path = tmp_path / "state.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(StateRecord(run_id="r1", step_index=0).to_dict()) + "\n"
        "\n   \n"
        + json.dumps(StateRecord(run_id="r1", step_index=1).to_dict()) + "\n",
        encoding="utf-8",
    )
    records = list(StateLedger.replay(path))
    assert [r.step_index for r in records] == [0, 1]


def test_state_record_to_dict_carries_all_required_fields():
    rec = StateRecord(run_id="r1", step_index=0)
    payload = rec.to_dict()
    assert set(payload.keys()) == {
        "run_id",
        "step_index",
        "llm_input",
        "llm_output",
        "intended_tool_calls",
        "policy_decisions",
        "tool_results",
        "errors",
    }


def test_state_ledger_count_increments(tmp_path):
    path = tmp_path / "state.jsonl"
    ledger = StateLedger(path)
    assert ledger.count == 0
    ledger.append(StateRecord(run_id="r1", step_index=0))
    assert ledger.count == 1
    ledger.close()


# ---------------------------------------------------------------------------
# PolicySpec / PolicyChecker
# ---------------------------------------------------------------------------


def test_policy_spec_from_dict_assigns_deterministic_version():
    a = PolicySpec.from_dict({"loop_budget": {"max_iterations": 10}})
    b = PolicySpec.from_dict({"loop_budget": {"max_iterations": 10}})
    assert a.version == b.version
    assert len(a.version) == 12


def test_policy_spec_from_yaml_path_raises_helpful_error_when_pyyaml_missing(tmp_path, monkeypatch):
    """The lazy YAML import must produce a helpful error when pyyaml is not installed.

    This guards the canonical scope rule that ``pyyaml`` is NOT a runtime
    dependency at this slice. The error message must point callers at
    ``pip install pyyaml`` AND at the dict-based path.
    """
    # Block 'yaml' from importing.
    monkeypatch.setitem(sys.modules, "yaml", None)
    p = tmp_path / "policy.yaml"
    p.write_text("loop_budget:\n  max_iterations: 10\n", encoding="utf-8")
    with pytest.raises(ImportError) as exc_info:
        PolicySpec.from_yaml_path(p)
    msg = str(exc_info.value)
    assert "pyyaml" in msg
    assert "from_dict" in msg


def test_policy_checker_allows_when_spec_is_permissive():
    checker = PermissivePolicyChecker()
    decision = checker.check(tool_name="search", tool_args={"q": "x"})
    assert decision.decision == "allow"
    assert decision.rule_id is None


def test_policy_checker_denies_explicit_denylist():
    spec = PolicySpec.from_dict({"tool_registry": {"denied": ["delete"]}})
    checker = PolicyChecker(spec)
    decision = checker.check(tool_name="delete", tool_args={})
    assert decision.decision == "deny"
    assert decision.rule_id == "tool_registry"
    assert decision.metadata["policy.requested_tool"] == "delete"


def test_policy_checker_denies_outside_allowlist():
    spec = PolicySpec.from_dict({
        "tool_registry": {"allowed": ["search", "fetch"]},
    })
    checker = PolicyChecker(spec)
    decision = checker.check(tool_name="delete", tool_args={})
    assert decision.decision == "deny"
    assert decision.rule_id == "tool_registry"


def test_policy_checker_denies_off_allowlist_url():
    spec = PolicySpec.from_dict({"url_allowlist": ["safe.test"]})
    checker = PolicyChecker(spec)
    decision = checker.check(
        tool_name="fetch",
        tool_args={"url": "https://evil.test/secret"},
    )
    assert decision.decision == "deny"
    assert decision.rule_id == "url_allowlist"
    assert decision.metadata["policy.url"] == "https://evil.test/secret"
    assert decision.metadata["policy.host"] == "evil.test"


def test_policy_checker_allows_url_on_allowlist():
    spec = PolicySpec.from_dict({"url_allowlist": ["safe.test"]})
    checker = PolicyChecker(spec)
    decision = checker.check(
        tool_name="fetch",
        tool_args={"url": "https://safe.test/page"},
    )
    assert decision.decision == "allow"


def test_policy_checker_denies_sandbox_escape(tmp_path):
    spec = PolicySpec.from_dict({})
    checker = PolicyChecker(spec, sandbox_root=tmp_path)
    # /etc/passwd resolves outside tmp_path
    decision = checker.check(
        tool_name="read",
        tool_args={"path": "/etc/passwd"},
    )
    assert decision.decision == "deny"
    assert decision.rule_id == "sandbox_path"


def test_policy_checker_allows_path_inside_sandbox(tmp_path):
    spec = PolicySpec.from_dict({})
    checker = PolicyChecker(spec, sandbox_root=tmp_path)
    inside = tmp_path / "doc.txt"
    decision = checker.check(
        tool_name="read",
        tool_args={"path": str(inside)},
    )
    assert decision.decision == "allow"


def test_policy_checker_loop_budget_denies_at_max_iterations():
    spec = PolicySpec.from_dict({"loop_budget": {"max_iterations": 3}})
    checker = PolicyChecker(spec)
    assert checker.check_loop_budget(iterations=2).decision == "allow"
    deny = checker.check_loop_budget(iterations=3)
    assert deny.decision == "deny"
    assert deny.rule_id == "loop_budget"


def test_policy_checker_cycle_detection():
    spec = PolicySpec.from_dict({"cycle_detection": {"max_repeats": 2}})
    checker = PolicyChecker(spec)
    assert checker.check_cycle(repeats=1).decision == "allow"
    deny = checker.check_cycle(repeats=2)
    assert deny.decision == "deny"
    assert deny.rule_id == "cycle_detection"


# ---------------------------------------------------------------------------
# bounded_retry
# ---------------------------------------------------------------------------


def test_bounded_retry_succeeds_on_first_try():
    @bounded_retry(max_retries=3, sleep=lambda _s: None)
    def ok():
        return "fine"

    rr = ok()
    assert rr.outcome == "success"
    assert rr.value == "fine"
    assert len(rr.attempts) == 1
    assert rr.attempts[0].outcome == "success"


def test_bounded_retry_retries_then_succeeds():
    """Two transient failures, then success on attempt 3."""
    calls = {"n": 0}

    @bounded_retry(max_retries=3, sleep=lambda _s: None)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(f"flaky-{calls['n']}")
        return "finally"

    rr = flaky()
    assert rr.outcome == "success"
    assert rr.value == "finally"
    assert len(rr.attempts) == 3
    assert rr.attempts[0].outcome == "transient_failure"
    assert rr.attempts[1].outcome == "transient_failure"
    assert rr.attempts[2].outcome == "success"


def test_bounded_retry_exhausts_after_max_retries():
    @bounded_retry(max_retries=2, sleep=lambda _s: None)
    def always_fails():
        raise RuntimeError("nope")

    with pytest.raises(RetryExhausted) as exc_info:
        always_fails()
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_bounded_retry_propagates_non_retryable():
    @bounded_retry(
        max_retries=3,
        sleep=lambda _s: None,
        is_retryable=lambda exc: False,
    )
    def fails():
        raise RuntimeError("hard")

    with pytest.raises(RuntimeError):
        fails()


def test_bounded_retry_backoff_is_deterministic_across_runs():
    """Same seed → same backoff schedule across two retry runs."""
    seed = 42
    schedules = []
    for _ in range(2):
        captured: list[RetryAttemptRecord] = []

        @bounded_retry(
            max_retries=3,
            backoff_base_ms=100,
            backoff_cap_ms=2000,
            seed=seed,
            on_attempt=captured.append,
            sleep=lambda _s: None,
        )
        def fails():
            raise RuntimeError("transient")

        with pytest.raises(RetryExhausted):
            fails()
        schedules.append([(r.attempt, r.outcome, r.backoff_ms) for r in captured])

    assert schedules[0] == schedules[1]


def test_bounded_retry_calls_on_attempt_callback():
    seen: list[RetryAttemptRecord] = []

    @bounded_retry(
        max_retries=2,
        sleep=lambda _s: None,
        on_attempt=seen.append,
    )
    def ok():
        return "yes"

    ok()
    assert len(seen) == 1
    assert seen[0].outcome == "success"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


def _terminal_llm(answer: str = "the answer"):
    """An LLM stub that returns a terminal answer on the first call."""

    def _llm(_inp: LLMInput) -> LLMOutput:
        return LLMOutput(final_answer=answer, raw_text=answer)

    return _llm


def _scripted_llm(*outputs: LLMOutput):
    """An LLM stub that returns each provided LLMOutput in order, then loops on the last."""
    seq = list(outputs)

    def _llm(inp: LLMInput) -> LLMOutput:
        idx = min(inp.step_index, len(seq) - 1)
        return seq[idx]

    return _llm


def test_agent_terminates_on_final_answer():
    agent = Agent(
        llm=_terminal_llm("hi"),
        tool_registry={},
    )
    result = agent.run("what's up?")
    assert result.terminal_reason == "final_answer"
    assert result.final_answer == "hi"
    assert result.step_count == 1


def test_agent_invokes_tool_through_registry():
    """A tool the LLM calls is invoked via the registry; result lands in state."""
    calls: list[str] = []

    def search(q: str) -> str:
        calls.append(q)
        return f"results for {q}"

    llm = _scripted_llm(
        LLMOutput(intended_tool_calls=(ToolCall(tool="search", args={"q": "linux"}),)),
        LLMOutput(final_answer="done", raw_text="done"),
    )
    agent = Agent(llm=llm, tool_registry={"search": search})
    result = agent.run("find linux")
    assert result.terminal_reason == "final_answer"
    assert calls == ["linux"]
    assert result.records[0].tool_results[0]["ok"] is True
    assert result.records[0].tool_results[0]["result"] == "results for linux"


def test_agent_respects_max_iterations_when_no_terminal_answer():
    """An LLM that never emits a final_answer trips the loop budget."""
    llm = _scripted_llm(
        LLMOutput(intended_tool_calls=(ToolCall(tool="noop", args={}),)),
    )

    def noop():
        return None

    agent = Agent(
        llm=llm,
        tool_registry={"noop": noop},
        max_iterations=3,
    )
    result = agent.run("loop forever")
    assert result.terminal_reason == "loop_budget_exhausted"
    assert result.step_count == 3


def test_agent_records_policy_deny_and_skips_execution():
    """A denied tool call is recorded, not executed."""
    invoked: list[str] = []

    def delete():
        invoked.append("delete")
        return "deleted"

    spec = PolicySpec.from_dict({"tool_registry": {"denied": ["delete"]}})
    checker = PolicyChecker(spec)
    llm = _scripted_llm(
        LLMOutput(intended_tool_calls=(ToolCall(tool="delete", args={}),)),
        LLMOutput(final_answer="done", raw_text="done"),
    )
    agent = Agent(
        llm=llm,
        tool_registry={"delete": delete},
        policy_checker=checker,
    )
    result = agent.run("try to delete")
    # The denied tool was never invoked.
    assert invoked == []
    # The policy decision was recorded.
    assert result.records[0].policy_decisions[0]["decision"] == "deny"
    assert result.records[0].policy_decisions[0]["rule_id"] == "tool_registry"
    # The tool result records the policy skip.
    assert result.records[0].tool_results[0]["skipped_by_policy"] is True


def test_agent_emits_spans_through_recorder_seam():
    """The span_recorder seam is called for every span class the runtime emits."""
    spans: list[tuple[str, dict]] = []

    def recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    def search(q: str) -> str:
        return "ok"

    llm = _scripted_llm(
        LLMOutput(intended_tool_calls=(ToolCall(tool="search", args={"q": "x"}),)),
        LLMOutput(final_answer="done", raw_text="done"),
    )
    agent = Agent(llm=llm, tool_registry={"search": search}, span_recorder=recorder)
    agent.run("ask")

    span_classes = {sc for sc, _ in spans}
    assert "agent_step" in span_classes
    assert "llm_call" in span_classes
    assert "tool_call" in span_classes
    assert "policy_check" in span_classes
    assert "retry_attempt" in span_classes


def test_agent_persists_to_state_ledger_when_provided(tmp_path):
    """The state ledger receives one record per step."""
    path = tmp_path / "state.jsonl"
    ledger = StateLedger(path)
    agent = Agent(
        llm=_terminal_llm(),
        tool_registry={},
        state_ledger=ledger,
    )
    agent.run("ping")
    ledger.close()

    records = list(StateLedger.replay(path))
    assert len(records) == 1
    assert records[0].step_index == 0


def test_agent_reports_retry_exhaustion_as_terminal_reason():
    """A tool that always fails through retry exhaustion ends the run."""

    def flaky():
        raise RuntimeError("never works")

    llm = _scripted_llm(
        LLMOutput(intended_tool_calls=(ToolCall(tool="flaky", args={}),)),
    )
    agent = Agent(
        llm=llm,
        tool_registry={"flaky": flaky},
        max_retries=1,
    )
    result = agent.run("try")
    assert result.terminal_reason == "retry_exhausted"
    assert result.records[0].errors[0]["error"] == "retry_exhausted"


def test_agent_emits_policy_version_on_every_check():
    """Every policy_check span carries the policy.version attribute."""
    spans: list[tuple[str, dict]] = []

    def recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    spec = PolicySpec.from_dict({"loop_budget": {"max_iterations": 5}})
    checker = PolicyChecker(spec)

    def search(q: str) -> str:
        return "ok"

    llm = _scripted_llm(
        LLMOutput(intended_tool_calls=(ToolCall(tool="search", args={"q": "x"}),)),
        LLMOutput(final_answer="done", raw_text="done"),
    )
    agent = Agent(
        llm=llm,
        tool_registry={"search": search},
        policy_checker=checker,
        span_recorder=recorder,
    )
    agent.run("ask")

    policy_spans = [attrs for sc, attrs in spans if sc == "policy_check"]
    assert policy_spans, "expected at least one policy_check span"
    for attrs in policy_spans:
        assert attrs["policy.version"] == spec.version
        assert "agent.policy.decision" in attrs


def test_agent_max_iterations_must_be_positive():
    with pytest.raises(ValueError):
        Agent(llm=_terminal_llm(), tool_registry={}, max_iterations=0)
