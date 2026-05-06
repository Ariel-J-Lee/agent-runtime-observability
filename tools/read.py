"""Sandbox-aware file read tool.

The v1 ``read`` tool loads a UTF-8 text file from a caller-supplied
path. The policy ``sandbox_path`` rule is the load-bearing access
check (it canonicalizes the path with ``os.path.realpath`` before
admitting the call); this tool boundary trusts that any path it
receives has already been admitted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["path"],
    "additionalProperties": False,
    "properties": {
        "path": {"type": "string", "minLength": 1},
    },
}


def handler(*, path: str) -> dict[str, Any]:
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    return {"path": str(p), "content": content, "byte_count": len(content.encode("utf-8"))}


__all__ = ["INPUT_SCHEMA", "handler"]
