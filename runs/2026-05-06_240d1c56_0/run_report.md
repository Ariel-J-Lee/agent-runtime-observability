# Runtime Demo Run 2026-05-06_240d1c56_0

## Setup

- Task: What does the Operator-A3 report say about its cadence review?
- Corpus: Synthetic 25-document corpus at data/corpus/v1/ (seed 20260506; CC0-1.0; PACKET-053 fixture)
- LLM execution path: stub
- Policy spec hash: a501847f03e2
- Seed: 0
- Timestamp: 2026-05-06T00:00:00Z

## Outcome

- Steps executed: 5
- Tool calls: 4 (4 allow, 0 deny, 0 escalate)
- Retries: 4 (0 exhausted)
- Failure modes triggered: (none)
- Result: success

## Notes

- Policy-gate trips:
- (no policy denials on this run)
- Reproducibility: regenerate this artifact with the corresponding `make` target against the upstream snapshot pinned in `manifest.json`. `trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns; `manifest.json` differs only on `timestamp`, `wall_clock_seconds`, and `code.git_sha`.
