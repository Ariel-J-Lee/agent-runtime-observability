# Failure-Mode Catalog

The v1 runtime classifies every observed failure into one of the five modes documented below. The classifier is `src/fail/catalog.py`; per-mode trigger fixtures live under `tasks/failure_modes/`; per-mode tests live under `tests/failure_modes/`; captured runs live under `runs/failure_modes/`.

For full mode descriptions, see [`docs/failure-modes.md`](./docs/failure-modes.md).

## Modes

### 1. `tool_call_failure`

- **Symptom** — A tool invocation failed transiently and was recorded; the bounded-retry layer is still within budget.
- **Reproduction** — `make failure-modes SCENARIO=tool_call_failure` (configurable stub fetcher fails on the first `fail_count` attempts then succeeds).
- **Trace signature** — `retry_attempt` spans with `agent.retry.outcome=transient_failure` followed by an `agent.retry.outcome=success`; the `agent_step` span carries `agent.failure_mode=tool_call_failure`.
- **Captured run** — [`runs/failure_modes/tool_call_failure/run_report.md`](./runs/failure_modes/tool_call_failure/run_report.md).
- **Limits** — Non-terminal: the run continues. The classification fires per-step when at least one transient failure was observed before a successful result. Distinct from `retry_exhaustion`, which fires only when the retry budget is exhausted.

### 2. `retry_exhaustion`

- **Symptom** — A tool's bounded-retry budget is exhausted; the run terminates.
- **Reproduction** — `make failure-modes SCENARIO=retry_exhaustion` (stub tool always fails; `policy.retry.max_retries=3` is exhausted).
- **Trace signature** — `retry_attempt` span with `agent.retry.outcome=exhausted`; the parent `agent_step` carries `agent.failure_mode=retry_exhaustion`. The agent's `terminal_reason="failure_mode_terminal"`.
- **Captured run** — [`runs/failure_modes/retry_exhaustion/run_report.md`](./runs/failure_modes/retry_exhaustion/run_report.md).
- **Limits** — Fires once the retry layer raises `RetryExhausted`. Distinct from `tool_call_failure`, which fires per attempt before exhaustion.

### 3. `schema_mismatch`

- **Symptom** — A tool call's arguments fail the input JSON-schema; the policy layer denies before the tool runs.
- **Reproduction** — `make failure-modes SCENARIO=schema_mismatch` (canned LLM emits a `search` call with `query` set to an integer; `policy.arg_schema_enforcement="strict"` denies).
- **Trace signature** — `policy_check` span with `agent.policy.decision=deny` and `agent.policy.rule_id=arg_schema`; the parent `agent_step` carries `agent.failure_mode=schema_mismatch`. No `tool_call` span (the tool never ran).
- **Captured run** — [`runs/failure_modes/schema_mismatch/run_report.md`](./runs/failure_modes/schema_mismatch/run_report.md).
- **Limits** — Fires only when the policy seam's `arg_schema_enforcement` is `"strict"` and the offending tool has a registered input schema. PG5 (the policy-side scenario) and F3 (the failure-mode classification) describe the same event from two angles.

### 4. `cycle_detection`

- **Symptom** — The agent observed the same `(tool, normalized_args)` pair more than `policy.cycle_detection.max_repeats` times in one run; the policy layer denies and the run terminates.
- **Reproduction** — `make failure-modes SCENARIO=cycle_detection` (canned LLM emits the same tool call four times; the fourth attempt trips the locked `max_repeats=3` threshold).
- **Trace signature** — `policy_check` span with `agent.policy.decision=deny` and `agent.policy.rule_id=cycle_detection`; the parent `agent_step` carries `agent.failure_mode=cycle_detection`. The agent's `terminal_reason="policy_denial_terminal"`.
- **Captured run** — [`runs/failure_modes/cycle_detection/run_report.md`](./runs/failure_modes/cycle_detection/run_report.md).
- **Limits** — The cycle key is `(tool_name, json.dumps(args, sort_keys=True))` so two argument dicts with identical content but different key order count as the same pair. Reordering across runs is invariant.

### 5. `catalogued_unhandled`

- **Symptom** — A tool raises a non-retryable, non-classifiable exception. The catch-all guarantees every observed failure has a documented mode.
- **Reproduction** — `make failure-modes SCENARIO=catalogued_unhandled` (stub tool raises a custom non-`Exception` class that bypasses bounded retry's default predicate).
- **Trace signature** — The `tool_call` span carries `agent.tool.exception_class=<name>`; the `agent_step` carries `agent.failure_mode=catalogued_unhandled`.
- **Captured run** — [`runs/failure_modes/catalogued_unhandled/run_report.md`](./runs/failure_modes/catalogued_unhandled/run_report.md).
- **Limits** — `KeyboardInterrupt` and `SystemExit` are explicitly re-raised by the runtime rather than classified, so process-level interrupts still propagate. Any other `BaseException` subclass that escapes bounded retry maps to this mode.

## Reproduction

```bash
pip install -r requirements.txt requirements-dev.txt
make failure-modes                                       # run all five
make failure-modes SCENARIO=tool_call_failure           # one mode
```

## Run artifacts

The per-mode test suite at `tests/failure_modes/` verifies each mode end-to-end against the canonical `policy/v1.yaml`. Captured trace artifacts live at `runs/failure_modes/<mode>/{trace.json, state.jsonl, run_report.md, manifest.json}`; reproduce them with `make failure-modes-check`.
