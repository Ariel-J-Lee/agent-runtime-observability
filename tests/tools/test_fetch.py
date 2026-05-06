"""Tests for the v1 ``fetch`` tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.runtime._schema import SchemaError, validate
from tools import fetch

from tests.tools._helpers import write_file


def test_fetch_reads_local_file_via_file_scheme(tmp_path):
    target = tmp_path / "doc.txt"
    write_file(target, "hello fetch")
    url = target.as_uri()  # file:///...

    result = fetch.handler(url=url)

    assert result["url"] == url
    assert result["body"] == "hello fetch"
    assert result["byte_count"] == len(b"hello fetch")


def test_fetch_rejects_non_file_scheme_with_unsupported_scheme_error():
    with pytest.raises(fetch.ToolUnsupportedSchemeError) as info:
        fetch.handler(url="https://evil.test/secret")
    assert info.value.scheme == "https"


def test_fetch_rejects_http_scheme():
    with pytest.raises(fetch.ToolUnsupportedSchemeError) as info:
        fetch.handler(url="http://anywhere.example/")
    assert info.value.scheme == "http"


def test_fetch_handles_unicode_body(tmp_path):
    target = tmp_path / "unicode.txt"
    body = "café, résumé, naïve — ☃"
    write_file(target, body)

    result = fetch.handler(url=target.as_uri())

    assert result["body"] == body
    assert result["byte_count"] == len(body.encode("utf-8"))


def test_input_schema_requires_url():
    with pytest.raises(SchemaError):
        validate({}, fetch.INPUT_SCHEMA)


def test_input_schema_rejects_extra_kwargs():
    with pytest.raises(SchemaError):
        validate({"url": "file:///x", "method": "POST"}, fetch.INPUT_SCHEMA)


def test_input_schema_accepts_url_only():
    validate({"url": "file:///x"}, fetch.INPUT_SCHEMA)
