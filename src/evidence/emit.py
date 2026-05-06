"""Single entry point for writing one captured run's four artifacts.

Reorders the call sites so that:

- ``trace.json`` is written via ``OtelJsonExporter.write``
- ``state.jsonl`` is written from ``agent_result.records``
- ``run_report.md`` is rendered from manifest + result + spans
- ``manifest.json`` is written last so ``wall_clock_seconds`` reflects
  the full emission

The caller drives the agent run; this module owns the artifact layout.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.evidence.manifest import write_manifest
from src.evidence.run_report import render_run_report
from src.runtime.agent import AgentResult
from src.tracing.otel_exporter import OtelJsonExporter


def write_state_jsonl(*, records, path: Path) -> None:
    """Write the per-step ledger as JSONL.

    Each line is the ``StateRecord.to_dict()`` output, byte-identical
    across reruns when records are deterministic.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=False))
            f.write("\n")


def emit_run(
    *,
    run_dir: Path,
    agent_result: AgentResult,
    exporter: OtelJsonExporter,
    spans: Sequence[tuple[str, Mapping[str, Any]]],
    manifest: Mapping[str, Any],
    task_name: str,
    corpus_description: str,
) -> None:
    """Write all four PACKET-046 §3.1 artifacts to ``run_dir``."""
    run_dir.mkdir(parents=True, exist_ok=True)

    exporter.write(run_dir / "trace.json")

    write_state_jsonl(records=agent_result.records, path=run_dir / "state.jsonl")

    report_md = render_run_report(
        manifest=manifest,
        agent_result=agent_result,
        spans=spans,
        task_name=task_name,
        corpus_description=corpus_description,
    )
    (run_dir / "run_report.md").write_text(report_md, encoding="utf-8")

    write_manifest(manifest, run_dir / "manifest.json")


__all__ = ["emit_run", "write_state_jsonl"]
