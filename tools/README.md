# Tools

The v1 tool layer for `agent-runtime-observability`. Each tool is a
pure-stdlib callable that accepts kwargs and returns a JSON-
serializable dict.

| Tool | Module | Purpose | Policy gate(s) |
|---|---|---|---|
| `search` | `tools/search.py` | Local-corpus substring search against a caller-injected mapping | PG3 (loop budget) on repeated unfocused calls |
| `fetch` | `tools/fetch.py` | `file://` URL fetch via stdlib `urllib.request` | PG1 (off-allowlist URL) |
| `read` | `tools/read.py` | UTF-8 file read | PG2 (sandbox escape) |
| `write` | `tools/write.py` | UTF-8 file write (creates parent dirs) | PG2 (sandbox escape) |
| `summarize` | `tools/summarize.py` | Deterministic extractive summarizer (stub at v1) | PG5 (argument-shape violation) |

## Schema-contract surface

Each tool module exports an `INPUT_SCHEMA: dict[str, Any]` that the
in-tree JSON-schema validator at `src/runtime/_schema.py` consumes.
`PolicyChecker(arg_schema_enforcement="strict", tool_schemas=...)`
validates every tool call's kwargs against the per-tool schema before
admitting the call; failures fire the `arg_schema` deny rule (PG5).

The aggregate `tools.TOOL_SCHEMAS` mapping is the single hand-off:
callers pass it directly to `PolicyChecker(tool_schemas=...)`.

## Wiring tools into an Agent

```python
from src.runtime import Agent, PolicyChecker, PolicySpec
from tools import TOOL_SCHEMAS, default_registry

policy_spec = PolicySpec.from_yaml_path("policy/v1.yaml")
checker = PolicyChecker(policy_spec, tool_schemas=TOOL_SCHEMAS, sandbox_root=...)
agent = Agent(
    name="demo",
    llm=...,
    tool_registry=default_registry(corpus={"doc-1": "..."}),
    policy_checker=checker,
)
```

`default_registry()` accepts an optional `corpus: Mapping[str, str]`
for the `search` tool; the other four tools are corpus-agnostic.

## v1 deviation set

- No HTTP/HTTPS transport at v1 (`fetch` is `file://`-only).
- No remote search backend (`search` consumes only a caller-injected
  corpus mapping).
- No LLM-backed summarization (`summarize` is a deterministic
  extractive stub).
- No filesystem sandboxing inside the tools themselves; the
  `sandbox_path` policy rule is the load-bearing path-safety check.

These deviations are explicit so a later slice can swap any tool's
implementation without changing its public schema or its registered
name.

## Running the tool surface

```sh
make tool-smoke
```

drives all five tools through a real `Agent.run()` with a stub LLM
emitting a search → fetch → read → write → summarize sequence and a
3-document literal corpus, then prints a one-line PASS.
