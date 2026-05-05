# Failure-Mode Catalog

This is the documented catalog of failure modes the v1 runtime must detect, classify, and surface in traces. Each entry below names the mode, the trigger, and the expected trace shape. **Trip artifacts (real trace files showing each mode firing) ship at Tier 4 in a future implementation packet, not at v0.**

For full mode descriptions, see [`docs/failure-modes.md`](./docs/failure-modes.md).

## Modes

1. **`tool_call_failure`** — a tool invocation raises an error or returns a non-success result. Trace span: `tool_call` with `agent.failure_mode=tool_call_failure`.
2. **`retry_exhaustion`** — bounded retries are exhausted on a transient tool failure. Trace span: `retry_attempt` with `agent.retry.outcome=exhausted` and `agent.failure_mode=retry_exhaustion`.
3. **`policy_gate_trip`** — the policy layer denies a tool call (any of PG1–PG5). Trace span: `policy_check` with `agent.policy.decision=deny` and `agent.failure_mode=policy_gate_trip`.
4. **`schema_mismatch`** — a tool argument or output fails JSON-schema validation. Trace span: `tool_call` with `agent.failure_mode=schema_mismatch`.
5. **`cycle_detection`** — the agent loop revisits the same state above a threshold. Trace span: `agent_step` with `agent.failure_mode=cycle_detection`.

Additional modes may be added by the implementation packet.

## v0 status

No trip artifacts at v0. `make failure-modes` is a placeholder target that prints v0 status and exits non-zero. Real trip artifacts land under `runs/failure_modes/<mode>/` at Tier 4.
