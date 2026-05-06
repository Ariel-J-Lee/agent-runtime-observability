"""Tests for the v1 ``write`` tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.runtime._schema import SchemaError, validate
from tools import write

from tests.tools._helpers import make_sandbox


def test_write_creates_file_with_content(tmp_path):
    sandbox = make_sandbox(tmp_path)
    target = sandbox / "out.txt"

    result = write.handler(path=str(target), content="payload")

    assert target.read_text(encoding="utf-8") == "payload"
    assert result == {
        "path": str(target),
        "ok": True,
        "byte_count": len(b"payload"),
    }


def test_write_creates_parent_dirs(tmp_path):
    sandbox = make_sandbox(tmp_path)
    target = sandbox / "deeply" / "nested" / "out.txt"

    write.handler(path=str(target), content="x")

    assert target.exists()


def test_write_overwrites_existing_file(tmp_path):
    sandbox = make_sandbox(tmp_path)
    target = sandbox / "out.txt"
    target.write_text("old", encoding="utf-8")

    write.handler(path=str(target), content="new")

    assert target.read_text(encoding="utf-8") == "new"


def test_write_handles_unicode(tmp_path):
    sandbox = make_sandbox(tmp_path)
    target = sandbox / "u.txt"
    body = "naïve"

    result = write.handler(path=str(target), content=body)

    assert target.read_text(encoding="utf-8") == body
    assert result["byte_count"] == len(body.encode("utf-8"))


def test_input_schema_requires_path_and_content():
    with pytest.raises(SchemaError):
        validate({"path": "/a"}, write.INPUT_SCHEMA)
    with pytest.raises(SchemaError):
        validate({"content": "x"}, write.INPUT_SCHEMA)


def test_input_schema_rejects_extra_kwargs():
    with pytest.raises(SchemaError):
        validate(
            {"path": "/a", "content": "x", "mode": "w"},
            write.INPUT_SCHEMA,
        )


def test_input_schema_accepts_path_and_content():
    validate({"path": "/a", "content": "x"}, write.INPUT_SCHEMA)
