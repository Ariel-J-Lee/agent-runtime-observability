"""Local-first URL fetch tool.

The v1 ``fetch`` tool retrieves the body at a URL. At this slice the
transport is pure stdlib (``urllib.request``) and constrained to the
``file://`` scheme; non-``file://`` URLs raise
:class:`ToolUnsupportedSchemeError` so the tool boundary defends
against any URL the policy gate would have denied. The policy
``url_allowlist`` rule is the load-bearing access check; this tool
boundary is a defense-in-depth backstop.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from typing import Any

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["url"],
    "additionalProperties": False,
    "properties": {
        "url": {"type": "string", "minLength": 1},
    },
}

_ALLOWED_SCHEMES = ("file",)


class ToolUnsupportedSchemeError(ValueError):
    """Raised when ``fetch`` is invoked against a non-``file://`` URL.

    The policy ``url_allowlist`` rule is expected to deny these calls
    upstream; this exception fires only when policy is permissive (e.g.
    in a unit test) but the tool itself is still asked to reach the
    network. Always failing closed at the tool boundary keeps the v1
    surface laptop-runnable and offline-by-default.
    """

    def __init__(self, scheme: str) -> None:
        super().__init__(
            f"fetch only supports {_ALLOWED_SCHEMES!r} URLs at v1; got scheme={scheme!r}"
        )
        self.scheme = scheme


def handler(*, url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ToolUnsupportedSchemeError(scheme=parsed.scheme)
    with urllib.request.urlopen(url) as response:
        body = response.read().decode("utf-8")
    return {"url": url, "body": body, "byte_count": len(body.encode("utf-8"))}


__all__ = ["INPUT_SCHEMA", "ToolUnsupportedSchemeError", "handler"]
