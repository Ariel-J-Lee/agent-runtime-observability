"""Captured-run emission helpers for ``agent-runtime-observability``.

Per PACKET-046 §3, every captured run produces four artifacts:

- ``trace.json`` — OTLP/JSON-subset trace
- ``state.jsonl`` — append-only ledger of agent steps
- ``run_report.md`` — recruiter-readable headline
- ``manifest.json`` — reproducibility envelope

This package factors the manifest-builder, run-report renderer, and
single-entry-point ``emit_run`` so the three captured-run emitters
(``scripts/run_canonical_smoke.py``, ``scripts/run_policy_gates.py``,
``scripts/run_failure_modes.py``) share one code path.
"""

from src.evidence.emit import (
    REPO_TOKEN,
    emit_run,
    normalize_in_repo_paths,
)
from src.evidence.manifest import (
    DETERMINISTIC_TIME_START_NS,
    EXCLUDED_FROM_REPRODUCIBILITY_DIFF,
    POLICY_VERSION_PREFIX_LEN,
    RUN_ID_DATE,
    RUN_ID_POLICY_PREFIX_LEN,
    compute_corpus_snapshot_id,
    compute_manifest,
    compute_policy_version,
    compute_run_id_policy_prefix,
    deterministic_time_source,
    sha256_bytes,
    sha256_file,
)
from src.evidence.run_report import render_run_report

__all__ = [
    "DETERMINISTIC_TIME_START_NS",
    "EXCLUDED_FROM_REPRODUCIBILITY_DIFF",
    "POLICY_VERSION_PREFIX_LEN",
    "REPO_TOKEN",
    "RUN_ID_DATE",
    "RUN_ID_POLICY_PREFIX_LEN",
    "compute_corpus_snapshot_id",
    "compute_manifest",
    "compute_policy_version",
    "compute_run_id_policy_prefix",
    "deterministic_time_source",
    "emit_run",
    "normalize_in_repo_paths",
    "render_run_report",
    "sha256_bytes",
    "sha256_file",
]
