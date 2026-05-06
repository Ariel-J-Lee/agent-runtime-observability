"""Local canonical-task smoke runner.

Drives the canonical task fixture (``tasks/canonical/v1.json``) through
a real :class:`Agent.run` against:

- the deterministic 25-document fixture corpus at ``data/corpus/v1/``
- the real v1 tool layer (``tools.default_registry``)
- ``PolicyChecker(arg_schema_enforcement="strict",
  tool_schemas=tools.TOOL_SCHEMAS)`` with a per-run ``url_allowlist``
  widened in-process to admit ``file://`` URLs (canonical
  ``policy/v1.yaml`` stays untouched on disk)
- the deterministic stub LLM at ``src.runtime.stub_llm.canned``
- ``sandbox_root = data/corpus/v1/`` so the canonical ``read`` step
  passes the ``sandbox_path`` policy gate

Prints a one-line PASS summary; exits 2 on any policy denial, missing
final_answer, or classified failure mode. No captured runs are
committed — this is a local validator only.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import (
    Agent,
    PolicyChecker,
    PolicySpec,
    make_canned_llm,
)
from tools import TOOL_SCHEMAS, default_registry


_CANONICAL_FIXTURE = _REPO_ROOT / "tasks" / "canonical" / "v1.json"
_CORPUS_DIR = _REPO_ROOT / "data" / "corpus" / "v1"
_POLICY_YAML = _REPO_ROOT / "policy" / "v1.yaml"


def _load_corpus_dict() -> dict[str, str]:
    return {
        p.stem: p.read_text(encoding="utf-8")
        for p in sorted(_CORPUS_DIR.glob("op-a*.md"))
    }


def _substitute_templates(value, *, corpus_dir: Path):
    if isinstance(value, dict):
        return {k: _substitute_templates(v, corpus_dir=corpus_dir) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_templates(v, corpus_dir=corpus_dir) for v in value]
    if isinstance(value, str):
        s = value
        if "{{corpus_url:" in s:
            for doc_id in (p.stem for p in corpus_dir.glob("op-a*.md")):
                s = s.replace(
                    "{{corpus_url:" + doc_id + "}}",
                    (corpus_dir / f"{doc_id}.md").as_uri(),
                )
        if "{{corpus_path:" in s:
            for doc_id in (p.stem for p in corpus_dir.glob("op-a*.md")):
                s = s.replace(
                    "{{corpus_path:" + doc_id + "}}",
                    str(corpus_dir / f"{doc_id}.md"),
                )
        return s
    return value


def main() -> int:
    fixture = json.loads(_CANONICAL_FIXTURE.read_text(encoding="utf-8"))
    corpus = _load_corpus_dict()
    if not corpus:
        print(
            f"[canonical] FAIL  corpus empty at {_CORPUS_DIR}; "
            "run `make fixture-build` first"
        )
        return 2

    canned = _substitute_templates(
        copy.deepcopy(fixture["canned_llm_tool_calls"]),
        corpus_dir=_CORPUS_DIR,
    )

    raw = copy.deepcopy(PolicySpec.from_yaml_path(_POLICY_YAML).raw)
    raw["url_allowlist"] = list(raw.get("url_allowlist", [])) + [""]
    spec = PolicySpec.from_dict(raw)

    checker = PolicyChecker(
        spec,
        tool_schemas=TOOL_SCHEMAS,
        sandbox_root=_CORPUS_DIR.resolve(),
    )

    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    agent = Agent(
        llm=make_canned_llm(
            canned,
            default_final_answer=fixture["canned_llm_tool_calls"][-1].get("final_answer"),
        ),
        tool_registry=default_registry(corpus=corpus),
        policy_checker=checker,
        span_recorder=_recorder,
    )

    result = agent.run(fixture["question"])

    denies = [
        attrs.get("agent.policy.rule_id")
        for cls, attrs in spans
        if cls == "policy_check" and attrs.get("agent.policy.decision") == "deny"
    ]
    if denies:
        print(f"[canonical] FAIL  unexpected policy denials: {denies}")
        return 2

    failure_modes = [r.failure_mode for r in result.records if r.failure_mode]
    if failure_modes:
        print(f"[canonical] FAIL  classified failure modes: {failure_modes}")
        return 2

    if result.terminal_reason != "final_answer":
        print(
            f"[canonical] FAIL  terminal_reason={result.terminal_reason!r} "
            "(expected final_answer)"
        )
        return 2

    tool_calls = [
        attrs.get("agent.tool_name")
        for cls, attrs in spans
        if cls == "tool_call"
    ]
    expected_seq = fixture["expected"]["tool_call_sequence"]
    if tool_calls != expected_seq:
        print(
            f"[canonical] FAIL  tool_call sequence {tool_calls!r} "
            f"!= expected {expected_seq!r}"
        )
        return 2

    print(
        f"[canonical] PASS  steps={result.step_count}  "
        f"terminal={result.terminal_reason}  tools={len(tool_calls)}  "
        f"corpus_docs={len(corpus)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
