"""End-to-end integration: real tools through Agent + PolicyChecker.

Pinned guarantees:

- ``PolicyChecker(arg_schema_enforcement="strict", tool_schemas=
  TOOL_SCHEMAS)`` constructs without raising. The strict-mode init
  guard requires every tool in ``policy_registry.allowed`` to have a
  registered schema; this test locks that the aggregate ``TOOL_SCHEMAS``
  covers every entry the canonical ``policy/v1.yaml`` allows.
- ``default_registry()`` returns a registry whose keys match
  ``TOOL_SCHEMAS`` exactly — no orphans on either side.
- A real ``Agent.run()`` walking a search → fetch → read → write →
  summarize sequence terminates without policy denials and with no
  classified failure mode when sandbox + URL allowlist are wired
  permissively for the test.
- The PG5 fixture's malformed ``query: 12345`` arg trips
  ``tools.search.INPUT_SCHEMA``, locking the cross-link between this
  slice and the canonical PG5 contract.
"""

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
    LLMInput,
    LLMOutput,
    PolicyChecker,
    PolicySpec,
    ToolCall,
)
from src.runtime._schema import SchemaError, validate
from tools import TOOL_SCHEMAS, default_registry


_POLICY_YAML = _REPO_ROOT / "policy" / "v1.yaml"
_PG5_FIXTURE = _REPO_ROOT / "tasks" / "policy_gates" / "pg5_arg_schema.json"


def _make_canned_llm(steps):
    """Drive the agent through ``steps``; emit final_answer at the end."""
    by_index = {i: tc for i, tc in enumerate(steps)}

    def _llm(inp: LLMInput) -> LLMOutput:
        tc = by_index.get(inp.step_index)
        if tc is None:
            return LLMOutput(final_answer="done", raw_text="terminal")
        return LLMOutput(intended_tool_calls=(tc,), raw_text=str(tc))

    return _llm


def test_strict_mode_construction_accepts_real_tool_schemas():
    spec = PolicySpec.from_yaml_path(_POLICY_YAML)
    # No raise: TOOL_SCHEMAS must cover every tool in
    # policy/v1.yaml's tool_registry.allowed.
    checker = PolicyChecker(spec, tool_schemas=TOOL_SCHEMAS)
    assert set(checker.tool_schemas) >= set(spec.get("tool_registry.allowed", []))


def test_default_registry_keys_match_tool_schemas_keys():
    registry = default_registry()
    assert set(registry) == set(TOOL_SCHEMAS)


def test_default_registry_covers_every_policy_allowed_tool():
    spec = PolicySpec.from_yaml_path(_POLICY_YAML)
    registry = default_registry()
    for tool_name in spec.get("tool_registry.allowed", []):
        assert tool_name in registry, f"missing tool: {tool_name}"


def test_agent_run_walks_all_five_tools_without_denials(tmp_path):
    sandbox = tmp_path / "agent-runtime-observability" / "test-run" / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    seed_file = sandbox / "seed.txt"
    seed_file.write_text("Alpha. Beta. Gamma.", encoding="utf-8")

    corpus = {
        "doc-alpha": "Alpha is a Greek letter.",
        "doc-beta": "Beta follows alpha.",
        "doc-gamma": "Gamma is a Greek letter used in physics.",
    }

    # Widen url_allowlist with the empty-host token so file:// URLs admit
    # under the policy's url_allowlist rule. The canonical policy/v1.yaml
    # is unchanged on disk; this is a per-test spec construction.
    raw = copy.deepcopy(PolicySpec.from_yaml_path(_POLICY_YAML).raw)
    raw["url_allowlist"] = list(raw.get("url_allowlist", [])) + [""]
    spec = PolicySpec.from_dict(raw)
    checker = PolicyChecker(
        spec,
        tool_schemas=TOOL_SCHEMAS,
        sandbox_root=sandbox.resolve(),
    )

    canned = [
        ToolCall(tool="search", args={"query": "greek"}),
        ToolCall(tool="fetch", args={"url": f"file://{seed_file}"}),
        ToolCall(tool="read", args={"path": str(seed_file)}),
        ToolCall(
            tool="write",
            args={"path": str(sandbox / "out.txt"), "content": "wrote"},
        ),
        ToolCall(tool="summarize", args={"text": "One. Two. Three. Four."}),
    ]

    spans: list[tuple[str, dict]] = []

    def _recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    agent = Agent(
        llm=_make_canned_llm(canned),
        tool_registry=default_registry(corpus=corpus),
        policy_checker=checker,
        span_recorder=_recorder,
    )

    result = agent.run("walk the five v1 tools")

    # Every policy_check span at this fixture should be allow.
    decisions = [
        attrs.get("agent.policy.decision")
        for cls, attrs in spans
        if cls == "policy_check"
    ]
    assert decisions, "expected at least one policy_check span"
    assert all(d == "allow" for d in decisions), decisions

    # Each of the five tools should have produced a tool_call span.
    tool_calls = [
        attrs.get("agent.tool_name")
        for cls, attrs in spans
        if cls == "tool_call"
    ]
    assert tool_calls == ["search", "fetch", "read", "write", "summarize"]

    # No classified failure mode on the happy path.
    assert all(r.failure_mode is None for r in result.records)


def test_pg5_fixture_args_trip_real_search_input_schema():
    """Lock the cross-link between PG5 fixture and tools.search.INPUT_SCHEMA.

    PACKET-052's GO direction is explicit: if the existing PG5 fixture
    no longer trips the real schema, stop and flag — do not rewrite the
    fixture in this lane. This assertion is the proof of compatibility.
    """
    fixture = json.loads(_PG5_FIXTURE.read_text(encoding="utf-8"))
    args = fixture["canned_llm_tool_calls"][0]["args"]
    from tools import search

    with pytest.raises(SchemaError):
        validate(args, search.INPUT_SCHEMA)
