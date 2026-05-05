# Evidence Tier

This repository explicitly states the evidence tier of every release. The honesty discipline is load-bearing: a release at Tier 1 must not claim Tier 4 evidence; a release at Tier 4 must not claim Tier 5 evidence; Tier 5 and Tier 6 are anti-claims at every version of this repo.

## Tier definitions (used here)

- **Tier 1 — Static Trace.** Source read and reasoned about. Planning, contracts, scaffolds.
- **Tier 2 — Build / syntax.** Code compiles or imports.
- **Tier 3 — Targeted tests.** Relevant tests pass.
- **Tier 4 — Real Command Path.** The harness command runs end-to-end against committed fixtures and the run artifacts (trace, state ledger, run report, manifest) are committed.
- **Tier 5 — Live runtime.** Observed against deployed system. **Anti-claim for this repo at every version.**
- **Tier 6 — Customer-visible proof.** Real user saw it work in production. **Anti-claim for this repo at every version.**

## Current release

**v0 — Tier 1 — Static Trace.** Controlled scaffold only.

- No real traces.
- No real retry histories.
- No real policy-gate trip artifacts.
- No benchmark numbers.
- No multi-agent proof.
- No coding-agent proof.

## Target for next release

**v1 — Tier 4 — Real Command Path.** Targets:

- `make canonical` runs end-to-end from a clean checkout
- `runs/<id>/trace.json` (OTLP JSON subset), `state.jsonl`, `run_report.md`, `manifest.json` committed
- At least three of {PG1, PG2, PG3, PG4, PG5} demonstrated with deny spans
- At least five failure modes documented with reproducible triggers and committed runs
- A reviewer with no prior context, on a 16 GB laptop, can clone, install, and run `make canonical` (and `make policy-gates`, `make failure-modes`) in <15 minutes wall-clock total

## Anti-claims (forbidden in this repo's surface at every version)

- "Audit trail of every decision in production"
- "Compliance-grade trace evidence"
- "Tamper-proof audit log"
- "Continuous audit posture"
- "Customer-visible audit dashboard"
- "Production-grade tracing infrastructure"
- "Real-time tracing dashboard"
- "Self-healing agent runtime"
- "Unbounded retry resilience"

These over-claim what a runnable laptop harness can demonstrate.
