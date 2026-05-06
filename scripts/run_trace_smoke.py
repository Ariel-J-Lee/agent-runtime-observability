"""Local trace-smoke runner.

Drives a tiny in-tree fixture (canned LLM + stub tools + permissive
policy) end-to-end through the agent loop with the OTLP-JSON exporter
attached as the ``span_recorder``. Writes the resulting trace to a
temp path, validates it against :mod:`src.tracing.otlp_subset_schema`,
and prints a one-line summary. Exits 0 on success, non-zero on schema
drift.

This script is **local-only**: no captured runs are committed by this
packet. T-EVIDENCE later replaces this stub with a captured-run
emitter that writes ``runs/<run-id>/trace.json``.

Examples::

    make trace-smoke                           # writes to /tmp/agent-runtime-trace-smoke.json
    python3 -m scripts.run_trace_smoke --out /custom/path/trace.json
    python3 -m scripts.run_trace_smoke --keep   # leave the trace on disk after success
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import (
    Agent,
    LLMInput,
    LLMOutput,
    PermissivePolicyChecker,
    ToolCall,
)
from src.tracing import (
    SUBSET_VERSION,
    OtelJsonExporter,
    validate_otlp_subset,
)


_DEFAULT_OUTPUT = Path("/tmp") / "agent-runtime-trace-smoke.json"


def _stub_search(*, query: str) -> dict[str, str]:
    return {"hit": f"doc-for-{query}"}


def _stub_fetch(*, url: str) -> dict[str, str]:
    return {"url": url, "body": "stub body"}


_CANNED = (
    {"step_index": 0, "tool": "search", "args": {"query": "alpha"}},
    {"step_index": 1, "tool": "fetch", "args": {"url": "https://fixtures.local/page"}},
)


def _build_canned_llm():
    by_step = {entry["step_index"]: entry for entry in _CANNED}

    def _llm(inp: LLMInput) -> LLMOutput:
        entry = by_step.get(inp.step_index)
        if entry is None:
            return LLMOutput(final_answer="(smoke complete)", raw_text="")
        tc = ToolCall(tool=entry["tool"], args=dict(entry.get("args") or {}))
        return LLMOutput(intended_tool_calls=(tc,), raw_text=str(entry))

    return _llm


def _make_deterministic_time_source(start_ns: int = 1_700_000_000_000_000_000):
    state = {"n": 0}

    def _now_ns() -> int:
        t = start_ns + state["n"] * 1_000_000
        state["n"] += 1
        return t

    return _now_ns


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.run_trace_smoke",
        description=(
            "Run the in-tree trace smoke: build an Agent with stub LLM "
            "+ stub tools + the OTLP exporter, write the captured "
            "trace, and validate against the subset schema."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Output path for trace.json (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed for trace-id/span-id generation (default: 0)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Leave the trace file on disk after success (default: kept)",
    )
    args = parser.parse_args(argv)

    exporter = OtelJsonExporter(
        seed=args.seed,
        time_source=_make_deterministic_time_source(),
    )

    agent = Agent(
        llm=_build_canned_llm(),
        tool_registry={"search": _stub_search, "fetch": _stub_fetch},
        policy_checker=PermissivePolicyChecker(),
        span_recorder=exporter,
        max_iterations=10,
    )
    result = agent.run("trace smoke")
    written = exporter.write(args.out)

    # Independent re-validation: read back from disk.
    import json as _json
    parsed = _json.loads(written.read_text(encoding="utf-8"))
    try:
        validate_otlp_subset(parsed)
    except Exception as exc:  # noqa: BLE001
        print(f"[trace-smoke] FAIL: schema validation: {exc}", file=sys.stderr)
        return 2

    span_count = exporter.span_count
    print(
        f"[trace-smoke] PASS  subset={SUBSET_VERSION}  spans={span_count}  "
        f"steps={result.step_count}  terminal={result.terminal_reason}  "
        f"trace={written}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
