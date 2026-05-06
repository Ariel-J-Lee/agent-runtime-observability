# Runtime Demo Run 2026-05-06_240d1c56_pg3_loop_budget

## Setup

- Task: Iterate forever without producing a final answer.
- Corpus: Adversarial fixture (no corpus); the agent calls stub tools to trigger the policy-gate denial documented in tasks/policy_gates/
- LLM execution path: stub
- Policy spec hash: 240d1c5626e6
- Seed: 0
- Timestamp: 2026-05-06T00:00:00Z

## Outcome

- Steps executed: 10
- Tool calls: 10 (10 allow, 0 deny, 0 escalate)
- Retries: 10 (0 exhausted)
- Failure modes triggered: (none)
- Result: failure (loop_budget_exhausted)

## Notes

- Policy-gate trips:
- (no policy denials on this run)
- Reproducibility: regenerate this artifact with the corresponding `make` target against the upstream snapshot pinned in `manifest.json`. `trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns; `manifest.json` differs only on `timestamp`, `wall_clock_seconds`, and `code.git_sha`.
