"""Sandbox-aware file write tool.

The v1 ``write`` tool creates parent directories and writes UTF-8
text. The policy ``sandbox_path`` rule is the load-bearing access
check; this tool boundary trusts the path has already been admitted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["path", "content"],
    "additionalProperties": False,
    "properties": {
        "path": {"type": "string", "minLength": 1},
        "content": {"type": "string"},
    },
}


def handler(*, path: str, content: str) -> dict[str, Any]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"path": str(p), "ok": True, "byte_count": len(content.encode("utf-8"))}


__all__ = ["INPUT_SCHEMA", "handler"]
