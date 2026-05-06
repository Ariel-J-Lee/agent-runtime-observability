"""Reproducibility-envelope tests for committed evidence runs.

PACKET-046 §1.3 #4 binds: "Two reviewers running the emitter against
the same upstream snapshot produce byte-identical ``trace.json``
(verified by ``sha256`` per file)." PACKET-054 GO-direction extends
the contract to ``state.jsonl`` and ``run_report.md``; ``manifest.json``
is byte-identical except on three documented per-run-volatile keys
(``timestamp``, ``wall_clock_seconds``, ``code.git_sha``).

This suite re-runs each emitter against a temp output directory and
asserts byte-identical match with the committed copy.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.evidence import EXCLUDED_FROM_REPRODUCIBILITY_DIFF
from scripts.run_canonical_smoke import _build_run as _build_canonical_run
from scripts.run_canonical_smoke import _resolve_canonical_run_dir
from scripts.run_canonical_smoke import _emit as _emit_canonical
from scripts.run_failure_modes import _emit_one as _emit_fm
from scripts.run_failure_modes import _list_scenarios as _list_fm_scenarios
from scripts.run_policy_gates import _emit_one as _emit_pg
from scripts.run_policy_gates import _list_scenarios as _list_pg_scenarios

_RUNS_DIR = _REPO_ROOT / "runs"


def _drop_dotted(d: dict, dotted: str) -> None:
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        cur = cur[p]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _diff_run(*, fresh_dir: Path, committed_dir: Path) -> list[str]:
    drift: list[str] = []
    for filename in ("trace.json", "state.jsonl", "run_report.md"):
        fresh = (fresh_dir / filename).read_bytes()
        committed = (committed_dir / filename).read_bytes()
        if fresh != committed:
            drift.append(filename)
    fresh_manifest = json.loads((fresh_dir / "manifest.json").read_text())
    committed_manifest = json.loads((committed_dir / "manifest.json").read_text())
    for key in EXCLUDED_FROM_REPRODUCIBILITY_DIFF:
        _drop_dotted(fresh_manifest, key)
        _drop_dotted(committed_manifest, key)
    if fresh_manifest != committed_manifest:
        drift.append("manifest.json (excluding volatile keys)")
    return drift


def test_canonical_run_re_emits_byte_identically():
    run_id, committed_dir = _resolve_canonical_run_dir()
    assert committed_dir.exists(), (
        f"no committed canonical run at {committed_dir}; "
        "run `make canonical` to emit one first"
    )
    with tempfile.TemporaryDirectory() as raw:
        rc = _emit_canonical(out_root=Path(raw))
        assert rc == 0
        fresh_dir = Path(raw) / run_id
        drift = _diff_run(fresh_dir=fresh_dir, committed_dir=committed_dir)
    assert not drift, f"canonical run drift: {drift}"


@pytest.mark.parametrize("scenario", _list_pg_scenarios())
def test_policy_gate_run_re_emits_byte_identically(scenario: str):
    committed_dir = _RUNS_DIR / "policy_gates" / scenario
    assert committed_dir.exists(), (
        f"no committed policy-gate run at {committed_dir}; "
        "run `make policy-gates` to emit"
    )
    with tempfile.TemporaryDirectory() as raw:
        fresh_dir = _emit_pg(scenario=scenario, out_root=Path(raw))
        drift = _diff_run(fresh_dir=fresh_dir, committed_dir=committed_dir)
    assert not drift, f"{scenario} drift: {drift}"


@pytest.mark.parametrize("scenario", _list_fm_scenarios())
def test_failure_mode_run_re_emits_byte_identically(scenario: str):
    committed_dir = _RUNS_DIR / "failure_modes" / scenario
    assert committed_dir.exists(), (
        f"no committed failure-mode run at {committed_dir}; "
        "run `make failure-modes` to emit"
    )
    with tempfile.TemporaryDirectory() as raw:
        fresh_dir = _emit_fm(scenario=scenario, out_root=Path(raw))
        drift = _diff_run(fresh_dir=fresh_dir, committed_dir=committed_dir)
    assert not drift, f"{scenario} drift: {drift}"


def test_excluded_keys_list_matches_locked_set():
    """The set of per-run-volatile manifest keys is a documented
    contract; locking it here so a future slice can't silently widen
    or narrow the exclusion list."""
    assert set(EXCLUDED_FROM_REPRODUCIBILITY_DIFF) == {
        "timestamp",
        "wall_clock_seconds",
        "code.git_sha",
    }
