"""Deterministic extractive-summarize tool.

The v1 ``summarize`` tool is a stub-safe extractive summarizer: it
splits the input text on sentence boundaries (``.``, ``!``, ``?``
followed by whitespace) and returns the first ``max_sentences`` joined
on single spaces. Pure stdlib, no LLM call, byte-identical output for
identical inputs. A later packet swaps in a local-LLM-backed
summarizer behind the same tool name and schema.
"""

from __future__ import annotations

import re
from typing import Any

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["text"],
    "additionalProperties": False,
    "properties": {
        "text": {"type": "string", "minLength": 1},
        "max_sentences": {"type": "integer", "minimum": 1, "maximum": 50},
    },
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def handler(*, text: str, max_sentences: int = 3) -> dict[str, Any]:
    sentences = [chunk.strip() for chunk in _SENTENCE_SPLIT.split(text.strip()) if chunk.strip()]
    summary = " ".join(sentences[:max_sentences])
    return {"summary": summary, "sentence_count": len(sentences)}


__all__ = ["INPUT_SCHEMA", "handler"]
