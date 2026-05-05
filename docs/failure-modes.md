# Failure Modes

The v1 release documents at least five failure modes with reproducible triggers. Each trigger commits a real run under `runs/failure_modes/<mode>/` showing the mode firing in the trace. **Trip artifacts ship at Tier 4 in a future implementation packet, not at v0.**

## Modes

### `tool_call_failure`

A tool invocation raises an error or returns a non-success result.

- Trace span: `tool_call` with `agent.failure_mode=tool_call_failure`.
- v1 fixture: `tasks/failure_modes/tool_call_failure.json`.
- v1 run: `runs/failure_modes/tool_call_failure/`.

### `retry_exhaustion`

Bounded retries are exhausted on a transient tool failure.

- Trace span: `retry_attempt` with `agent.retry.outcome=exhausted` and `agent.failure_mode=retry_exhaustion`.
- v1 fixture: `tasks/failure_modes/retry_exhaustion.json`.
- v1 run: `runs/failure_modes/retry_exhaustion/`.

### `policy_gate_trip`

The policy layer denies a tool call (any of PG1–PG5).

- Trace span: `policy_check` with `agent.policy.decision=deny` and `agent.failure_mode=policy_gate_trip`.
- v1 fixture: `tasks/failure_modes/policy_gate_trip.json`.
- v1 run: `runs/failure_modes/policy_gate_trip/`.

### `schema_mismatch`

A tool argument or output fails JSON-schema validation.

- Trace span: `tool_call` with `agent.failure_mode=schema_mismatch`.
- v1 fixture: `tasks/failure_modes/schema_mismatch.json`.
- v1 run: `runs/failure_modes/schema_mismatch/`.

### `cycle_detection`

The agent loop revisits the same state above a threshold.

- Trace span: `agent_step` with `agent.failure_mode=cycle_detection`.
- v1 fixture: `tasks/failure_modes/cycle_detection.json`.
- v1 run: `runs/failure_modes/cycle_detection/`.

## v0 status

No fixtures and no trip artifacts at v0. The implementation packet ships them at Tier 4.
