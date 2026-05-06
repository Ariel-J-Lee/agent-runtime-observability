# Policy Gates

The v1 release demonstrates the five named policy-gate scenarios end-to-end. Each scenario commits a captured run under [`runs/policy_gates/<scenario>/`](../runs/policy_gates/) carrying `trace.json`, `state.jsonl`, `run_report.md`, and `manifest.json`.

For trace-level signatures, see the captured runs under [`runs/policy_gates/`](../runs/policy_gates/).

## Scenarios

| ID | Scenario | What gets denied | Captured run | What the trace shows |
|---|---|---|---|---|
| PG1 | Off-allowlist URL | a `fetch` call to a URL not on the allowlist | [`pg1_off_allowlist_url/`](../runs/policy_gates/pg1_off_allowlist_url/run_report.md) | `policy_check` span with `decision=deny`, `rule_id=url_allowlist`, the offending URL recorded as an attribute |
| PG2 | Sandbox escape | a `write` call targeting a path outside the sandbox dir | [`pg2_sandbox_escape/`](../runs/policy_gates/pg2_sandbox_escape/run_report.md) | deny span with `rule_id=sandbox_path` |
| PG3 | Iteration budget | agent loop exceeds `max_iterations` | [`pg3_loop_budget/`](../runs/policy_gates/pg3_loop_budget/run_report.md) | terminates with `agent.terminal_reason = loop_budget`; deny-span emission is a documented runtime gap (locked in `tests/evidence/test_pg3_runs_terminate_with_loop_budget_reason`) |
| ↳ PG3-tokens | Token budget variant | agent loop exceeds `max_tokens` | [`pg3_loop_budget_tokens/`](../runs/policy_gates/pg3_loop_budget_tokens/run_report.md) | same documented runtime gap as PG3; terminates with `agent.terminal_reason = loop_budget` |
| PG4 | Forbidden tool | agent attempts to call a tool not registered or explicitly disallowed | [`pg4_forbidden_tool/`](../runs/policy_gates/pg4_forbidden_tool/run_report.md) | deny span with `rule_id=tool_registry` |
| ↳ PG4-precedence | Forbidden tool with arg-schema violation | same as PG4, but the arguments also fail JSON-schema | [`pg4_forbidden_tool_with_arg_schema_violation/`](../runs/policy_gates/pg4_forbidden_tool_with_arg_schema_violation/run_report.md) | deny span with `rule_id=tool_registry` (precedence rule fires before `arg_schema`) |
| PG5 | Argument-shape violation | tool call whose arguments fail JSON-schema validation | [`pg5_arg_schema/`](../runs/policy_gates/pg5_arg_schema/run_report.md) | deny span with `rule_id=arg_schema`; parent `agent_step` carries `agent.failure_mode = schema_mismatch` |

## Visibility rules

- Every deny event is a first-class span (not buried in a log line).
- Every deny attribute points at the rule (`rule_id`) and the policy spec hash (`policy.version` attribute) so a reviewer can map the deny to the rule that fired.
- Trip fixtures live under [`tasks/policy_gates/<scenario>.json`](../tasks/policy_gates/); captured runs under [`runs/policy_gates/<scenario>/`](../runs/policy_gates/).

## PG3 documented runtime gap

PG3 (loop budget; iteration variant) and PG3-tokens (token-budget variant) terminate via `agent.terminal_reason = loop_budget` rather than emitting a `policy_check` deny span. The runtime detects budget exhaustion and stops the loop correctly, but the `policy_check` deny event is not yet surfaced in the trace. The gap is locked in `tests/evidence/test_pg3_runs_terminate_with_loop_budget_reason` and `tests/evidence/test_each_policy_gate_run_carries_at_least_one_deny_span` (PG3 / PG3-tokens skip-list). Surfacing the deny span on PG3 is a follow-on runtime fix; the captured run reports the honest behavior so a reviewer can see exactly what the trace contains today.

## Reproduction

```bash
pip install -r requirements.txt requirements-dev.txt
make policy-gates                                         # exercise all seven scenarios
make policy-gates SCENARIO=pg1_off_allowlist_url          # exercise one
make policy-gates-check                                   # re-emit and diff against committed runs
```

The policy spec is at [`policy/v1.yaml`](../policy/v1.yaml).
