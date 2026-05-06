"""Tests for the v1 ``summarize`` tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.runtime._schema import SchemaError, validate
from tools import summarize


def test_summarize_returns_first_three_sentences_by_default():
    text = "First. Second. Third. Fourth. Fifth."
    result = summarize.handler(text=text)
    assert result["summary"] == "First. Second. Third."
    assert result["sentence_count"] == 5


def test_summarize_respects_max_sentences():
    text = "One. Two. Three. Four."
    result = summarize.handler(text=text, max_sentences=2)
    assert result["summary"] == "One. Two."


def test_summarize_handles_single_sentence():
    result = summarize.handler(text="Just one sentence.")
    assert result["summary"] == "Just one sentence."
    assert result["sentence_count"] == 1


def test_summarize_handles_no_terminal_punctuation():
    # No sentence boundary → treated as one sentence chunk.
    result = summarize.handler(text="raw text without period")
    assert result["summary"] == "raw text without period"
    assert result["sentence_count"] == 1


def test_summarize_is_deterministic():
    text = "Alpha. Beta. Gamma. Delta."
    a = summarize.handler(text=text, max_sentences=2)
    b = summarize.handler(text=text, max_sentences=2)
    assert a == b


def test_summarize_handles_question_and_exclamation_marks():
    text = "Why is this so? Because of physics! And math. And more."
    result = summarize.handler(text=text, max_sentences=3)
    assert result["summary"] == "Why is this so? Because of physics! And math."


def test_input_schema_requires_text():
    with pytest.raises(SchemaError):
        validate({}, summarize.INPUT_SCHEMA)


def test_input_schema_rejects_extra_kwargs():
    with pytest.raises(SchemaError):
        validate({"text": "x", "language": "en"}, summarize.INPUT_SCHEMA)


def test_input_schema_rejects_max_sentences_below_minimum():
    with pytest.raises(SchemaError):
        validate({"text": "x", "max_sentences": 0}, summarize.INPUT_SCHEMA)


def test_input_schema_accepts_text_only():
    validate({"text": "x"}, summarize.INPUT_SCHEMA)


def test_input_schema_accepts_text_and_max_sentences():
    validate({"text": "x", "max_sentences": 5}, summarize.INPUT_SCHEMA)
