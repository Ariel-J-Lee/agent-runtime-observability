# agent-runtime-observability

A governed agent runtime built around inspectability — OpenTelemetry-shaped traces, bounded retries, a policy-gate layer that denies unsafe tool calls, and a documented failure-mode catalog — designed to run on a laptop and audit, not a tracing dashboard with agents bolted on.

## Status

This repository is currently a scaffold. Traces, policy-gate demonstrations, retry histories, failure-mode triggers, and any multi-agent or coding-agent claims arrive in a subsequent release; see [`ROADMAP.md`](./ROADMAP.md).

## What the next release will demonstrate

A single-agent governed runtime that:

- runs end-to-end on a 16 GB laptop with no hosted-API dependency by default;
- emits OpenTelemetry-shaped JSON traces (OTLP JSON subset) loadable in Jaeger or Grafana Tempo;
- demonstrates at least three of five named policy-gate scenarios — off-allowlist URL, sandbox escape, iteration / token budget, forbidden tool, argument-shape violation — with deny events visible in the trace and `rule_id` attributes set;
- ships a documented failure-mode catalog (tool-call failure, retry exhaustion, policy-gate trip, schema mismatch, cycle detection) with reproducible triggers;
- commits run reports for the canonical demo and each failure-mode trigger.

## Repository shape

| Path | Purpose today |
|---|---|
| `src/runtime/` | Stub modules for the seven runtime components. Importable, inert. |
| `src/tracing/` | Stub OpenTelemetry-shaped JSON exporter module. |
| `src/fail/` | Stub failure-mode catalog helper module. |
| `tasks/` | Placeholder. The next release ships canonical demo task, policy-gate fixtures, failure-mode triggers. |
| `policy/` | Placeholder. The next release ships the canonical declarative policy spec. |
| `tools/` | Placeholder. The next release ships tool implementations with JSON-schema contracts. |
| `tests/` | Smoke test that verifies the file structure is intact. |
| `runs/` | Placeholder for trace artifacts. |
| `data/` | Placeholder. `data/DATA-SOURCE.md` documents the schema; no data committed yet. |
| `docs/` | Documentation describing the runtime model, policy gates, failure modes, and architecture. |
| `failure_modes.md` | Top-level documented catalog summary. |
| `Makefile` | `make smoke` runs the smoke test. Other targets print status and exit non-zero. |

## Reproduce

```bash
git clone https://github.com/Ariel-J-Lee/agent-runtime-observability.git
cd agent-runtime-observability
make smoke   # verifies the file structure is intact
```

The canonical demo, trace verification, and policy-gate exercises arrive in a subsequent release.

## License

[Apache-2.0](./LICENSE).

## Adjacent repositories

- [`production-rag-eval-harness`](https://github.com/Ariel-J-Lee/production-rag-eval-harness) — retrieval-quality evaluation harness.
- [`aws-bedrock-iac-reference`](https://github.com/Ariel-J-Lee/aws-bedrock-iac-reference) — AWS / Bedrock infrastructure-as-code reference.

Cross-references are descriptive only; this repository does not import or deploy them.
