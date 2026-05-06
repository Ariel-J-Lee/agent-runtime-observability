"""v1 tool layer for ``agent-runtime-observability``.

Five tools, each a pure-stdlib callable matching the runtime's
``tool_registry`` shape (``kwargs -> dict``):

- :mod:`tools.search` — local-corpus substring search (corpus is
  caller-injected; no corpus file ships at this slice).
- :mod:`tools.fetch` — ``file://`` URL fetch via stdlib
  ``urllib.request``; non-``file://`` schemes raise.
- :mod:`tools.read` — UTF-8 file read.
- :mod:`tools.write` — UTF-8 file write (creates parent dirs).
- :mod:`tools.summarize` — deterministic extractive summary.

Each tool module exports an ``INPUT_SCHEMA`` declaring the kwargs the
LLM is allowed to supply. :data:`TOOL_SCHEMAS` aggregates those for
``PolicyChecker(tool_schemas=...)``. :func:`default_registry` returns
a ``tool_registry`` mapping ready to pass as ``Agent(tool_registry=...)``;
``search`` requires an injected corpus and is the only tool that
needs construction-time wiring at v1.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from . import fetch as fetch
from . import read as read
from . import search as search
from . import summarize as summarize
from . import write as write

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search": search.INPUT_SCHEMA,
    "fetch": fetch.INPUT_SCHEMA,
    "read": read.INPUT_SCHEMA,
    "write": write.INPUT_SCHEMA,
    "summarize": summarize.INPUT_SCHEMA,
}


def default_registry(
    *,
    corpus: Optional[Mapping[str, str]] = None,
) -> dict[str, Callable[..., Any]]:
    """Return a ``tool_registry`` populated with the five v1 tools.

    Args:
        corpus: Document corpus for ``search``. Defaults to an empty
            mapping; ``search`` will then return zero hits for every
            query. T-FIXTURES later ships a canonical 25-document
            corpus the harness wires through this argument.
    """
    return {
        "search": search.make_handler(corpus=corpus or {}),
        "fetch": fetch.handler,
        "read": read.handler,
        "write": write.handler,
        "summarize": summarize.handler,
    }


__all__ = [
    "TOOL_SCHEMAS",
    "default_registry",
    "fetch",
    "read",
    "search",
    "summarize",
    "write",
]
