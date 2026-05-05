# Runtime Model

The v1 release implements a single-agent governed runtime with seven required components. This document describes the contract; the implementation packet provides the code at Tier 4.

## Required components

1. **LLM** — one local LLM provides reasoning. Local-first (Ollama-shape). Hosted-API integration is opt-in only.
2. **Tool surface** — a small fixed set of tools with JSON-schema input/output contracts (e.g., `search`, `fetch`, `read`, `write`). Tools are deterministic stubs by default at v1.
3. **Policy / guardrail layer** — between LLM tool intent and tool execution. Declarative policy spec (recommended YAML). Rules check tool name, arguments, and runtime context against allowlist/blocklist before execution. Deny events are first-class trace spans.
4. **State management** — per-step state record (LLM input, LLM output, intended tool calls, policy decisions, tool results, errors) persisted as JSONL. State is rerunnable from the committed file.
5. **Retry policy** — bounded retries on transient tool failures with exponential backoff. Hard cap (recommended 3 retries per tool call, configurable). Exhaustion is a first-class failure mode in the catalog.
6. **Trace export** — OpenTelemetry-shaped JSON written per run (OTLP JSON spec subset). Spans for `agent_step`, `llm_call`, `tool_call`, `policy_check`, `retry_attempt`. Trace IDs propagate across all spans of a run.
7. **Failure-mode catalog** — a documented set of failure modes the runtime detects and traces, with reproducible fixtures.

## What "governed" means here (operational definition)

Not generic guardrails. For this repo, governed means:

- every tool call is gated by an explicit policy check whose decision is recorded in the trace;
- every retry is recorded with attempt index, backoff delay, and outcome;
- every state transition is rerunnable from the committed state file;
- every failure is classified into the catalog rather than left as an unhandled exception.

## Recommended span attributes (minimum)

Each span carries the following attributes at minimum:

- `agent.run_id`
- `agent.step_index`
- `agent.tool_name` (on `tool_call` spans)
- `agent.policy.decision` ∈ `{allow, deny, escalate}` (on `policy_check` spans)
- `agent.policy.rule_id` (on `policy_check` spans where `decision != allow`)
- `agent.retry.attempt` and `agent.retry.outcome` (on `retry_attempt` spans)
- `agent.failure_mode` (on any span that emits a catalogued failure)

These are recommendations; the implementation packet may expand. The set above is the minimum legible shape.

## v0 status

No runtime is implemented at v0. Stub modules exist under `src/runtime/`, `src/tracing/`, and `src/fail/` so the project structure is importable but inert. Real implementation lands at Tier 4.
