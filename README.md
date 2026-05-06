# agent-runtime-observability

A governed agent runtime built around inspectability — OpenTelemetry-shaped traces, bounded retries, a policy-gate layer that denies unsafe tool calls, and a documented failure-mode catalog — designed to run on a laptop and audit, not a tracing dashboard with agents bolted on.

## Status

This repository contains the first working governed-runtime slice on `main`.

Implemented today:

- a single-agent runtime skeleton with a JSONL state ledger and a bounded retry layer
- a strict input-schema enforcement surface for tool calls
- a v1 policy-gate spec with five named scenarios (off-allowlist URL, sandbox escape, iteration / token budget, forbidden tool, argument-shape violation), each verified by per-scenario tests
- a documented failure-mode catalog with five canonical triggers (tool-call failure, retry exhaustion, policy-gate trip, schema mismatch, cycle detection), a classifier, and per-mode tests
- an OTLP-JSON-subset trace exporter with a subset-schema validator and a trace-smoke surface
- a five-tool layer (`search`, `fetch`, `read`, `write`, `summarize`) with `INPUT_SCHEMA` per tool and a tool-smoke surface
- a synthetic 25-document fixture corpus, a canonical task fixture, and a deterministic stub LLM that drives `make canonical` end-to-end with no hosted-LLM dependency

Still out of scope for this release:

- multi-agent orchestration
- hosted LLM dependency as proof
- production deployment
- customer deployment
- autonomous agent operation
- remote search backend or HTTP / HTTPS tool execution
- MCP server delivery
- large-scale inference platform claim

## Verification surface

The runtime, policy, trace, tool, and fixture slices verify the runtime / tool boundary with:

- `pytest tests/`
- `make smoke` — verify file structure
- `make smoke-runtime` — runtime-skeleton tests
- `make policy-gates` — five named scenarios; `SCENARIO=<id>` selects one
- `make failure-modes` — five canonical triggers; `SCENARIO=<id>` selects one
- `make trace-smoke` — drive the in-tree trace fixture through the OTLP-JSON exporter and validate against the subset schema
- `make tool-smoke` — drive the five v1 tools through a real `Agent.run` with strict-mode `arg_schema` enforcement
- `make fixture-build` — (re)build the deterministic fixture corpus from the documented seed
- `make canonical` — drive the canonical task fixture through a real `Agent.run` against the fixture corpus and the v1 tool, policy, and trace surfaces

The hiring signal is not that this is a production agent platform. It is a bounded reference implementation for governed tool use, schema enforcement, policy gates, failure classification, and traceable agent execution.

## Repository shape

| Path | What is here today |
|---|---|
| `src/runtime/` | Single-agent runtime: `agent.py` (loop), `policy.py` (validation seam), `retry.py` (bounded retry), `state.py` (JSONL state ledger), `_schema.py` (input-schema enforcement), `stub_llm/` (deterministic stub LLM driver). |
| `src/tracing/` | OTLP-JSON-subset writer (`otel_exporter.py`) and the subset-schema validator (`otlp_subset_schema.py`). |
| `src/fail/` | Failure-mode catalog and classifier (`catalog.py`). |
| `policy/` | v1 policy spec (`v1.yaml`), meta-schema (`v1.schema.json`), and policy-gate documentation. |
| `tools/` | Five v1 tools with `INPUT_SCHEMA` per tool: `search.py`, `fetch.py`, `read.py`, `write.py`, `summarize.py`. |
| `data/corpus/v1/` | Synthetic 25-document fixture corpus (deterministic, license-clean, isolated to `data/`). |
| `tasks/` | Canonical task fixture, policy-gate scenarios, failure-mode triggers. |
| `tests/` | Runtime-smoke test, structure-smoke (`smoke.sh`), per-policy-gate scenario tests, per-failure-mode trigger tests, fixture-driven integration tests. |
| `scripts/` | `run_canonical_smoke.py`, `run_policy_gates.py`, `run_failure_modes.py`, `run_trace_smoke.py`, `run_tool_smoke.py`, `build_fixture_corpus.py`. |
| `runs/` | Placeholder for committed runtime evidence; no canonical run is committed yet. |
| `docs/` | Architecture, runtime model, policy gates, failure modes, evidence-tier notes. |
| `failure_modes.md` | Top-level documented failure-mode catalog summary. |
| `Makefile` | The targets named in `Verification surface` above. |

## Reproduce

```bash
git clone https://github.com/Ariel-J-Lee/agent-runtime-observability.git
cd agent-runtime-observability
pip install -r requirements.txt -r requirements-dev.txt
make smoke           # verify file structure
make smoke-runtime   # runtime-skeleton tests
make policy-gates    # all five policy-gate scenarios
make failure-modes   # all five failure-mode triggers
make trace-smoke     # trace exporter + subset-schema validation
make tool-smoke      # five tools through a real Agent.run
make fixture-build --check   # verify on-disk fixture matches manifest
make canonical       # canonical task through Agent.run on the fixture corpus
```

A committed runtime evidence run, with policy-gate denial traces and failure-mode triggers captured under `runs/<run-id>/`, comes next.

## Evidence boundaries

This repository demonstrates governed-runtime mechanics in a local reference implementation. It does **not** claim:

- production SaaS deployment
- customer deployment
- autonomous agent operation
- multi-agent orchestration
- hosted LLM dependency as proof
- remote search backend or HTTP / HTTPS tool execution
- MCP server delivery
- large-scale inference platform ownership
- RLHF / DPO / LoRA training

## License

[Apache-2.0](./LICENSE).

## Adjacent repositories

- [`production-rag-eval-harness`](https://github.com/Ariel-J-Lee/production-rag-eval-harness) — retrieval-quality evaluation harness.
- [`aws-bedrock-iac-reference`](https://github.com/Ariel-J-Lee/aws-bedrock-iac-reference) — AWS / Bedrock infrastructure-as-code reference.

Cross-references are descriptive only; this repository does not import or deploy them.
