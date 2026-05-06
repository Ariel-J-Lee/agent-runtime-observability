"""Lock the cross-link between trace ``policy.version`` and manifest.

PACKET-046 §3.3 says every ``policy_check`` span carries
``policy.version`` (the SHA-256 prefix of ``policy/v1.yaml``).
PACKET-046 §3.7 records the same prefix in ``manifest.json#/policy/version``.
A reviewer mapping a deny event back to the rule that fired it should
see one consistent prefix throughout the captured artifacts.

This suite walks every committed run, extracts the ``policy.version``
attribute from every ``policy_check`` span in ``trace.json``, and
asserts they all match the manifest's ``policy.version``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_RUNS_DIR = _REPO_ROOT / "runs"


def _committed_run_dirs() -> list[Path]:
    out: list[Path] = []
    for p in sorted(_RUNS_DIR.iterdir()):
        if p.is_dir() and p.name not in ("policy_gates", "failure_modes"):
            out.append(p)
    for sub in ("policy_gates", "failure_modes"):
        sub_dir = _RUNS_DIR / sub
        if sub_dir.is_dir():
            out.extend(sorted(p for p in sub_dir.iterdir() if p.is_dir()))
    return out


def _policy_versions_in_trace(trace: dict) -> set[str]:
    versions: set[str] = set()
    for rs in trace.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for span in ss.get("spans", []):
                if span.get("name") != "policy_check":
                    continue
                for attr in span.get("attributes", []):
                    if attr.get("key") == "policy.version":
                        v = attr.get("value", {}).get("stringValue")
                        if v is not None:
                            versions.add(v)
    return versions


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_trace_policy_version_matches_manifest(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    trace = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))
    expected = manifest["policy"]["version"]
    in_trace = _policy_versions_in_trace(trace)
    assert in_trace, (
        f"{run_dir.name}: no policy_check span carries policy.version"
    )
    assert in_trace == {expected}, (
        f"{run_dir.name}: trace policy.version {in_trace!r} "
        f"!= manifest.policy.version {expected!r}"
    )


def test_canonical_run_id_matches_directory_name():
    """The canonical directory name is the canonical run-id (PACKET-046 §3.2)."""
    canonicals = [p for p in _committed_run_dirs() if p.parent == _RUNS_DIR]
    assert len(canonicals) == 1
    run_dir = canonicals[0]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == run_dir.name


def test_canonical_run_id_format_matches_packet_046_3_2():
    """``<YYYY-MM-DD>_<8-hex-policy-sha-prefix>_<seed>`` per PACKET-054 GO-direction lock #1.

    The 8-hex prefix is computed from the on-disk ``policy/v1.yaml``
    file SHA-256 (so the run-id is stable against changes to the
    in-memory widening). The trace's ``policy.version`` and the
    manifest's ``policy.version`` carry the 12-hex version of the
    in-memory spec; the run-id and the manifest's ``policy.version``
    legitimately use different prefix lengths from related sources.
    """
    canonicals = [p for p in _committed_run_dirs() if p.parent == _RUNS_DIR]
    run_id = canonicals[0].name
    parts = run_id.split("_")
    assert len(parts) == 3, f"expected 3 underscored parts; got {parts!r}"
    date_part, sha_part, seed_part = parts
    assert len(date_part) == len("YYYY-MM-DD")
    assert len(sha_part) == 8
    assert seed_part.lstrip("-").isdigit()
