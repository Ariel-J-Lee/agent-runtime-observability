# Runs

Committed captured-run artifacts from the v1 runtime. Each run carries the four PACKET-046 §3.1 artifacts:

| File | Role |
|---|---|
| `trace.json` | OTLP/JSON-subset trace (Jaeger 1.52+ / Tempo 2.4+ accept on file import). Exporter at `src/tracing/otel_exporter.py`. |
| `state.jsonl` | Per-step rerunnable ledger. One JSON object per agent step. Schema in `docs/runtime-model.md`. |
| `run_report.md` | Recruiter-readable headline. Setup / Outcome / Notes sections. |
| `manifest.json` | Reproducibility envelope. Pins corpus, policy, code, stub-LLM, seed, timestamp. |

## Layout

```
runs/
├── 2026-05-06_<8-hex-policy-sha>_0/        # canonical run
│   ├── trace.json
│   ├── state.jsonl
│   ├── run_report.md
│   └── manifest.json
├── policy_gates/
│   ├── pg1_off_allowlist_url/...
│   ├── pg2_sandbox_escape/...
│   ├── pg3_loop_budget/...
│   ├── pg4_forbidden_tool/...
│   └── pg5_arg_schema/...
└── failure_modes/
    ├── tool_call_failure/...
    ├── retry_exhaustion/...
    ├── schema_mismatch/...
    ├── cycle_detection/...
    └── catalogued_unhandled/...
```

The canonical run directory name is `<YYYY-MM-DD>_<policy-spec-sha-prefix>_<seed>` per PACKET-046 §3.2 — sortable, deterministic given inputs, reviewer-readable. Non-canonical runs (`policy_gates/<scenario>/`, `failure_modes/<mode>/`) use the scenario / mode slug as the directory name; the full run-id lives inside `manifest.json`.

## Reproducibility contract (PACKET-054 GO-direction)

Two reviewers running the emitter against the same upstream snapshot produce **byte-identical** `trace.json`, `state.jsonl`, and `run_report.md`. `manifest.json` is byte-identical except on three documented per-run-volatile keys: `timestamp`, `wall_clock_seconds`, and `code.git_sha`. Reviewers verify reproducibility with:

```sh
make canonical-check        # re-emit canonical + diff
make policy-gates-check     # re-emit every PG run + diff
make failure-modes-check    # re-emit every FM run + diff
make evidence-check         # all three at once
```

Each prints `[<lane>] PASS  byte-identical re-emission ...` on success and exits 2 on drift.

## Regenerating the artifacts

```sh
make evidence-build         # canonical + 5 PG + 5 FM
make canonical              # canonical run only
make policy-gates           # all 5 PG runs
make policy-gates SCENARIO=pg1_off_allowlist_url   # one PG run
make failure-modes          # all 5 FM runs
make failure-modes SCENARIO=cycle_detection        # one FM run
```

The deterministic OTel-exporter time source (start `1746489600000000000`, +1 ms per call) and `random.Random(seed=0)` together lock trace ID, span IDs, and timestamps so reruns produce byte-identical traces.

## Loading a trace in Jaeger or Tempo

The captured `trace.json` files are OTLP/JSON-subset documents that Jaeger 1.52+ and Grafana Tempo 2.4+ accept on file import.

**Jaeger (one-line)**:

```sh
docker run --rm -p 16686:16686 jaegertracing/all-in-one:1.52
# then in the Jaeger UI: Search → Upload JSON file → select runs/<run-id>/trace.json
```

**Grafana Tempo (file-based ingestion)**: drop the `trace.json` into the Tempo blocks directory or use the file-import flow documented at <https://grafana.com/docs/tempo/latest/>.

The OTLP subset shipped here intentionally omits `traceState`, `flags`, `events`, `links`, `status`, and `droppedAttributesCount`. Adding those later is non-breaking for both viewers.

## Documented gap: root README trace-viewer invocation

PACKET-046 §1.3 #5 requires `README.md` to include a one-line trace-viewer invocation. PACKET-054's Forbidden Surface forbids root README state change. The trace-viewer invocation lives in this file (`runs/README.md`) instead. Surfacing the README link is deferred to a follow-on T-DOCS packet.

## What committed evidence does NOT claim

Per PACKET-046 §1.4 + PACKET-014 §1.3 / §8:

- These traces are not benchmark numbers. No latency / throughput / p95 / SLA claim is made or implied.
- No real workflow, no real RCA, no production deployment claim.
- The corpus is synthetic (CC0-1.0); see `data/DATA-SOURCE.md`.
- The LLM is a deterministic canned-table emitter; see `src/runtime/stub_llm/canned.py`. No live LLM is exercised.
