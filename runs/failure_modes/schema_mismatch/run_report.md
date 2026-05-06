# Runtime Demo Run 2026-05-06_240d1c56_schema_mismatch

## Setup

- Task: Call a registered tool with arguments that fail its input JSON-schema.
- Corpus: Adversarial fixture (no corpus); the stub tool layer is rigged per tasks/failure_modes/ to fire the catalogued failure mode
- LLM execution path: stub
- Policy spec hash: 240d1c5626e6
- Seed: 0
- Timestamp: 2026-05-06T00:00:00Z

## Outcome

- Steps executed: 2
- Tool calls: 1 (0 allow, 1 deny, 0 escalate)
- Retries: 0 (0 exhausted)
- Failure modes triggered: schema_mismatch
- Result: success

## Notes

- Policy-gate trips:
- step 0: deny on rule_id `arg_schema`
- Reproducibility: regenerate this artifact with the corresponding `make` target against the upstream snapshot pinned in `manifest.json`. `trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns; `manifest.json` differs only on `timestamp`, `wall_clock_seconds`, and `code.git_sha`.
