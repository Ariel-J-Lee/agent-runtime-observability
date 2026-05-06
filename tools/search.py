"""Local-corpus search tool.

The v1 ``search`` tool returns candidate document IDs against a caller-
injected corpus mapping. It is intentionally pure-stdlib and
deterministic:

- Match: case-insensitive substring of the query against each document
  body.
- Order: matches are returned sorted by document ID so two reruns
  against the same corpus produce byte-identical output.
- Bound: the optional ``top_k`` argument caps the result list length
  (default 5, max 50).

The corpus is **not** an LLM-supplied argument. Callers wire it at
construction time via :func:`make_handler`. The canonical 25-document
corpus arrives in a later T-FIXTURES packet; this slice ships no
corpus file, only the tool surface that consumes one.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["query"],
    "additionalProperties": False,
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 50},
    },
}


def make_handler(*, corpus: Mapping[str, str]) -> Callable[..., dict[str, Any]]:
    """Return a ``search`` callable bound to ``corpus``.

    The returned callable matches the runtime's tool-handler shape
    (kwargs only, returns a JSON-serializable dict) and walks
    ``corpus`` once per call.
    """
    bound = dict(corpus)

    def _search(*, query: str, top_k: int = 5) -> dict[str, Any]:
        needle = query.lower()
        hits = [doc_id for doc_id, body in bound.items() if needle in body.lower()]
        hits.sort()
        return {"hits": hits[:top_k], "match_count": len(hits)}

    return _search


__all__ = ["INPUT_SCHEMA", "make_handler"]
