# Tasks

The v1 task fixtures the runtime executes against.

| Path | Role |
|---|---|
| `tasks/canonical/v1.json` | The canonical demo task: a single golden-path question over the fixture corpus that drives `search → fetch → read → summarize → final_answer` with no policy denials and no failure modes |
| `tasks/policy_gates/pg{1-5}_*.json` | Adversarial fixtures that trigger the five policy-gate scenarios documented in `docs/policy-gates.md` |
| `tasks/failure_modes/<mode>.json` | Fixtures that trigger each catalogued failure mode documented in `docs/failure-modes.md` |

## Fixture shape

Every fixture is a single JSON document carrying:

- `scenario_id` — stable identifier referenced by tests + smoke runners
- `scenario_class` — one of `CANONICAL`, `PG1`–`PG5`, `F1`–`F5`
- `variant` — typically `default`; multiple variants of the same class differ in stub-LLM behavior
- `question` — the user-question string the agent receives
- `canned_llm_tool_calls` — list of step entries the deterministic stub LLM emits, keyed by `step_index`
- `expected` — the assertion contract: terminal reason, policy decisions, failure modes, tool-call sequence

Each `canned_llm_tool_calls` entry is either a tool call (`{"step_index": int, "tool": str, "args": dict}`) or a terminal answer (`{"step_index": int, "final_answer": str}`).

## Stub-LLM contract

All fixtures are consumed by the deterministic stub LLM at `src.runtime.stub_llm.canned.make_canned_llm`. The stub looks up each agent step in the canned table by `step_index` and emits the corresponding tool call or terminal answer. Two reviewers running the same fixture produce byte-identical traces.

## Path templates (canonical fixture only)

The canonical task fixture's `fetch` and `read` steps target real corpus files whose absolute paths are not known until the run starts. The fixture uses two template tokens that the smoke runner / test harness substitutes at runtime:

- `{{corpus_url:<doc-id>}}` → `file:///<absolute-corpus-path>/<doc-id>.md`
- `{{corpus_path:<doc-id>}}` → `<absolute-corpus-path>/<doc-id>.md`

Adversarial fixtures don't use templates; they carry literal paths chosen to trip the relevant policy gate.

## Running

```sh
make canonical       # canonical task end-to-end smoke
make policy-gates    # all five policy-gate scenarios
make failure-modes   # all five catalogued failure modes
```

Each runs locally; none commits anything under `runs/<run-id>/`.
