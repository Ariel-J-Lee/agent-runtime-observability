# Runtime Demo Run 2026-05-06_240d1c56_catalogued_unhandled

## Setup

- Task: Tool raises an exception that is not classified by F1-F4.
- Corpus: Adversarial fixture (no corpus); the stub tool layer is rigged per tasks/failure_modes/ to fire the catalogued failure mode
- LLM execution path: stub
- Policy spec hash: 240d1c5626e6
- Seed: 0
- Timestamp: 2026-05-06T00:00:00Z

## Outcome

- Steps executed: 1
- Tool calls: 1 (1 allow, 0 deny, 0 escalate)
- Retries: 0 (0 exhausted)
- Failure modes triggered: catalogued_unhandled
- Result: failure (catalogued_unhandled)

## Notes

- Policy-gate trips:
- (no policy denials on this run)
- Reproducibility: regenerate this artifact with the corresponding `make` target against the upstream snapshot pinned in `manifest.json`. `trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns; `manifest.json` differs only on `timestamp`, `wall_clock_seconds`, and `code.git_sha`.
