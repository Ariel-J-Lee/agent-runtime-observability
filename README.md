# agent-runtime-observability

A governed agent runtime built around inspectability — OpenTelemetry-shaped traces, bounded retries, a policy-gate layer that denies unsafe tool calls, and a documented failure-mode catalog — designed to run on a laptop and audit, not a tracing dashboard with agents bolted on.

## Status

The runtime ships v1 captured-run evidence on `main`. The canonical run [`runs/2026-05-06_240d1c56_0/`](./runs/2026-05-06_240d1c56_0/) walks `search → fetch → read → summarize → final_answer` end-to-end via `make canonical`, against the synthetic 25-document fixture corpus and a deterministic stub LLM (`src/runtime/stub_llm/`) that keeps the canonical run hosted-LLM-free.

Seven policy-gate runs under [`runs/policy_gates/`](./runs/policy_gates/) and five failure-mode runs under [`runs/failure_modes/`](./runs/failure_modes/) complete the v1 captured-run surface. Each captured run carries the four required artifacts: `trace.json`, `state.jsonl`, `run_report.md`, and `manifest.json`.

## What this release demonstrates

| Capability | Captured run | Trace signature |
|---|---|---|
| Canonical demo task — single-agent loop reaches a final answer | [`runs/2026-05-06_240d1c56_0/run_report.md`](./runs/2026-05-06_240d1c56_0/run_report.md) | `agent_step` ×5, `llm_call` ×5, `tool_call` ×4, `policy_check` ×4 (all allow); terminal `final_answer` |
| **Policy gates that deny unsafe tool calls** | | |
| Off-allowlist URL (PG1) | [`runs/policy_gates/pg1_off_allowlist_url/run_report.md`](./runs/policy_gates/pg1_off_allowlist_url/run_report.md) | `policy_check` deny; `agent.policy.rule_id = url_allowlist`; terminates after deny |
| Sandbox escape (PG2) | [`runs/policy_gates/pg2_sandbox_escape/run_report.md`](./runs/policy_gates/pg2_sandbox_escape/run_report.md) | `policy_check` deny; `agent.policy.rule_id = sandbox_path`; terminates after deny |
| Loop / iteration budget (PG3) | [`runs/policy_gates/pg3_loop_budget/run_report.md`](./runs/policy_gates/pg3_loop_budget/run_report.md) | terminates with `agent.terminal_reason = loop_budget`; deny-span emission is a documented runtime gap (locked in `tests/evidence/test_pg3_runs_terminate_with_loop_budget_reason`) |
| ↳ Token-budget variant (PG3-tokens) | [`runs/policy_gates/pg3_loop_budget_tokens/run_report.md`](./runs/policy_gates/pg3_loop_budget_tokens/run_report.md) | terminates with `agent.terminal_reason = loop_budget`; deny-span emission is the same documented runtime gap as PG3 |
| Forbidden tool (PG4) | [`runs/policy_gates/pg4_forbidden_tool/run_report.md`](./runs/policy_gates/pg4_forbidden_tool/run_report.md) | `policy_check` deny; `agent.policy.rule_id = tool_registry`; terminates after deny |
| ↳ Precedence variant (PG4 with arg-schema violation) | [`runs/policy_gates/pg4_forbidden_tool_with_arg_schema_violation/run_report.md`](./runs/policy_gates/pg4_forbidden_tool_with_arg_schema_violation/run_report.md) | `policy_check` deny; `agent.policy.rule_id = tool_registry` (precedence rule fires before `arg_schema`) |
| Argument-shape violation (PG5) | [`runs/policy_gates/pg5_arg_schema/run_report.md`](./runs/policy_gates/pg5_arg_schema/run_report.md) | `policy_check` deny; `agent.policy.rule_id = arg_schema`; parent `agent_step` carries `agent.failure_mode = schema_mismatch` (F3) |
| **Failure modes with reproducible triggers** | | |
| `tool_call_failure` (F1) | [`runs/failure_modes/tool_call_failure/run_report.md`](./runs/failure_modes/tool_call_failure/run_report.md) | `retry_attempt` with `outcome = transient_failure` then `success`; `agent.failure_mode = tool_call_failure`; terminal `final_answer` |
| `retry_exhaustion` (F2) | [`runs/failure_modes/retry_exhaustion/run_report.md`](./runs/failure_modes/retry_exhaustion/run_report.md) | final `retry_attempt` with `outcome = exhausted`; `agent.failure_mode = retry_exhaustion`; `terminal_reason = failure_mode_terminal` |
| `schema_mismatch` (F3) | [`runs/failure_modes/schema_mismatch/run_report.md`](./runs/failure_modes/schema_mismatch/run_report.md) | `policy_check` deny `rule_id = arg_schema`; `agent.failure_mode = schema_mismatch`; `terminal_reason = failure_mode_terminal` |
| `cycle_detection` (F4) | [`runs/failure_modes/cycle_detection/run_report.md`](./runs/failure_modes/cycle_detection/run_report.md) | `policy_check` deny `rule_id = cycle_detection`; `agent.failure_mode = cycle_detection`; `terminal_reason = policy_denial_terminal` |
| `catalogued_unhandled` (F5) | [`runs/failure_modes/catalogued_unhandled/run_report.md`](./runs/failure_modes/catalogued_unhandled/run_report.md) | `tool_call` span carries `agent.tool.exception_class`; `agent.failure_mode = catalogued_unhandled`; `terminal_reason = failure_mode_terminal` |

## Headline summary

The canonical run (`2026-05-06_240d1c56_0`) executes 5 agent steps with 4 tool calls and 0 retries, emits 17 trace spans, and terminates with `final_answer` against the 25-document synthetic fixture corpus. Of the five named policy-gate scenarios, **four (PG1, PG2, PG4, PG5) fire deny spans with the documented `rule_id` set in the trace**; PG3 (loop budget; both iteration and token-budget variants) terminates via `agent.terminal_reason = loop_budget` rather than a deny span — a documented runtime gap surfaced in [`runs/policy_gates/pg3_loop_budget/run_report.md`](./runs/policy_gates/pg3_loop_budget/run_report.md). All five canonical failure modes fire `agent.failure_mode` on the offending step and reach their documented terminal state. Numbers and structural facts come from the captured `run_report.md` and `manifest.json` files; nothing in this prose claims more than those files support.

## Verification surface

The runtime, policy, trace, tool, fixture, and evidence slices verify the runtime / tool boundary with:

- `pytest tests/`
- `make smoke` — verify file structure
- `make smoke-runtime` — runtime-skeleton tests
- `make policy-gates` — exercise the seven policy-gate scenarios; `SCENARIO=<id>` selects one
- `make policy-gates-check` — re-emit and diff each policy-gate run against its committed artifacts
- `make failure-modes` — exercise the five canonical modes; `SCENARIO=<id>` selects one
- `make failure-modes-check` — re-emit and diff each failure-mode run against its committed artifacts
- `make trace-smoke` — drive the in-tree trace fixture through the OTLP-JSON exporter and validate against the subset schema
- `make tool-smoke` — drive the five v1 tools through a real `Agent.run` with strict-mode `arg_schema` enforcement
- `make fixture-build` — (re)build the deterministic fixture corpus from the documented seed
- `python3 -m scripts.build_fixture_corpus --check` — verify on-disk fixture matches the manifest
- `make canonical` — drive the canonical task fixture through a real `Agent.run` against the fixture corpus and the v1 tool, policy, and trace surfaces
- `make canonical-check` — re-emit and diff the canonical run against the committed artifacts
- `make evidence-build` and `make evidence-check` — aggregate emit / diff across canonical + policy-gate + failure-mode runs

The hiring signal is not that this is a production agent platform. It is a bounded reference implementation for governed tool use, schema enforcement, policy gates, failure classification, and traceable agent execution.

## Repository shape

| Path | What is here today |
|---|---|
| `src/runtime/` | Single-agent loop (`agent.py`), state ledger (`state.py`), policy seam (`policy.py`), bounded retry (`retry.py`), input-schema enforcement (`_schema.py`), and the deterministic stub LLM driver (`stub_llm/`). |
| `src/tracing/` | OTLP-JSON-subset writer (`otel_exporter.py`) and the subset-schema validator (`otlp_subset_schema.py`). |
| `src/fail/` | Failure-mode classifier mapping spans to the five catalogued modes (`catalog.py`). |
| `src/evidence/` | Captured-run helpers: `manifest.py` for the per-run reproducibility envelope, `run_report.py` for the human-readable headline, and `emit.py` for writing the four artifact files atomically. |
| `policy/` | Canonical YAML policy spec (`v1.yaml`), JSON meta-schema (`v1.schema.json`), and policy-gate documentation. The runtime self-validates the spec at startup. |
| `tools/` | Five v1 tools with `INPUT_SCHEMA` per tool: `search.py`, `fetch.py`, `read.py`, `write.py`, `summarize.py`. |
| `data/corpus/v1/` | Synthetic 25-document fixture corpus (deterministic, license-clean CC0-1.0, isolated to `data/`). Attestation in `data/DATA-SOURCE.md`. |
| `tasks/` | Canonical task fixture, seven policy-gate fixtures (PG1, PG2, PG3, PG3-tokens, PG4, PG4-precedence, PG5), and five failure-mode triggers. |
| `tests/` | Runtime-smoke, structure-smoke (`smoke.sh`), per-policy-gate scenario tests, per-failure-mode trigger tests, fixture-driven integration tests, and the evidence-suite tests that lock the captured-run shape and reproducibility envelope. |
| `scripts/` | `run_canonical_smoke.py`, `run_policy_gates.py`, `run_failure_modes.py`, `run_trace_smoke.py`, `run_tool_smoke.py`, `build_fixture_corpus.py`. |
| `runs/` | Committed captured runs: the canonical demo at `runs/2026-05-06_240d1c56_0/`, seven policy-gate runs under `runs/policy_gates/`, and five failure-mode runs under `runs/failure_modes/`. See [`runs/README.md`](./runs/README.md) for the per-run file inventory. |
| `docs/` | Architecture, runtime model, policy gates, failure modes, evidence-anchoring discipline. |
| `failure_modes.md` | Top-level documented failure-mode catalog summary. |
| `Makefile` | The targets named in `Verification surface` above. |

## Reproduce

```bash
git clone https://github.com/Ariel-J-Lee/agent-runtime-observability.git
cd agent-runtime-observability
pip install -r requirements.txt -r requirements-dev.txt
make smoke               # verify file structure
make smoke-runtime       # runtime-skeleton tests
make policy-gates        # exercise all seven policy-gate scenarios
make failure-modes       # exercise all five failure-mode triggers
make trace-smoke         # trace exporter + subset-schema validation
make tool-smoke          # five tools through a real Agent.run
make fixture-build       # (re)build the deterministic fixture corpus from the documented seed
python3 -m scripts.build_fixture_corpus --check   # verify on-disk fixture matches the manifest
make canonical           # canonical task through Agent.run on the fixture corpus
make canonical-check     # re-emit and diff the canonical run vs committed artifacts
make policy-gates-check  # re-emit and diff all seven policy-gate runs
make failure-modes-check # re-emit and diff all five failure-mode runs
```

The canonical run is deterministic given the pinned seed, the deterministic stub LLM, and the policy-spec hash. Two reviewers running `make canonical-check` against the same code state produce byte-identical `trace.json`, `state.jsonl`, and `run_report.md`. The `manifest.json` is byte-identical except on three documented per-run-volatile keys (`timestamp`, `wall_clock_seconds`, `code.git_sha`) that are excluded from the reproducibility diff.

## Limits

This is a first runnable proof, not a benchmark.

- **Deterministic stub LLM canonical default.** The committed runs use a deterministic stub LLM (`src/runtime/stub_llm/`) keyed by the canonical fixture. Live local-LLM and hosted-API paths are documented and runnable but opt-in only; they are not part of the captured-run surface.
- **Synthetic public-safe fixture corpus.** Twenty-five hand-authored CC0-1.0 documents under `data/corpus/v1/`. The runtime is exercised against these only; results do not generalize beyond this corpus.
- **Single-agent only at v1.** No multi-agent coordination. Multi-agent claims do not appear anywhere in this README, `docs/`, or the repo description.
- **Filesystem-path-based sandbox.** Sandbox isolation is `realpath`-based against an allowlisted per-run directory. Not container-isolated and not capability-restricted at v1.
- **PG3 documented runtime gap.** The loop-budget policy (PG3 and PG3-tokens) terminates via `agent.terminal_reason = loop_budget` rather than emitting a `policy_check` deny span. The gap is locked in `tests/evidence/test_pg3_runs_terminate_with_loop_budget_reason`. Surfacing the deny span on PG3 is a follow-on runtime fix.
- **First proof, not benchmark.** The captured runs demonstrate that the runtime components, the policy-gate denials, and the failure-mode triggers fire end-to-end with reproducible traces. They are not a performance, latency, throughput, or accuracy benchmark.
- **Reproducibility envelope is bounded.** Two reviewers running the same `make canonical-check` invocation produce byte-identical `trace.json` and `state.jsonl` given the pinned policy-spec hash, stub-LLM script hash, code SHA, and seed. Reproducibility across substantively different code or policy revisions is not claimed.
- **No coding-agent claim, no MCP-server claim.** Both deferred; neither is in v1 scope.
- **No production deployment claim, no customer-deployment claim, no autonomous-agent operation, no large-scale inference platform claim, no RLHF / DPO / LoRA training.** This is a local reference implementation.

## License

[Apache-2.0](./LICENSE).

## Adjacent repositories

- [`production-rag-eval-harness`](https://github.com/Ariel-J-Lee/production-rag-eval-harness) — retrieval-quality evaluation harness.
- [`aws-bedrock-iac-reference`](https://github.com/Ariel-J-Lee/aws-bedrock-iac-reference) — AWS / Bedrock infrastructure-as-code reference.

Cross-references are descriptive only; this repository does not import or deploy them.
