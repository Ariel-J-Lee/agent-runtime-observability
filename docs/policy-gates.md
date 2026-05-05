# Policy Gates

The v1 release demonstrates at least three of five named policy-gate scenarios end-to-end. Each demonstration commits a real trace under `runs/policy_gates/<scenario>/` showing the deny event with a `rule_id` attribute. **Trip artifacts ship at Tier 4 in a future implementation packet, not at v0.**

## Scenarios

| ID | Scenario | What gets denied | What the trace shows |
|---|---|---|---|
| PG1 | Off-allowlist URL | a `fetch` call to a URL not on the allowlist | `policy_check` span with `decision=deny`, `rule_id=url_allowlist`, the offending URL recorded as an attribute |
| PG2 | Sandbox escape | a `write` call targeting a path outside the sandbox dir | deny span with `rule_id=sandbox_path` |
| PG3 | Iteration / token budget | agent loop exceeds `max_iterations` or token budget | deny span with `rule_id=loop_budget` and the iteration / token count recorded |
| PG4 | Forbidden tool | agent attempts to call a tool not registered or explicitly disallowed | deny span with `rule_id=tool_registry` |
| PG5 | Argument-shape violation | tool call whose arguments fail JSON-schema validation | deny span with `rule_id=arg_schema` |

## Visibility rules

- Every deny event must appear in the trace as a first-class span (not buried in a log line).
- Every deny attribute must point at the rule (`rule_id`) and the policy spec hash (`policy.version` attribute) so a reviewer can map the deny to the rule that fired.
- Trip fixtures live under `tasks/policy_gates/<scenario>.json`; trip runs under `runs/policy_gates/<scenario>/`.

## v0 status

No fixtures and no trip artifacts at v0. The scenarios above describe the v1 contract; the implementation packet ships fixtures and runs.
