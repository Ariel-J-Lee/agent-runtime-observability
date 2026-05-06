"""Single entry point for writing one captured run's four artifacts.

Reorders the call sites so that:

- ``trace.json`` is written from ``OtelJsonExporter.to_otlp_dict()``
  after normalizing in-repo absolute paths to a stable ``<repo>``
  token (so the artifact is reviewer-checkout-independent)
- ``state.jsonl`` is written from ``agent_result.records`` with the
  same normalization applied to each record's ``to_dict()`` output
- ``run_report.md`` is rendered from manifest + result + spans
- ``manifest.json`` is written last so ``wall_clock_seconds`` reflects
  the full emission

The path-normalization step is the load-bearing reproducibility fix
PM/QA caught on Pass 1: without it, the canonical run's ``state.jsonl``
captured the original local checkout's absolute prefix
(``/tmp/career-ops/agent-runtime-observability-shell/...``) so
re-emitting from a different checkout (``/tmp/aro-pr9/...``) drifted
on every line that referenced a corpus path or URL. Replacing the
in-repo absolute prefix with a stable ``<repo>`` token in the
captured artifacts keeps the run-as-recorded readable and stable
without changing what the agent actually executed.

The caller drives the agent run; this module owns the artifact layout
and the path normalization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.evidence.manifest import write_manifest
from src.evidence.run_report import render_run_report
from src.runtime.agent import AgentResult
from src.tracing.otel_exporter import OtelJsonExporter

REPO_TOKEN = "<repo>"


def normalize_in_repo_paths(value: Any, *, repo_root: Path) -> Any:
    """Recursively replace absolute in-repo paths with :data:`REPO_TOKEN`.

    Walks dicts, lists, and strings. Strings carrying the absolute
    repo prefix (``str(repo_root.resolve())``) get the prefix replaced
    with ``<repo>``. The ``file://<abs>`` URL form is handled first so
    URLs become ``file://<repo>/...`` rather than ``file://<repo>/...``
    being mangled to ``file:<repo>...``.

    Args:
        value: Arbitrary JSON-serializable value (dict / list / str /
            number / bool / None).
        repo_root: The repository root path to strip from any absolute
            path embedded in the value.
    """
    abs_root = str(repo_root.resolve())
    file_uri_prefix = f"file://{abs_root}"
    return _normalize(value, abs_root=abs_root, file_uri_prefix=file_uri_prefix)


def _normalize(value: Any, *, abs_root: str, file_uri_prefix: str) -> Any:
    if isinstance(value, dict):
        return {
            k: _normalize(v, abs_root=abs_root, file_uri_prefix=file_uri_prefix)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [
            _normalize(v, abs_root=abs_root, file_uri_prefix=file_uri_prefix)
            for v in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _normalize(v, abs_root=abs_root, file_uri_prefix=file_uri_prefix)
            for v in value
        )
    if isinstance(value, str):
        s = value
        # Order matters: replace the URL form first so the bare-path
        # replacement doesn't break the URL scheme prefix.
        s = s.replace(file_uri_prefix, f"file://{REPO_TOKEN}")
        s = s.replace(abs_root, REPO_TOKEN)
        return s
    return value


def write_state_jsonl(*, records, path: Path, repo_root: Path) -> None:
    """Write the per-step ledger as JSONL with in-repo paths normalized.

    Each line is the ``StateRecord.to_dict()`` output passed through
    :func:`normalize_in_repo_paths`; byte-identical across reviewer
    checkouts when the agent run itself is deterministic.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            normalized = normalize_in_repo_paths(record.to_dict(), repo_root=repo_root)
            f.write(json.dumps(normalized, ensure_ascii=False, sort_keys=False))
            f.write("\n")


def write_trace_json(*, exporter: OtelJsonExporter, path: Path, repo_root: Path) -> None:
    """Serialize the OTLP-subset trace with in-repo paths normalized."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = normalize_in_repo_paths(exporter.to_otlp_dict(), repo_root=repo_root)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def emit_run(
    *,
    run_dir: Path,
    repo_root: Path,
    agent_result: AgentResult,
    exporter: OtelJsonExporter,
    spans: Sequence[tuple[str, Mapping[str, Any]]],
    manifest: Mapping[str, Any],
    task_name: str,
    corpus_description: str,
) -> None:
    """Write all four PACKET-046 §3.1 artifacts to ``run_dir``.

    Args:
        run_dir: Directory to receive ``trace.json`` / ``state.jsonl``
            / ``run_report.md`` / ``manifest.json``.
        repo_root: Repository root used to normalize in-repo absolute
            paths in the captured trace and state. Reviewers running
            ``make canonical`` from a different checkout produce
            byte-identical artifacts because the absolute prefix
            collapses to the stable ``<repo>`` token.
        agent_result: The terminal :class:`AgentResult` from the run.
        exporter: The trace exporter that captured the run's spans.
        spans: List-captured spans the run-report renderer reads.
        manifest: The §3.7 reproducibility envelope dict.
        task_name: One-line task description for the run report.
        corpus_description: One-line corpus description for the report.
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    write_trace_json(exporter=exporter, path=run_dir / "trace.json", repo_root=repo_root)

    write_state_jsonl(
        records=agent_result.records,
        path=run_dir / "state.jsonl",
        repo_root=repo_root,
    )

    report_md = render_run_report(
        manifest=manifest,
        agent_result=agent_result,
        spans=spans,
        task_name=task_name,
        corpus_description=corpus_description,
    )
    (run_dir / "run_report.md").write_text(report_md, encoding="utf-8")

    write_manifest(manifest, run_dir / "manifest.json")


__all__ = [
    "REPO_TOKEN",
    "emit_run",
    "normalize_in_repo_paths",
    "write_state_jsonl",
    "write_trace_json",
]
