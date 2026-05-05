# Runs

> **v0 PLACEHOLDER.** This directory's real content arrives at Tier 4 in a future implementation packet. The empty state is intentional and is not evidence.

The v1 release will populate this directory with:

- `runs/<run-id>/trace.json` — OpenTelemetry-shaped JSON trace, one per canonical demo run
- `runs/<run-id>/state.jsonl` — per-step state record, rerunnable
- `runs/<run-id>/run_report.md` — human-readable run summary
- `runs/<run-id>/manifest.json` — run metadata (task ID, model versions, policy spec hash, code SHA, seed)
- `runs/policy_gates/<scenario>/` — committed runs for each demonstrated policy-gate scenario
- `runs/failure_modes/<mode>/` — committed runs for each catalogued failure-mode trigger

**No fake trace files at v0. No real trace files at v0 either.** Real Tier-4 traces appear here only when the implementation packet runs the canonical demo end-to-end.
