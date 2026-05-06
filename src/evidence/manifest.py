"""Reproducibility-envelope helpers for captured runs.

PACKET-046 §3.7 binds the ``manifest.json`` shape to a fixed set of
keys:

- ``run_id`` — sortable identifier ``<YYYY-MM-DD>_<policy-sha-prefix>_<seed/suffix>``
- ``task_id`` — ``canonical | pg<N>_<slug> | <failure_mode>``
- ``corpus`` — ``{snapshot_id, source, doc_count, license_files}``
- ``policy`` — ``{spec_path, spec_sha256, version}``
- ``code`` — ``{git_sha, tracing_subset_schema_sha256}``
- ``llm`` — ``{execution_path, stub_script_path, stub_script_sha256}``
- ``seed`` — integer
- ``timestamp`` — ISO-8601
- ``wall_clock_seconds`` — float
- ``regression_baseline`` — boolean

Three keys are documented as inherently per-run-volatile and are
excluded when reviewers diff manifests for reproducibility:
``timestamp``, ``wall_clock_seconds``, and ``code.git_sha``. The other
fields are byte-identical across reruns against the same upstream
snapshot.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional

# PACKET-046 §3.2 — date component of the run-id format.
RUN_ID_DATE = "2026-05-06"

# PACKET-046 §3.7 ``policy.version`` is the SHA-256 prefix of
# ``policy/v1.yaml``. The runtime's :class:`PolicySpec` already pins
# this to 12 hex chars (``sha256(file_bytes)[:12]``); the manifest
# matches so reviewers see one consistent prefix on the
# ``policy_check`` span attribute and the manifest field. The
# canonical run-id uses an 8-hex prefix per PACKET-054 GO-direction
# lock #1; the two prefix lengths derive from the same full SHA-256.
POLICY_VERSION_PREFIX_LEN = 12
RUN_ID_POLICY_PREFIX_LEN = 8

# PACKET-054 GO-direction lock: deterministic exporter time source so
# ``trace.json`` is byte-identical across reruns.
DETERMINISTIC_TIME_START_NS = 1_746_489_600_000_000_000  # 2026-05-06 UTC midnight
DETERMINISTIC_TIME_STEP_NS = 1_000_000  # +1 ms per call

# Manifest fields that must NOT be diffed against the committed copy
# when verifying reproducibility (per PACKET-054 GO-direction lock #4).
EXCLUDED_FROM_REPRODUCIBILITY_DIFF: tuple[str, ...] = (
    "timestamp",
    "wall_clock_seconds",
    "code.git_sha",
)


def deterministic_time_source(*, start_ns: int = DETERMINISTIC_TIME_START_NS,
                              step_ns: int = DETERMINISTIC_TIME_STEP_NS):
    """Return a callable that emits a monotonic counter starting at ``start_ns``.

    Each invocation advances by ``step_ns``. Lockstep with the exporter
    so two reviewers running the same fixture against the same code
    produce byte-identical timestamps in the captured trace.
    """
    state = {"now": start_ns}

    def _now() -> int:
        value = state["now"]
        state["now"] += step_ns
        return value

    return _now


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def compute_policy_version(*, repo_root: Path) -> tuple[str, str]:
    """Return ``(policy_spec_sha256, policy_version_prefix)``.

    The prefix is :data:`POLICY_VERSION_PREFIX_LEN` (12) hex chars to
    match the runtime's ``PolicySpec.version`` length so manifest and
    trace span attribute carry one consistent prefix.
    """
    sha = sha256_file(repo_root / "policy" / "v1.yaml")
    return sha, sha[:POLICY_VERSION_PREFIX_LEN]


def compute_run_id_policy_prefix(*, repo_root: Path) -> str:
    """Return the 8-hex SHA-256 prefix used in the canonical run-id."""
    sha = sha256_file(repo_root / "policy" / "v1.yaml")
    return sha[:RUN_ID_POLICY_PREFIX_LEN]


def compute_corpus_snapshot_id(*, repo_root: Path) -> str:
    """Return the SHA-256 of the corpus manifest bytes.

    Per PACKET-054 GO-direction lock #9, the corpus snapshot id is the
    SHA-256 of ``data/corpus/v1/manifest.json`` — the corpus manifest
    already pins each doc's SHA-256, so this single hash recursively
    pins all 25 doc SHAs.
    """
    return sha256_file(repo_root / "data" / "corpus" / "v1" / "manifest.json")


def _capture_git_sha(repo_root: Path) -> str:
    """Capture ``git rev-parse HEAD`` at emit time. Returns ``"unknown"``
    when not in a git repo or when git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def compute_manifest(
    *,
    repo_root: Path,
    run_id: str,
    task_id: str,
    seed: int = 0,
    timestamp: str,
    wall_clock_seconds: float,
    execution_path: str = "stub",
    regression_baseline: bool = False,
    policy_version: Optional[str] = None,
) -> dict[str, Any]:
    """Return a fully-formed manifest dict matching PACKET-046 §3.7.

    Args:
        repo_root: Repo root used for filesystem-relative SHA-256 reads
            (corpus manifest, policy spec, tracing subset schema, stub
            LLM script).
        run_id: PACKET-046 §3.2 run-id (``<YYYY-MM-DD>_<policy-sha-prefix>_<suffix>``).
        task_id: ``canonical | pg<N>_<slug> | <failure_mode>``.
        seed: integer seed; canonical runs use 0 by default.
        timestamp: ISO-8601 string the caller has already formatted.
        wall_clock_seconds: float; per-run-volatile; excluded from
            reproducibility diffs.
        execution_path: ``stub`` (the canonical default) | ``local`` |
            ``hosted``.
        regression_baseline: tags the artifact as the baseline a future
            regression test will diff against.
        policy_version: When the run mutates the on-disk policy spec
            in-memory (the canonical run widens ``url_allowlist`` to
            admit ``file://`` URLs), the runtime ``PolicySpec`` carries
            a different ``version`` than the file SHA. Pass it here so
            ``manifest.policy.version`` matches the ``policy.version``
            attribute the runtime emits on every ``policy_check`` span.
            Defaults to the file-bytes prefix when omitted.
    """
    spec_sha, default_version = compute_policy_version(repo_root=repo_root)
    version = policy_version if policy_version is not None else default_version
    return {
        "run_id": run_id,
        "task_id": task_id,
        "corpus": {
            "snapshot_id": compute_corpus_snapshot_id(repo_root=repo_root),
            "source": "synthetic-fixture-corpus",
            "doc_count": 25,
            "license_files": ["data/LICENSE.fixture-corpus"],
        },
        "policy": {
            "spec_path": "policy/v1.yaml",
            "spec_sha256": spec_sha,
            "version": version,
        },
        "code": {
            "git_sha": _capture_git_sha(repo_root),
            "tracing_subset_schema_sha256": sha256_file(
                repo_root / "src" / "tracing" / "otlp_subset_schema.py"
            ),
        },
        "llm": {
            "execution_path": execution_path,
            "stub_script_path": "src/runtime/stub_llm/canned.py",
            "stub_script_sha256": sha256_file(
                repo_root / "src" / "runtime" / "stub_llm" / "canned.py"
            ),
        },
        "seed": seed,
        "timestamp": timestamp,
        "wall_clock_seconds": wall_clock_seconds,
        "regression_baseline": regression_baseline,
    }


def write_manifest(manifest: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "DETERMINISTIC_TIME_START_NS",
    "DETERMINISTIC_TIME_STEP_NS",
    "EXCLUDED_FROM_REPRODUCIBILITY_DIFF",
    "POLICY_VERSION_PREFIX_LEN",
    "RUN_ID_DATE",
    "RUN_ID_POLICY_PREFIX_LEN",
    "compute_corpus_snapshot_id",
    "compute_manifest",
    "compute_policy_version",
    "compute_run_id_policy_prefix",
    "deterministic_time_source",
    "sha256_bytes",
    "sha256_file",
    "write_manifest",
]
