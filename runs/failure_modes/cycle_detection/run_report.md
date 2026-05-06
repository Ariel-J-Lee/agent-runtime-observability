# Runtime Demo Run 2026-05-06_240d1c56_cycle_detection

## Setup

- Task: Repeat the same (tool, args) pair beyond cycle_detection.max_repeats.
- Corpus: Adversarial fixture (no corpus); the stub tool layer is rigged per tasks/failure_modes/ to fire the catalogued failure mode
- LLM execution path: stub
- Policy spec hash: 240d1c5626e6
- Seed: 0
- Timestamp: 2026-05-06T00:00:00Z

## Outcome

- Steps executed: 4
- Tool calls: 4 (3 allow, 1 deny, 0 escalate)
- Retries: 3 (0 exhausted)
- Failure modes triggered: cycle_detection
- Result: failure (cycle_detection)

## Notes

- Policy-gate trips:
- step 3: deny on rule_id `cycle_detection`
- Reproducibility: regenerate this artifact with the corresponding `make` target against the upstream snapshot pinned in `manifest.json`. `trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns; `manifest.json` differs only on `timestamp`, `wall_clock_seconds`, and `code.git_sha`.
