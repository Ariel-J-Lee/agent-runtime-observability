# Runtime Model

The v1 release implements a single-agent governed runtime with seven required components. This document describes the contract and points at the code on `main`.

For the live demonstration, see [`runs/2026-05-06_240d1c56_0/run_report.md`](../runs/2026-05-06_240d1c56_0/run_report.md).

## Required components

1. **LLM** — the runtime calls one LLM for reasoning. The canonical run uses a deterministic stub LLM at [`src/runtime/stub_llm/`](../src/runtime/stub_llm/). The `Agent` constructor accepts a `Callable[[LLMInput], LLMOutput]` seam so a caller can plug in a live local-LLM (e.g. Ollama-shape) or hosted-API adapter that satisfies that shape; no such adapter ships at v1.
2. **Tool surface** — a small fixed set of tools with JSON-schema input/output contracts: [`tools/search.py`](../tools/search.py), [`tools/fetch.py`](../tools/fetch.py), [`tools/read.py`](../tools/read.py), [`tools/write.py`](../tools/write.py), [`tools/summarize.py`](../tools/summarize.py).
3. **Policy / guardrail layer** — sits between LLM tool intent and tool execution. Declarative policy spec ([`policy/v1.yaml`](../policy/v1.yaml)) validated against a JSON meta-schema ([`policy/v1.schema.json`](../policy/v1.schema.json)) at startup. Rules check tool name, arguments, and runtime context against allowlist / blocklist before execution. Deny events are first-class trace spans. Implementation at [`src/runtime/policy.py`](../src/runtime/policy.py).
4. **State management** — per-step state record (LLM input, LLM output, intended tool calls, policy decisions, tool results, errors) persisted as JSONL. The committed `state.jsonl` is rerunnable. Implementation at [`src/runtime/state.py`](../src/runtime/state.py).
5. **Retry policy** — bounded retries on transient tool failures with exponential backoff. Hard cap (default 3 retries per tool call, configurable). Exhaustion is a first-class failure mode in the catalog. Implementation at [`src/runtime/retry.py`](../src/runtime/retry.py).
6. **Trace export** — OpenTelemetry-shaped JSON written per run (OTLP JSON spec subset). Spans for `agent_step`, `llm_call`, `tool_call`, `policy_check`, `retry_attempt`. Trace IDs propagate across all spans of a run. Implementation at [`src/tracing/otel_exporter.py`](../src/tracing/otel_exporter.py); subset-schema validator at [`src/tracing/otlp_subset_schema.py`](../src/tracing/otlp_subset_schema.py).
7. **Failure-mode catalog** — a documented set of failure modes the runtime detects and traces, with reproducible fixtures. Classifier at [`src/fail/catalog.py`](../src/fail/catalog.py); summary at [`failure_modes.md`](../failure_modes.md); long-form per-mode descriptions at [`docs/failure-modes.md`](./failure-modes.md).

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

These are recommendations; the implementation may expand. The set above is the minimum legible shape.
