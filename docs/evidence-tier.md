# Evidence

This repository anchors numeric and structural claims to captured runs under [`runs/`](../runs/). The honesty discipline is load-bearing: claims in the README, in this `docs/` tree, or in the repository description trace back to a corresponding captured run, or they are not substantiated by a measurement.

## What is committed

The runtime ships v1 captured-run evidence on `main`:

- One canonical run at [`runs/2026-05-06_240d1c56_0/`](../runs/2026-05-06_240d1c56_0/) — single-agent loop walks `search → fetch → read → summarize → final_answer` end-to-end via `make canonical`.
- Seven policy-gate runs under [`runs/policy_gates/`](../runs/policy_gates/) — `pg1_off_allowlist_url`, `pg2_sandbox_escape`, `pg3_loop_budget`, `pg3_loop_budget_tokens`, `pg4_forbidden_tool`, `pg4_forbidden_tool_with_arg_schema_violation`, `pg5_arg_schema`.
- Five failure-mode runs under [`runs/failure_modes/`](../runs/failure_modes/) — `tool_call_failure`, `retry_exhaustion`, `schema_mismatch`, `cycle_detection`, `catalogued_unhandled`.

Each captured run carries the four required artifacts: `trace.json`, `state.jsonl`, `run_report.md`, `manifest.json`. The `manifest.json` pins the corpus snapshot, policy-spec hash, code SHA, stub-LLM script hash, and seed. Reviewers verify reproducibility byte-identically with `make canonical-check`, `make policy-gates-check`, and `make failure-modes-check`.

## Reproducibility envelope

`trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns given the pinned policy-spec hash, stub-LLM script hash, code SHA, and seed. `manifest.json` is byte-identical except on three documented per-run-volatile keys — `timestamp`, `wall_clock_seconds`, and `code.git_sha` — that are excluded from the reproducibility diff.

In-repo absolute paths in `trace.json` and `state.jsonl` are normalized to a stable `<repo>` token before being written, so the captured artifacts are reviewer-checkout-independent. A reviewer cloning the repo into any path can run `make evidence-check` and see byte-identical re-emission against the committed runs.

## What this repository does NOT claim

- No live runtime against a deployed system, no real production observation, no customer-visible proof.
- No real workflow, no real root-cause analysis, no production deployment claim.
- No multi-agent coordination, no coding-agent variant, no MCP-server delivery, no large-scale inference platform, no RLHF / DPO / LoRA training.
- No latency / throughput / SLA / benchmark numbers.
- No "audit-grade", "compliance-ready", "SOC2-ready", "regulator-acceptable", or "production-grade policy engine" framing. The runtime is a local reference implementation with reproducible captured runs.

## Discipline

A claim that names a numeric outcome (a span count, a step count, a retry count, a scenario count) traces back to a `manifest.json` field or a `run_report.md` cell on a committed run. A claim that names a structural fact (a rule-id, a failure-mode name, a terminal reason) traces back to a `trace.json` attribute or a `state.jsonl` field on a committed run. A claim that does neither — that lives only in prose, with no captured run to back it up — is not substantiated by a measurement and is not made on this repository's public surface.
