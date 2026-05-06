# Roadmap

> **Status note — 2026-05-06.** This roadmap predates the first runnable proof. The repository now ships v1 captured-run evidence on `main`: a canonical run at [`runs/2026-05-06_240d1c56_0/`](./runs/2026-05-06_240d1c56_0/), seven policy-gate runs under [`runs/policy_gates/`](./runs/policy_gates/), and five failure-mode runs under [`runs/failure_modes/`](./runs/failure_modes/). The seven runtime components, the five named policy-gate scenarios, and the five canonical failure modes are all demonstrated end-to-end with reproducible traces. PG3 (loop budget; iteration and token-budget variants) terminates via `agent.terminal_reason = loop_budget` rather than a deny span — a documented runtime gap that surfaces honestly in the captured run reports and is locked in `tests/evidence/test_pg3_runs_terminate_with_loop_budget_reason`. v2 deferrals stay deferred.

## v1 release contract surface (demonstrated)

The v1 implementation includes all seven components of a single-agent governed runtime:

1. **LLM** — the runtime calls one LLM for reasoning. The canonical run uses a deterministic stub LLM at [`src/runtime/stub_llm/`](./src/runtime/stub_llm/). The `Agent` constructor exposes a `Callable[[LLMInput], LLMOutput]` seam for a caller-supplied live-LLM or hosted-API adapter; no such adapter ships at v1.
2. **Tool surface** — five tools with JSON-schema input/output contracts at [`tools/`](./tools/).
3. **Policy / guardrail layer** — declarative rules with deny events as first-class trace spans. Spec at [`policy/v1.yaml`](./policy/v1.yaml).
4. **State management** — per-step JSONL state record, rerunnable. Implementation at [`src/runtime/state.py`](./src/runtime/state.py).
5. **Retry policy** — bounded retries, exponential backoff, hard cap. Implementation at [`src/runtime/retry.py`](./src/runtime/retry.py).
6. **Trace export** — OpenTelemetry-shaped JSON (OTLP JSON subset). Implementation at [`src/tracing/otel_exporter.py`](./src/tracing/otel_exporter.py).
7. **Failure-mode catalog** — documented modes with reproducible triggers. Classifier at [`src/fail/catalog.py`](./src/fail/catalog.py).

See [`docs/runtime-model.md`](./docs/runtime-model.md) for the per-component contract.

## Policy-gate scenarios (demonstrated)

All five named scenarios are demonstrated. PG1, PG2, PG4, and PG5 fire deny spans with the documented `rule_id` set in the trace. PG3 (loop budget) terminates with `agent.terminal_reason = loop_budget`; emitting the deny span on PG3 is a follow-on runtime fix tracked alongside the captured run.

- **PG1** — off-allowlist URL fetch — [`runs/policy_gates/pg1_off_allowlist_url/`](./runs/policy_gates/pg1_off_allowlist_url/) — `rule_id = url_allowlist`
- **PG2** — sandbox path escape — [`runs/policy_gates/pg2_sandbox_escape/`](./runs/policy_gates/pg2_sandbox_escape/) — `rule_id = sandbox_path`
- **PG3** — iteration / token budget exceeded — [`runs/policy_gates/pg3_loop_budget/`](./runs/policy_gates/pg3_loop_budget/) and [`runs/policy_gates/pg3_loop_budget_tokens/`](./runs/policy_gates/pg3_loop_budget_tokens/) — terminates with `agent.terminal_reason = loop_budget`; documented runtime gap on the deny-span emission
- **PG4** — forbidden tool call — [`runs/policy_gates/pg4_forbidden_tool/`](./runs/policy_gates/pg4_forbidden_tool/) and [`runs/policy_gates/pg4_forbidden_tool_with_arg_schema_violation/`](./runs/policy_gates/pg4_forbidden_tool_with_arg_schema_violation/) — `rule_id = tool_registry`
- **PG5** — argument-shape violation — [`runs/policy_gates/pg5_arg_schema/`](./runs/policy_gates/pg5_arg_schema/) — `rule_id = arg_schema`

See [`docs/policy-gates.md`](./docs/policy-gates.md).

## Failure-mode catalog (demonstrated)

All five canonical modes are demonstrated. Each fires `agent.failure_mode` on the offending step and reaches its documented terminal state.

- `tool_call_failure` — [`runs/failure_modes/tool_call_failure/`](./runs/failure_modes/tool_call_failure/)
- `retry_exhaustion` — [`runs/failure_modes/retry_exhaustion/`](./runs/failure_modes/retry_exhaustion/)
- `schema_mismatch` — [`runs/failure_modes/schema_mismatch/`](./runs/failure_modes/schema_mismatch/)
- `cycle_detection` — [`runs/failure_modes/cycle_detection/`](./runs/failure_modes/cycle_detection/)
- `catalogued_unhandled` — [`runs/failure_modes/catalogued_unhandled/`](./runs/failure_modes/catalogued_unhandled/)

See [`docs/failure-modes.md`](./docs/failure-modes.md) and [`failure_modes.md`](./failure_modes.md).

## v2 deferral list

Out of scope for v1; revisited only if a captured-run evidence path makes them safe:

- Multi-agent coordination — held until a real captured-run multi-agent demo is committed; the v1 surface contains no multi-agent claim.
- Coding-agent variant — held; private brand references are blocked indefinitely.
- Container-isolated sandbox — v1 uses filesystem-path-based sandbox; container isolation is a v2 concern.
- Multi-region or HA deployment.
- Streaming UI or latency benchmarks.
- CI workflow beyond the existing `make smoke` + `make policy-gates` + `make failure-modes` + `make evidence-check` surface — added with the regression-gate slice, not at v1.
- Regression gate — `make regression` as a separate v2 lane; the manifest's `regression_baseline` flag stays `false` at v1.
- PG3 deny-span emission — the policy-gate rule fires correctly (terminates with `agent.terminal_reason = loop_budget`), but the `policy_check` deny span on PG3 / PG3-tokens is a follow-on runtime fix tracked in `tests/evidence/test_pg3_runs_terminate_with_loop_budget_reason`.

## Open decisions (the implementation must resolve before any v2 publication)

- **OpenTelemetry SDK vs OpenTelemetry-shaped JSON without SDK dependency.** v1 ships shaped JSON, no hard SDK dependency.
- **Local LLM choice.** v1 ships the deterministic stub LLM as the canonical default. The `Agent` constructor accepts a `Callable[[LLMInput], LLMOutput]` seam, so a caller can plug in a live local-LLM or hosted-API adapter that satisfies that shape; no such adapter ships at v1.
- **Policy spec language.** v1 ships YAML at [`policy/v1.yaml`](./policy/v1.yaml).
- **Sandbox primitives.** v1 ships filesystem-path-based with `os.path.realpath` checks.
- **Trace viewer recommendation.** Jaeger 1.52+ and Grafana Tempo 2.4+ accept the captured `trace.json` files on file import; see [`runs/README.md`](./runs/README.md).
- **Hosted-API opt-in mechanism.** Deferred to a future release. Design intent is env-var opt-in with a startup banner so a caller does not accidentally hit a hosted endpoint; no opt-in mechanism ships at v1.
- **Regression-gate tolerance for failure-mode reruns.** v2 concern; v1 ships byte-identical reproducibility checks via `make canonical-check`, `make policy-gates-check`, `make failure-modes-check`.

## Verification today

`make smoke`, `make smoke-runtime`, `make policy-gates`, `make policy-gates-check`, `make failure-modes`, `make failure-modes-check`, `make trace-smoke`, `make tool-smoke`, `make fixture-build`, `make canonical`, `make canonical-check`, `make evidence-build`, and `make evidence-check` all do real work. `make regression` is the documented v2 lane and is not part of the v1 verification surface.
