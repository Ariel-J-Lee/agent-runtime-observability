"""Tests for the v1 ``search`` tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.runtime._schema import SchemaError, validate
from tools import search

from tests.tools._helpers import SAMPLE_CORPUS


def test_input_schema_is_well_formed():
    # The schema itself should be a well-formed object schema; validate
    # an empty doc against it to surface any shape-of-schema typos.
    with pytest.raises(SchemaError):
        validate({}, search.INPUT_SCHEMA)


def test_search_returns_matches_sorted_by_doc_id():
    handler = search.make_handler(corpus=SAMPLE_CORPUS)
    result = handler(query="greek")
    # All three SAMPLE_CORPUS docs mention "Greek"; sort is by doc-id.
    assert result["hits"] == ["doc-alpha", "doc-beta", "doc-gamma"]
    assert result["match_count"] == 3


def test_search_returns_only_matching_docs():
    handler = search.make_handler(corpus=SAMPLE_CORPUS)
    # Only doc-gamma mentions "physics".
    result = handler(query="physics")
    assert result == {"hits": ["doc-gamma"], "match_count": 1}


def test_search_is_case_insensitive():
    handler = search.make_handler(corpus=SAMPLE_CORPUS)
    assert handler(query="GREEK")["hits"] == ["doc-alpha", "doc-beta", "doc-gamma"]
    assert handler(query="Alpha")["hits"] == ["doc-alpha", "doc-beta"]


def test_search_empty_corpus_returns_no_hits():
    handler = search.make_handler(corpus={})
    assert handler(query="anything") == {"hits": [], "match_count": 0}


def test_search_no_matches_returns_no_hits():
    handler = search.make_handler(corpus=SAMPLE_CORPUS)
    assert handler(query="zeta") == {"hits": [], "match_count": 0}


def test_search_top_k_caps_results():
    handler = search.make_handler(corpus=SAMPLE_CORPUS)
    # All three SAMPLE_CORPUS docs mention "letter"; cap at 1.
    result = handler(query="letter", top_k=1)
    assert len(result["hits"]) == 1
    assert result["match_count"] == 3


def test_search_handler_takes_a_snapshot_of_corpus():
    mutable = dict(SAMPLE_CORPUS)
    handler = search.make_handler(corpus=mutable)
    mutable["doc-omega"] = "Omega is the last Greek letter."
    # Snapshot was taken at construction; later mutation should not
    # affect search results.
    result = handler(query="omega")
    assert "doc-omega" not in result["hits"]


def test_input_schema_rejects_int_query():
    # Mirrors the canonical PG5 fixture (tasks/policy_gates/pg5_arg_schema.json)
    # which sends ``query: 12345``; this assertion locks the cross-link
    # between the real input schema and the PG5 contract.
    with pytest.raises(SchemaError):
        validate({"query": 12345}, search.INPUT_SCHEMA)


def test_input_schema_rejects_extra_kwargs():
    with pytest.raises(SchemaError):
        validate({"query": "x", "rogue": "y"}, search.INPUT_SCHEMA)


def test_input_schema_accepts_query_only():
    validate({"query": "alpha"}, search.INPUT_SCHEMA)  # no raise


def test_input_schema_accepts_query_with_top_k():
    validate({"query": "alpha", "top_k": 3}, search.INPUT_SCHEMA)  # no raise
