"""Tests for the v1 ``read`` tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.runtime._schema import SchemaError, validate
from tools import read

from tests.tools._helpers import make_sandbox, write_file


def test_read_returns_file_content(tmp_path):
    sandbox = make_sandbox(tmp_path)
    target = sandbox / "note.txt"
    write_file(target, "stored content")

    result = read.handler(path=str(target))

    assert result["path"] == str(target)
    assert result["content"] == "stored content"
    assert result["byte_count"] == len(b"stored content")


def test_read_handles_unicode(tmp_path):
    sandbox = make_sandbox(tmp_path)
    target = sandbox / "u.txt"
    body = "résumé"
    write_file(target, body)

    result = read.handler(path=str(target))

    assert result["content"] == body
    assert result["byte_count"] == len(body.encode("utf-8"))


def test_read_raises_when_path_missing(tmp_path):
    target = tmp_path / "absent.txt"
    with pytest.raises(FileNotFoundError):
        read.handler(path=str(target))


def test_input_schema_requires_path():
    with pytest.raises(SchemaError):
        validate({}, read.INPUT_SCHEMA)


def test_input_schema_rejects_extra_kwargs():
    with pytest.raises(SchemaError):
        validate({"path": "/a", "encoding": "utf-8"}, read.INPUT_SCHEMA)


def test_input_schema_accepts_path_only():
    validate({"path": "/a"}, read.INPUT_SCHEMA)
