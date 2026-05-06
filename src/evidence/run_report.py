"""Render PACKET-046 §3.6 ``run_report.md`` from a captured run.

Mandatory sections:

- ``# Runtime Demo Run <run-id>``
- ``## Setup`` — task, corpus, llm-execution-path, policy-spec-hash, seed, timestamp
- ``## Outcome`` — steps executed, tool-call counts (allow/deny/escalate),
  retry counts (with exhausted), failure-modes triggered, result
- ``## Notes`` — policy-gate trips one-line; reproducibility hint
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.runtime.agent import AgentResult


def _count_decisions(spans: Sequence[tuple[str, Mapping[str, Any]]]) -> tuple[int, int, int]:
    allow = deny = escalate = 0
    for cls, attrs in spans:
        if cls != "policy_check":
            continue
        d = attrs.get("agent.policy.decision")
        if d == "allow":
            allow += 1
        elif d == "deny":
            deny += 1
        elif d == "escalate":
            escalate += 1
    return allow, deny, escalate


def _count_retries(spans: Sequence[tuple[str, Mapping[str, Any]]]) -> tuple[int, int]:
    total = 0
    exhausted = 0
    for cls, attrs in spans:
        if cls != "retry_attempt":
            continue
        total += 1
        if attrs.get("agent.retry.outcome") == "exhausted":
            exhausted += 1
    return total, exhausted


def _policy_gate_lines(spans: Sequence[tuple[str, Mapping[str, Any]]]) -> list[str]:
    lines = []
    for cls, attrs in spans:
        if cls != "policy_check":
            continue
        if attrs.get("agent.policy.decision") != "deny":
            continue
        rule = attrs.get("agent.policy.rule_id", "<unknown>")
        step = attrs.get("agent.step_index", "?")
        lines.append(f"- step {step}: deny on rule_id `{rule}`")
    return lines


def render_run_report(
    *,
    manifest: Mapping[str, Any],
    agent_result: AgentResult,
    spans: Sequence[tuple[str, Mapping[str, Any]]],
    task_name: str,
    corpus_description: str,
) -> str:
    """Return the markdown body for ``run_report.md``."""
    allow, deny, escalate = _count_decisions(spans)
    retry_total, retry_exhausted = _count_retries(spans)
    failure_modes = sorted(
        {r.failure_mode for r in agent_result.records if r.failure_mode}
    )
    if agent_result.terminal_reason == "final_answer":
        result = "success"
    else:
        primary_mode = failure_modes[0] if failure_modes else agent_result.terminal_reason
        result = f"failure ({primary_mode})"

    pg_lines = _policy_gate_lines(spans)
    pg_block = "\n".join(pg_lines) if pg_lines else "- (no policy denials on this run)"
    fm_block = ", ".join(failure_modes) if failure_modes else "(none)"

    return (
        f"# Runtime Demo Run {manifest['run_id']}\n"
        f"\n"
        f"## Setup\n"
        f"\n"
        f"- Task: {task_name}\n"
        f"- Corpus: {corpus_description}\n"
        f"- LLM execution path: {manifest['llm']['execution_path']}\n"
        f"- Policy spec hash: {manifest['policy']['version']}\n"
        f"- Seed: {manifest['seed']}\n"
        f"- Timestamp: {manifest['timestamp']}\n"
        f"\n"
        f"## Outcome\n"
        f"\n"
        f"- Steps executed: {agent_result.step_count}\n"
        f"- Tool calls: {allow + deny + escalate} ({allow} allow, {deny} deny, {escalate} escalate)\n"
        f"- Retries: {retry_total} ({retry_exhausted} exhausted)\n"
        f"- Failure modes triggered: {fm_block}\n"
        f"- Result: {result}\n"
        f"\n"
        f"## Notes\n"
        f"\n"
        f"- Policy-gate trips:\n"
        f"{pg_block}\n"
        f"- Reproducibility: regenerate this artifact with the corresponding `make` target "
        f"against the upstream snapshot pinned in `manifest.json`. "
        f"`trace.json`, `state.jsonl`, and `run_report.md` are byte-identical "
        f"across reruns; `manifest.json` differs only on `timestamp`, "
        f"`wall_clock_seconds`, and `code.git_sha`.\n"
    )


__all__ = ["render_run_report"]
