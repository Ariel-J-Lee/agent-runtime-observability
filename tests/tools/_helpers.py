"""Shared helpers for the v1 tool test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


SAMPLE_CORPUS: Mapping[str, str] = {
    "doc-alpha": "Alpha is the first letter of the Greek alphabet.",
    "doc-beta": "Beta follows alpha. Both are Greek letters.",
    "doc-gamma": "Gamma is the third Greek letter, used widely in physics.",
}


def make_sandbox(tmp_path: Path) -> Path:
    """Return a fresh sandbox dir under ``tmp_path`` for read/write tests."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    return sandbox


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
