# Runtime Demo Run 2026-05-06_240d1c56_pg4_forbidden_tool_with_arg_schema_violation

## Setup

- Task: Invoke an unregistered tool whose arguments would also fail the input schema; tool_registry must win the precedence.
- Corpus: Adversarial fixture (no corpus); the agent calls stub tools to trigger the policy-gate denial documented in tasks/policy_gates/
- LLM execution path: stub
- Policy spec hash: 240d1c5626e6
- Seed: 0
- Timestamp: 2026-05-06T00:00:00Z

## Outcome

- Steps executed: 2
- Tool calls: 1 (0 allow, 1 deny, 0 escalate)
- Retries: 0 (0 exhausted)
- Failure modes triggered: (none)
- Result: success

## Notes

- Policy-gate trips:
- step 0: deny on rule_id `tool_registry`
- Reproducibility: regenerate this artifact with the corresponding `make` target against the upstream snapshot pinned in `manifest.json`. `trace.json`, `state.jsonl`, and `run_report.md` are byte-identical across reruns; `manifest.json` differs only on `timestamp`, `wall_clock_seconds`, and `code.git_sha`.
