"""Tests for the OTLP-JSON-subset trace exporter.

Coverage:

- Round-trip: feed canned span events; assemble; validate; assert
  structure
- Determinism: same seed + same time_source → byte-identical JSON
  across two exporters
- Attribute completeness: every locked attribute (PACKET-046 §3.3)
  lands on the right span class
- Parent-child: child spans (llm_call / tool_call / policy_check /
  retry_attempt) attach to the current agent_step via parentSpanId
- Schema-drift detection: the validator raises on malformed docs
- Integration: build a real Agent (stub LLM + stub tools), wire the
  exporter, run end-to-end, validate the captured artifact
- ``agent_step`` follow-up merge: the failure-mode follow-up event
  merges into the existing step span instead of creating a new one
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.runtime._schema import SchemaError
from src.tracing import (
    OTLP_SUBSET_SCHEMA,
    OtelJsonExporter,
    SCOPE_NAME,
    SERVICE_NAME,
    SPAN_ID_PATTERN,
    SUBSET_VERSION,
    TRACE_ID_PATTERN,
    new_exporter,
    validate_otlp_subset,
)
from tests.tracing._helpers import (
    all_spans,
    build_stub_agent,
    extract_spans_by_name,
    get_attribute,
    make_deterministic_time_source,
)


# ---------------------------------------------------------------------------
# Empty exporter
# ---------------------------------------------------------------------------


def test_empty_exporter_produces_valid_doc():
    """An exporter that never receives a call still emits a valid OTLP doc."""
    exporter = OtelJsonExporter()
    doc = exporter.to_otlp_dict()

    # Must validate as a valid OTLP-subset doc even with zero spans.
    validate_otlp_subset(doc)

    assert doc["resourceSpans"][0]["scopeSpans"][0]["spans"] == []
    assert exporter.span_count == 0
    assert exporter.trace_id is None  # never assigned


# ---------------------------------------------------------------------------
# Round-trip + structure
# ---------------------------------------------------------------------------


def test_basic_round_trip_assembles_and_validates():
    exporter = OtelJsonExporter(
        seed=0,
        time_source=make_deterministic_time_source(),
    )
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    exporter("llm_call", {
        "agent.run_id": "r1",
        "agent.step_index": 0,
        "agent.llm.execution_path": "stub",
    })

    doc = exporter.to_otlp_dict()
    validate_otlp_subset(doc)

    spans = all_spans(doc)
    assert [s["name"] for s in spans] == ["agent_step", "llm_call"]


def test_resource_attributes_pin_service_and_subset_version():
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    doc = exporter.to_otlp_dict()

    resource_attrs = doc["resourceSpans"][0]["resource"]["attributes"]
    by_key = {a["key"]: a["value"] for a in resource_attrs}

    assert by_key["service.name"]["stringValue"] == SERVICE_NAME
    assert by_key["agent.runtime.subset_version"]["stringValue"] == SUBSET_VERSION

    scope_name = doc["resourceSpans"][0]["scopeSpans"][0]["scope"]["name"]
    assert scope_name == SCOPE_NAME


def test_trace_id_and_span_id_are_correct_hex_lengths():
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})

    spans = all_spans(exporter.to_otlp_dict())
    assert len(spans) == 1
    span = spans[0]
    assert len(span["traceId"]) == 32
    assert all(c in "0123456789abcdef" for c in span["traceId"])
    assert len(span["spanId"]) == 16
    assert all(c in "0123456789abcdef" for c in span["spanId"])


def test_span_kind_is_internal():
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    span = all_spans(exporter.to_otlp_dict())[0]
    # SPAN_KIND_INTERNAL = 1
    assert span["kind"] == 1


# ---------------------------------------------------------------------------
# Attribute encoding
# ---------------------------------------------------------------------------


def test_attribute_encoding_handles_all_supported_value_types():
    exporter = OtelJsonExporter()
    exporter("agent_step", {
        "agent.run_id": "r1",
        "agent.step_index": 0,
        "agent.flag.true": True,
        "agent.flag.false": False,
        "agent.score": 0.42,
    })

    span = all_spans(exporter.to_otlp_dict())[0]
    by_key = {a["key"]: a["value"] for a in span["attributes"]}

    assert by_key["agent.run_id"] == {"stringValue": "r1"}
    assert by_key["agent.step_index"] == {"intValue": "0"}
    assert by_key["agent.flag.true"] == {"boolValue": True}
    assert by_key["agent.flag.false"] == {"boolValue": False}
    assert by_key["agent.score"] == {"doubleValue": 0.42}


def test_attribute_keys_are_stable_sorted():
    """Two emissions with the same attrs in different key order produce identical attributes lists."""
    e1 = OtelJsonExporter()
    e1("agent_step", {
        "z.last": "z",
        "agent.run_id": "r",
        "a.first": "a",
        "agent.step_index": 0,
    })

    e2 = OtelJsonExporter()
    e2("agent_step", {
        "agent.step_index": 0,
        "agent.run_id": "r",
        "z.last": "z",
        "a.first": "a",
    })

    a1 = all_spans(e1.to_otlp_dict())[0]["attributes"]
    a2 = all_spans(e2.to_otlp_dict())[0]["attributes"]

    assert [kv["key"] for kv in a1] == [kv["key"] for kv in a2]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_seed_and_time_source_produces_byte_identical_json():
    def _build():
        exp = OtelJsonExporter(seed=42, time_source=make_deterministic_time_source())
        exp("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
        exp("policy_check", {
            "agent.run_id": "r1",
            "agent.step_index": 0,
            "agent.policy.decision": "allow",
            "policy.version": "abc",
        })
        return exp

    a = _build()
    b = _build()
    assert json.dumps(a.to_otlp_dict(), sort_keys=True) == json.dumps(b.to_otlp_dict(), sort_keys=True)
    assert a.trace_id == b.trace_id


def test_different_seeds_produce_different_trace_ids():
    e1 = OtelJsonExporter(seed=1)
    e2 = OtelJsonExporter(seed=2)
    e1("agent_step", {"agent.run_id": "r", "agent.step_index": 0})
    e2("agent_step", {"agent.run_id": "r", "agent.step_index": 0})
    assert e1.trace_id != e2.trace_id


# ---------------------------------------------------------------------------
# agent_step merge + parent-child
# ---------------------------------------------------------------------------


def test_agent_step_follow_up_merges_into_existing_span():
    """Two ``agent_step`` emissions for the same (run_id, step_index) merge.

    The runtime emits a follow-up ``agent_step`` event carrying
    ``agent.failure_mode`` after the step's body runs. The exporter
    must merge it into the existing span rather than create a second
    span for the same step.
    """
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    exporter("agent_step", {
        "agent.run_id": "r1",
        "agent.step_index": 0,
        "agent.failure_mode": "tool_call_failure",
    })

    spans = extract_spans_by_name(exporter.to_otlp_dict(), "agent_step")
    assert len(spans) == 1, f"expected a single merged agent_step; got {len(spans)}"

    span = spans[0]
    assert get_attribute(span, "agent.run_id") == "r1"
    assert get_attribute(span, "agent.step_index") == "0"
    assert get_attribute(span, "agent.failure_mode") == "tool_call_failure"


def test_child_spans_attach_to_current_agent_step_via_parent_span_id():
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    exporter("policy_check", {
        "agent.run_id": "r1",
        "agent.step_index": 0,
        "agent.policy.decision": "allow",
        "policy.version": "abc",
    })
    exporter("tool_call", {
        "agent.run_id": "r1",
        "agent.step_index": 0,
        "agent.tool_name": "search",
    })

    docs = exporter.to_otlp_dict()
    agent_step = extract_spans_by_name(docs, "agent_step")[0]
    children = [s for s in all_spans(docs) if s["name"] != "agent_step"]

    assert children
    for child in children:
        assert child.get("parentSpanId") == agent_step["spanId"]


def test_top_level_span_has_no_parent_span_id():
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    span = extract_spans_by_name(exporter.to_otlp_dict(), "agent_step")[0]
    assert "parentSpanId" not in span


def test_steps_in_different_run_or_step_get_distinct_agent_step_spans():
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 1})
    exporter("agent_step", {"agent.run_id": "r2", "agent.step_index": 0})

    spans = extract_spans_by_name(exporter.to_otlp_dict(), "agent_step")
    assert len(spans) == 3


def test_child_span_in_step_2_attaches_to_step_2_not_step_1():
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 0})
    exporter("agent_step", {"agent.run_id": "r1", "agent.step_index": 1})
    exporter("policy_check", {
        "agent.run_id": "r1",
        "agent.step_index": 1,
        "agent.policy.decision": "allow",
        "policy.version": "abc",
    })

    doc = exporter.to_otlp_dict()
    step1 = [s for s in all_spans(doc)
             if s["name"] == "agent_step"
             and get_attribute(s, "agent.step_index") == "1"][0]
    policy = [s for s in all_spans(doc) if s["name"] == "policy_check"][0]
    assert policy["parentSpanId"] == step1["spanId"]


# ---------------------------------------------------------------------------
# Schema drift
# ---------------------------------------------------------------------------


def test_validator_rejects_short_trace_id():
    bad_doc = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "x"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "x"},
                        "spans": [
                            {
                                "traceId": "tooshort",  # not 32 hex chars
                                "spanId": "0123456789abcdef",
                                "name": "agent_step",
                                "kind": 1,
                                "startTimeUnixNano": "0",
                                "endTimeUnixNano": "0",
                                "attributes": [],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with pytest.raises(SchemaError) as exc_info:
        validate_otlp_subset(bad_doc)
    assert "pattern" in exc_info.value.message.lower() or "tooshort" in exc_info.value.message.lower()


def test_validator_rejects_extra_top_level_key():
    bad_doc = {
        "resourceSpans": [],
        "extraField": "should not be here",
    }
    with pytest.raises(SchemaError):
        validate_otlp_subset(bad_doc)


def test_validator_rejects_missing_required_span_field():
    bad_doc = {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "scope": {"name": "x"},
                        "spans": [
                            {
                                # missing traceId
                                "spanId": "0123456789abcdef",
                                "name": "agent_step",
                                "kind": 1,
                                "startTimeUnixNano": "0",
                                "endTimeUnixNano": "0",
                                "attributes": [],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with pytest.raises(SchemaError):
        validate_otlp_subset(bad_doc)


def test_validator_accepts_well_formed_doc_from_real_exporter():
    """Driven exporter output validates without raising."""
    exporter = OtelJsonExporter(seed=0)
    exporter("agent_step", {"agent.run_id": "r", "agent.step_index": 0})
    exporter("policy_check", {
        "agent.run_id": "r",
        "agent.step_index": 0,
        "agent.policy.decision": "allow",
        "policy.version": "abc123",
    })
    exporter("retry_attempt", {
        "agent.run_id": "r",
        "agent.step_index": 0,
        "agent.retry.attempt": 1,
        "agent.retry.outcome": "success",
        "agent.retry.backoff_ms": 0,
    })
    exporter.validate()  # no raise


# ---------------------------------------------------------------------------
# Integration: real Agent + exporter + validation
# ---------------------------------------------------------------------------


def test_agent_run_through_exporter_yields_validating_trace():
    exporter = new_exporter(seed=7, time_source=make_deterministic_time_source())
    canned = [
        {"step_index": 0, "tool": "search", "args": {"query": "alpha"}},
        {"step_index": 1, "tool": "search", "args": {"query": "beta"}},
    ]
    agent = build_stub_agent(canned_tool_calls=canned, span_recorder=exporter)
    result = agent.run("trace-export integration test")

    # The agent ran the canned steps and then the LLM stub emits a
    # final_answer on step 2 (no canned entry).
    assert result.terminal_reason == "final_answer"
    assert result.step_count == 3

    # The captured trace validates against the subset schema.
    exporter.validate()

    doc = exporter.to_otlp_dict()
    span_names = [s["name"] for s in all_spans(doc)]
    # Each step should produce one agent_step + one llm_call (+ tool_call
    # and policy_check / retry_attempt for the canned tool steps).
    assert span_names.count("agent_step") == 3
    assert span_names.count("llm_call") == 3
    assert span_names.count("tool_call") == 2
    assert span_names.count("policy_check") == 2  # one per tool call
    # retry_attempt fires once per tool call (one success).
    assert span_names.count("retry_attempt") >= 2


def test_locked_attribute_set_lands_on_each_span_class():
    """Every locked attribute the runtime emits appears on the right span."""
    exporter = new_exporter(seed=11, time_source=make_deterministic_time_source())
    canned = [{"step_index": 0, "tool": "search", "args": {"query": "x"}}]
    agent = build_stub_agent(canned_tool_calls=canned, span_recorder=exporter)
    agent.run("attribute completeness test")

    doc = exporter.to_otlp_dict()

    agent_step = extract_spans_by_name(doc, "agent_step")[0]
    assert get_attribute(agent_step, "agent.run_id") is not None
    assert get_attribute(agent_step, "agent.step_index") is not None

    llm_call = extract_spans_by_name(doc, "llm_call")[0]
    assert get_attribute(llm_call, "agent.run_id") is not None
    assert get_attribute(llm_call, "agent.step_index") is not None
    assert get_attribute(llm_call, "agent.llm.execution_path") == "stub"

    tool_call = extract_spans_by_name(doc, "tool_call")[0]
    assert get_attribute(tool_call, "agent.run_id") is not None
    assert get_attribute(tool_call, "agent.step_index") is not None
    assert get_attribute(tool_call, "agent.tool_name") == "search"

    policy_check = extract_spans_by_name(doc, "policy_check")[0]
    assert get_attribute(policy_check, "agent.run_id") is not None
    assert get_attribute(policy_check, "agent.step_index") is not None
    assert get_attribute(policy_check, "agent.policy.decision") in ("allow", "deny")
    # PermissivePolicyChecker uses a permissive PolicySpec; its version
    # is still well-defined per the policy module's contract.
    assert get_attribute(policy_check, "policy.version") is not None

    retry_attempt = extract_spans_by_name(doc, "retry_attempt")[0]
    assert get_attribute(retry_attempt, "agent.run_id") is not None
    assert get_attribute(retry_attempt, "agent.step_index") is not None
    assert get_attribute(retry_attempt, "agent.retry.attempt") is not None
    assert get_attribute(retry_attempt, "agent.retry.outcome") is not None
    assert get_attribute(retry_attempt, "agent.retry.backoff_ms") is not None


# ---------------------------------------------------------------------------
# Disk write
# ---------------------------------------------------------------------------


def test_write_serializes_doc_to_disk(tmp_path):
    exporter = OtelJsonExporter()
    exporter("agent_step", {"agent.run_id": "r", "agent.step_index": 0})
    out = tmp_path / "trace.json"
    written = exporter.write(out)

    assert written == out
    assert written.exists()
    parsed = json.loads(written.read_text(encoding="utf-8"))
    validate_otlp_subset(parsed)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_subset_version_is_pinned():
    assert SUBSET_VERSION == "v1.0"


def test_trace_id_and_span_id_patterns_are_lowercase_hex():
    assert TRACE_ID_PATTERN == "^[0-9a-f]{32}$"
    assert SPAN_ID_PATTERN == "^[0-9a-f]{16}$"


def test_otlp_subset_schema_top_level_shape():
    assert OTLP_SUBSET_SCHEMA["required"] == ["resourceSpans"]
    assert OTLP_SUBSET_SCHEMA["additionalProperties"] is False
