# Roadmap

## Tier ladder

- **v0** (this commit): Tier 1 — Static Trace. Controlled scaffold only.
- **v1**: Tier 4 — Real Command Path. The runtime release contract specifies the v1 target and acceptance criteria.
- Tier 5 (live runtime against deployed system) and Tier 6 (customer-visible proof) are **anti-claims** for this repo at every version.

## v1 release contract surface

The v1 implementation must include all seven components of a single-agent governed runtime:

1. **LLM** — local-first; hosted opt-in only.
2. **Tool surface** — JSON-schema input/output contracts.
3. **Policy / guardrail layer** — declarative rules, deny events as first-class trace spans.
4. **State management** — per-step JSONL state record, rerunnable.
5. **Retry policy** — bounded retries, exponential backoff, hard cap.
6. **Trace export** — OpenTelemetry-shaped JSON (OTLP JSON subset).
7. **Failure-mode catalog** — documented modes with reproducible triggers.

See [`docs/runtime-model.md`](./docs/runtime-model.md) for the full contract.

## Policy-gate scenarios (v1 target)

At minimum three of five must be demonstrated with deny events visible in the trace and `rule_id` attributes set:

- **PG1** — off-allowlist URL fetch
- **PG2** — sandbox path escape
- **PG3** — iteration / token budget exceeded
- **PG4** — forbidden tool call
- **PG5** — argument-shape violation

See [`docs/policy-gates.md`](./docs/policy-gates.md).

## Failure-mode catalog (v1 target)

At minimum five modes must be documented with reproducible triggers:

- tool-call failure
- retry exhaustion
- policy-gate trip
- schema mismatch
- cycle detection

See [`docs/failure-modes.md`](./docs/failure-modes.md) and [`failure_modes.md`](./failure_modes.md).

## v2 deferral list

Out of scope for v0 and v1; revisited only if a Tier-4 evidence path makes them safe:

- Multi-agent coordination — held until a real Tier-4 multi-agent demo is committed; the v0 and v1 surface contains no multi-agent claim.
- Coding-agent variant — held; private brand references are blocked indefinitely.
- Container-isolated sandbox — v1 uses filesystem-path-based sandbox; container isolation is a v2 concern.
- Multi-region or HA deployment.
- Streaming UI or latency benchmarks.
- CI workflow beyond a smoke test — added with real implementation, not at v0.

## Open decisions (the implementation packet must resolve before publication)

- **OpenTelemetry SDK vs OpenTelemetry-shaped JSON without SDK dependency.** Default plan: shaped JSON, no hard SDK dependency at v1.
- **Local LLM choice.** Default plan: a small generic Ollama model from a non-coding-specialized family.
- **Policy spec language.** Default plan: YAML.
- **Sandbox primitives.** Default plan: filesystem-path-based with `os.path.realpath` checks at v1.
- **Trace viewer recommendation.** Jaeger and Grafana Tempo accept OTLP JSON.
- **Hosted-API opt-in mechanism.** Default plan: env-var opt-in with a startup banner so casual reviewers do not accidentally hit a hosted endpoint and confuse Tier 4 with Tier 5.
- **Regression-gate tolerance for failure-mode reruns.** Default plan: any catalogued mode failing to fire on rerun causes CI failure.

## v0 status

`make smoke` is the only Makefile target that does real work at v0. Every other target (`canonical`, `policy-gates`, `failure-modes`, `regression`) prints v0 status and exits non-zero so CI cannot be tricked into a green light without real implementation.
