"""Tests for the canonical task fixture and its end-to-end run."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime import (
    Agent,
    PolicyChecker,
    PolicySpec,
    ToolCall,
    make_canned_llm,
)
from tools import TOOL_SCHEMAS, default_registry


_CANONICAL_FIXTURE = _REPO_ROOT / "tasks" / "canonical" / "v1.json"
_CORPUS_DIR = _REPO_ROOT / "data" / "corpus" / "v1"
_POLICY_YAML = _REPO_ROOT / "policy" / "v1.yaml"


def _load_fixture() -> dict:
    return json.loads(_CANONICAL_FIXTURE.read_text(encoding="utf-8"))


def _load_corpus_dict() -> dict[str, str]:
    return {
        p.stem: p.read_text(encoding="utf-8")
        for p in sorted(_CORPUS_DIR.glob("op-a*.md"))
    }


def _substitute_templates(value, *, corpus_dir: Path):
    """Substitute ``{{corpus_url:<id>}}`` and ``{{corpus_path:<id>}}``
    placeholders with concrete file-system paths."""
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


def test_canonical_fixture_has_required_top_level_fields():
    fix = _load_fixture()
    assert fix["scenario_class"] == "CANONICAL"
    assert "question" in fix
    assert "canned_llm_tool_calls" in fix
    assert isinstance(fix["canned_llm_tool_calls"], list)
    assert len(fix["canned_llm_tool_calls"]) >= 2  # at least one tool + final_answer
    assert fix["expected"]["terminal_reason"] == "final_answer"
    assert fix["expected"]["policy_decisions"] == "all_allow"
    assert fix["expected"]["failure_modes"] == []


def test_canonical_fixture_terminal_step_is_a_final_answer():
    fix = _load_fixture()
    last = fix["canned_llm_tool_calls"][-1]
    assert "final_answer" in last
    assert isinstance(last["final_answer"], str) and last["final_answer"]


def test_canonical_fixture_references_only_corpus_doc_ids():
    fix = _load_fixture()
    corpus_ids = {p.stem for p in _CORPUS_DIR.glob("op-a*.md")}
    serialized = json.dumps(fix)
    # Every corpus_url / corpus_path template id must resolve to a real doc.
    for prefix in ("{{corpus_url:", "{{corpus_path:"):
        idx = 0
        while True:
            i = serialized.find(prefix, idx)
            if i == -1:
                break
            j = serialized.find("}}", i)
            assert j != -1, "unterminated template"
            doc_id = serialized[i + len(prefix):j]
            assert doc_id in corpus_ids, f"template references unknown doc {doc_id!r}"
            idx = j + 2


def test_canonical_fixture_runs_to_terminal_final_answer():
    """End-to-end: real Agent + tools.default_registry + PolicyChecker
    walk the canned LLM through the canonical task and terminate
    successfully with no policy denials and no failure modes."""
    fix = _load_fixture()
    corpus = _load_corpus_dict()

    # Substitute templates so fetch / read / summarize see concrete values.
    canned = _substitute_templates(
        copy.deepcopy(fix["canned_llm_tool_calls"]),
        corpus_dir=_CORPUS_DIR,
    )

    # Widen the canonical url_allowlist with the empty-host token so
    # file:// URLs admit; canonical policy/v1.yaml stays untouched.
    raw = copy.deepcopy(PolicySpec.from_yaml_path(_POLICY_YAML).raw)
    raw["url_allowlist"] = list(raw.get("url_allowlist", [])) + [""]
    spec = PolicySpec.from_dict(raw)

    checker = PolicyChecker(
        spec,
        tool_schemas=TOOL_SCHEMAS,
        sandbox_root=_CORPUS_DIR.resolve(),
    )

    spans: list[tuple[str, dict]] = []

    def _recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    agent = Agent(
        llm=make_canned_llm(canned, default_final_answer=fix["canned_llm_tool_calls"][-1]["final_answer"]),
        tool_registry=default_registry(corpus=corpus),
        policy_checker=checker,
        span_recorder=_recorder,
    )

    result = agent.run(fix["question"])

    assert result.terminal_reason == fix["expected"]["terminal_reason"]
    assert result.final_answer == fix["canned_llm_tool_calls"][-1]["final_answer"]

    # No policy denials.
    decisions = [
        attrs.get("agent.policy.decision")
        for cls, attrs in spans
        if cls == "policy_check"
    ]
    assert decisions and all(d == "allow" for d in decisions), decisions

    # Tool-call sequence matches expected.
    tool_calls = [
        attrs.get("agent.tool_name")
        for cls, attrs in spans
        if cls == "tool_call"
    ]
    assert tool_calls == fix["expected"]["tool_call_sequence"]

    # No classified failure modes.
    assert all(r.failure_mode is None for r in result.records)
