# Runtime Demo Run 2026-05-06_240d1c56_pg3_loop_budget_tokens

## Setup

- Task: Burn through the token budget before finishing.
- Corpus: Adversarial fixture (no corpus); the agent calls stub tools to trigger the policy-gate denial documented in tasks/policy_gates/
- LLM execution path: stub
- Policy spec hash: 240d1c5626e6
- Seed: 0
- Timestamp: 2026-05-06T00:00:00Z

## Outcome

- Steps executed: 3
- Tool calls: 2 (2 allow, 0 deny, 0 escalate)
- Retries: 2 (0 exhausted)
- Failure modes triggered: (none)
- Result: success

## Notes

- Policy-gate trips:
- (no policy denials on this run)
- Reproducibility: regenerate this artifact with the corresponding `make` target against the upstream snapshot pinned in `manifest.json`. `trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns; `manifest.json` differs only on `timestamp`, `wall_clock_seconds`, and `code.git_sha`.
