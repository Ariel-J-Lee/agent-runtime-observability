# Failure Modes

The v1 release documents five failure modes with reproducible triggers. Each trigger commits a captured run under [`runs/failure_modes/<mode>/`](../runs/failure_modes/) carrying `trace.json`, `state.jsonl`, `run_report.md`, and `manifest.json`.

For the catalog summary, see [`failure_modes.md`](../failure_modes.md). For trace-level signatures, see the captured runs under [`runs/failure_modes/`](../runs/failure_modes/).

## Modes

### `tool_call_failure`

A tool invocation raises an error or returns a non-success result transiently; the bounded-retry layer is still within budget.

- Trace span: `retry_attempt` with `agent.retry.outcome=transient_failure` then `agent.retry.outcome=success`; the `agent_step` span carries `agent.failure_mode=tool_call_failure`.
- Fixture: [`tasks/failure_modes/tool_call_failure.json`](../tasks/failure_modes/tool_call_failure.json).
- Captured run: [`runs/failure_modes/tool_call_failure/run_report.md`](../runs/failure_modes/tool_call_failure/run_report.md).

### `retry_exhaustion`

Bounded retries are exhausted on a transient tool failure; the run terminates.

- Trace span: final `retry_attempt` with `agent.retry.outcome=exhausted`; the parent `agent_step` carries `agent.failure_mode=retry_exhaustion`. The agent's `terminal_reason="failure_mode_terminal"`.
- Fixture: [`tasks/failure_modes/retry_exhaustion.json`](../tasks/failure_modes/retry_exhaustion.json).
- Captured run: [`runs/failure_modes/retry_exhaustion/run_report.md`](../runs/failure_modes/retry_exhaustion/run_report.md).

### `schema_mismatch`

A tool call's arguments fail the input JSON-schema; the policy layer denies before the tool runs.

- Trace span: `policy_check` with `agent.policy.decision=deny` and `agent.policy.rule_id=arg_schema`; the parent `agent_step` carries `agent.failure_mode=schema_mismatch`. No `tool_call` span (the tool never ran).
- Fixture: [`tasks/failure_modes/schema_mismatch.json`](../tasks/failure_modes/schema_mismatch.json).
- Captured run: [`runs/failure_modes/schema_mismatch/run_report.md`](../runs/failure_modes/schema_mismatch/run_report.md).
- PG5 (the policy-side scenario) and `schema_mismatch` (the failure-mode classification) describe the same event from two angles.

### `cycle_detection`

The agent observed the same `(tool, normalized_args)` pair more than `policy.cycle_detection.max_repeats` times in one run; the policy layer denies and the run terminates.

- Trace span: `policy_check` with `agent.policy.decision=deny` and `agent.policy.rule_id=cycle_detection`; the parent `agent_step` carries `agent.failure_mode=cycle_detection`. The agent's `terminal_reason="policy_denial_terminal"`.
- Fixture: [`tasks/failure_modes/cycle_detection.json`](../tasks/failure_modes/cycle_detection.json).
- Captured run: [`runs/failure_modes/cycle_detection/run_report.md`](../runs/failure_modes/cycle_detection/run_report.md).

### `catalogued_unhandled`

A tool raises a non-retryable, non-classifiable exception. The catch-all guarantees every observed failure has a documented mode.

- Trace span: the `tool_call` span carries `agent.tool.exception_class`; the `agent_step` carries `agent.failure_mode=catalogued_unhandled`. The agent's `terminal_reason="failure_mode_terminal"`.
- Fixture: [`tasks/failure_modes/catalogued_unhandled.json`](../tasks/failure_modes/catalogued_unhandled.json).
- Captured run: [`runs/failure_modes/catalogued_unhandled/run_report.md`](../runs/failure_modes/catalogued_unhandled/run_report.md).
- `KeyboardInterrupt` and `SystemExit` are explicitly re-raised by the runtime rather than classified, so process-level interrupts still propagate. Any other `BaseException` subclass that escapes bounded retry maps to this mode.

## Reproduction

```bash
pip install -r requirements.txt requirements-dev.txt
make failure-modes                                       # exercise all five
make failure-modes SCENARIO=tool_call_failure            # exercise one
make failure-modes-check                                 # re-emit and diff against committed runs
```

## Run artifacts

The per-mode test suite at [`tests/failure_modes/`](../tests/failure_modes/) verifies each mode end-to-end against the canonical [`policy/v1.yaml`](../policy/v1.yaml). Captured trace artifacts live at [`runs/failure_modes/<mode>/`](../runs/failure_modes/) with the four-file shape.
