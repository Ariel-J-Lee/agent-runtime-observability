# agent-runtime-observability

A governed agent runtime built around inspectability — OpenTelemetry-shaped traces, bounded retries, a policy-gate layer that actually denies unsafe tool calls, and a documented failure-mode catalog — that you can rerun on a laptop and audit, not a tracing dashboard with agents bolted on or an OpenTelemetry tutorial.

## v0 status

This repository is a v0 controlled scaffold. The runtime release contract lives in private planning materials; Tier-4 evidence target arrives in a future implementation packet.

There are **no benchmark numbers, no real traces, no real retry histories, no real policy-gate trips, no multi-agent proof, and no coding-agent proof** at v0. Empty directories and stub modules are intentional placeholders, not omitted evidence.

## What the v1 release will demonstrate

A single-agent governed runtime that:

- runs end-to-end on a 16 GB laptop with no hosted-API dependency by default;
- emits OpenTelemetry-shaped JSON traces (OTLP JSON subset) loadable in Jaeger or Grafana Tempo;
- demonstrates at least three of five named policy-gate scenarios (off-allowlist URL, sandbox escape, iteration / token budget, forbidden tool, argument-shape violation), with deny events visible in the trace and `rule_id` attributes set;
- ships a documented failure-mode catalog with at least five modes (tool-call failure, retry exhaustion, policy-gate trip, schema mismatch, cycle detection) and reproducible triggers;
- commits run reports for the canonical demo and each failure-mode trigger.

See [`ROADMAP.md`](./ROADMAP.md) for the v0 → v1 trajectory and open decisions.

## Repository shape

| Path | Purpose at v0 |
|---|---|
| `src/runtime/` | Stub modules for the seven required runtime components. Importable, inert. |
| `src/tracing/` | Stub OpenTelemetry-shaped JSON exporter module. |
| `src/fail/` | Stub failure-mode catalog helper module. |
| `tasks/` | Placeholder. v1 ships canonical demo task, policy-gate fixtures, failure-mode triggers. |
| `policy/` | Placeholder. v1 ships the canonical declarative policy spec. |
| `tools/` | Placeholder. v1 ships tool implementations with JSON-schema contracts. |
| `tests/` | One real smoke test that verifies the v0 file structure is intact. |
| `runs/` | Placeholder. v1 ships real Tier-4 trace artifacts here. **No fake traces at v0.** |
| `data/` | Placeholder. `data/DATA-SOURCE.md` documents the schema; no data committed at v0. |
| `docs/` | Real documentation describing the v1 contract: runtime model, policy gates, failure modes, evidence tier, architecture. |
| `failure_modes.md` | Top-level documented catalog summary. |
| `Makefile` | `make smoke` runs the v0 smoke test. Other targets print v0 status and exit non-zero. |

## Reproduce

`v0 ships a scaffold; reproducing the canonical demo, verifying traces, and exercising policy gates lands at Tier 4 in a future implementation packet.`

```bash
git clone https://github.com/Ariel-J-Lee/agent-runtime-observability.git
cd agent-runtime-observability
make smoke   # verifies the v0 file structure is intact
```

## License

[Apache-2.0](./LICENSE).

## Adjacent public portfolio repositories

These are sibling public repos under the same author. Each is its own scope; this repo does not deploy them or evaluate them.

- `production-rag-eval-harness` — retrieval-quality evaluation harness.
- `aws-bedrock-iac-reference` — AWS / Bedrock infrastructure-as-code reference architecture.

Cross-repo deployment is not part of any version of this repo.
