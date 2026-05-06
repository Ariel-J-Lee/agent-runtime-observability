"""Local tool-surface smoke runner.

Drives the five v1 tools through a real :class:`Agent.run` with:

- a 3-document literal corpus for ``search``
- a fresh tmp sandbox for ``read`` / ``write``
- a stub LLM emitting search → fetch → read → write → summarize
- ``PolicyChecker(arg_schema_enforcement="strict", tool_schemas=
  TOOL_SCHEMAS)`` so every call traverses the real schema layer
- a permissive ``url_allowlist`` only widened in-process to admit the
  ``file://`` URL the fetch step uses

Prints a one-line PASS summary; exits 2 on any policy denial or
classified failure mode. No captured runs are committed — this is a
local validator only.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import (
    Agent,
    LLMInput,
    LLMOutput,
    PolicyChecker,
    PolicySpec,
    ToolCall,
)
from tools import TOOL_SCHEMAS, default_registry


def _make_canned_llm(steps):
    by_index = {i: tc for i, tc in enumerate(steps)}

    def _llm(inp: LLMInput) -> LLMOutput:
        tc = by_index.get(inp.step_index)
        if tc is None:
            return LLMOutput(final_answer="done", raw_text="terminal")
        return LLMOutput(intended_tool_calls=(tc,), raw_text=str(tc))

    return _llm


def main() -> int:
    corpus = {
        "doc-alpha": "Alpha is the first letter of the Greek alphabet.",
        "doc-beta": "Beta follows alpha. Both are Greek letters.",
        "doc-gamma": "Gamma is the third Greek letter.",
    }

    with tempfile.TemporaryDirectory() as raw_dir:
        sandbox = Path(raw_dir) / "sandbox"
        sandbox.mkdir(parents=True, exist_ok=True)
        seed = sandbox / "seed.txt"
        seed.write_text(
            "Alpha is a Greek letter. Beta follows alpha. Gamma is third.",
            encoding="utf-8",
        )

        raw = copy.deepcopy(
            PolicySpec.from_yaml_path(_REPO_ROOT / "policy" / "v1.yaml").raw
        )
        # Widen url_allowlist with the empty-host token so file:// URLs admit;
        # policy/v1.yaml on disk is unchanged.
        raw["url_allowlist"] = list(raw.get("url_allowlist", [])) + [""]
        spec = PolicySpec.from_dict(raw)
        checker = PolicyChecker(
            spec,
            tool_schemas=TOOL_SCHEMAS,
            sandbox_root=sandbox.resolve(),
        )

        canned = [
            ToolCall(tool="search", args={"query": "greek"}),
            ToolCall(tool="fetch", args={"url": f"file://{seed}"}),
            ToolCall(tool="read", args={"path": str(seed)}),
            ToolCall(
                tool="write",
                args={
                    "path": str(sandbox / "out.txt"),
                    "content": "smoke wrote this",
                },
            ),
            ToolCall(tool="summarize", args={"text": "One. Two. Three. Four."}),
        ]

        spans: list[tuple[str, dict[str, Any]]] = []

        def _recorder(span_class, attrs):
            spans.append((span_class, dict(attrs)))

        agent = Agent(
            llm=_make_canned_llm(canned),
            tool_registry=default_registry(corpus=corpus),
            policy_checker=checker,
            span_recorder=_recorder,
        )

        result = agent.run("walk the five v1 tools")

        denies = [
            attrs
            for cls, attrs in spans
            if cls == "policy_check" and attrs.get("agent.policy.decision") == "deny"
        ]
        if denies:
            print(
                f"[tool-smoke] FAIL  unexpected policy denials: "
                f"{json.dumps([d.get('agent.policy.rule_id') for d in denies])}"
            )
            return 2

        tool_calls = [
            attrs.get("agent.tool_name")
            for cls, attrs in spans
            if cls == "tool_call"
        ]
        expected = ["search", "fetch", "read", "write", "summarize"]
        if tool_calls != expected:
            print(f"[tool-smoke] FAIL  tool_call sequence: {tool_calls!r} != {expected!r}")
            return 2

        failure_modes = [r.failure_mode for r in result.records if r.failure_mode]
        if failure_modes:
            print(f"[tool-smoke] FAIL  classified failure modes: {failure_modes}")
            return 2

        print(
            f"[tool-smoke] PASS  tools={len(expected)}  "
            f"steps={result.step_count}  terminal={result.terminal_reason}"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
