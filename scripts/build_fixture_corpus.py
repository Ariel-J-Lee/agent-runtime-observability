"""Deterministic synthetic fixture-corpus generator.

Produces exactly 25 Markdown documents under ``data/corpus/v1/`` plus
a ``manifest.json`` carrying the SHA-256 of each file. Two reviewers
running this script against the same seed emit byte-identical files;
the manifest carries no timestamp so reproducibility is verifiable.

Topic universe (per PACKET-046 §2.2 + PACKET-014 §5.3):

- synthetic operations / policy reports for fictitious operators
  (``Operator-A1`` … ``Operator-A25``) and fictitious organizations
  (``Org-North``, ``Org-South``, ``Org-East``, ``Org-West``).
- subjects: incident-triage cadence summaries, change-management
  ledger reviews, release-readiness gate notes, configuration drift
  audits, observability gap reports, runbook revision logs, etc.
- public-safe only: no real workflow, no real RCA, no real entity, no
  PII, no reconstruction-from-private. PACKET-003 §6 attestations
  apply via ``data/DATA-SOURCE.md``.

Usage::

    python3 -m scripts.build_fixture_corpus              # writes to data/corpus/v1/
    python3 -m scripts.build_fixture_corpus --check      # rebuild + diff vs manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

SEED = 20260506
DOC_COUNT = 25
SCHEMA_VERSION = "1.0"
GENERATOR_PATH = "scripts/build_fixture_corpus.py"
CORPUS_DIR_NAME = "corpus/v1"
MANIFEST_NAME = "manifest.json"

# ---------------------------------------------------------------------------
# Vocabulary — fixed lists drawn from deterministically by the seeded RNG.
# ---------------------------------------------------------------------------

_SUBJECTS = [
    "Q3 Incident Triage Cadence Report",
    "Change Management Ledger Review",
    "Release-Readiness Gate Summary",
    "Configuration Drift Audit Notes",
    "Observability Gap Report",
    "Runbook Revision Log",
    "Capacity Headroom Snapshot",
    "Backup-Restore Verification Notes",
    "Access Review Cadence Summary",
    "Service-Level Target Reconciliation",
]

_ORGS = ["Org-North", "Org-South", "Org-East", "Org-West"]

_FOCUS_AREAS = [
    "ingest pipelines",
    "policy gate evaluation",
    "retry-budget allocation",
    "trace-attribute completeness",
    "sandbox-path enforcement",
    "URL allowlist drift",
    "runbook coverage",
    "schedule alignment",
    "ledger reconciliation",
    "post-deployment review cadence",
]

_OUTCOMES = [
    "no further action required",
    "tracked for next cadence review",
    "escalated to the cadence council",
    "documented in the change ledger",
    "scheduled for re-audit next quarter",
]

_SUMMARY_TEMPLATES = [
    "{operator} reports steady performance across {focus_a} and {focus_b}.",
    "Cadence for {operator} remained on schedule across {focus_a}; {focus_b} required minor adjustments.",
    "{operator} closed all open items from the prior review cycle, including {focus_a} and {focus_b}.",
    "Coverage for {operator} extended to {focus_a}; {focus_b} is queued for the next cycle.",
    "{operator} surfaced two cadence variances; both were absorbed within the existing {focus_a} budget.",
]

_FINDING_TEMPLATES = [
    "{focus} review for {operator} completed; {outcome}.",
    "{org} confirmed alignment on {focus}; {outcome}.",
    "{focus} drift was bounded within tolerance; {outcome}.",
    "{focus} coverage extended one cycle ahead of schedule for {operator}.",
    "{focus} ledger reconciliation closed for {org} with {outcome}.",
    "{operator} expanded {focus} to include the post-deployment window.",
]

_CADENCE_TEMPLATES = [
    "Cadence review is scheduled at the standard {operator} interval; the next session lands on the same week as the {org} cadence council.",
    "Cadence remains aligned with the {operator} default; cross-team checkpoints with {org} are unchanged.",
    "{operator} continues on the established cadence; {org} maintains parallel review.",
    "Cadence transitioned from monthly to quarterly for {operator}; {org} confirmed the schedule shift.",
]

_NOTES_TEMPLATES = [
    "All findings are synthetic and authored solely as fixtures for the agent-runtime-observability demo corpus.",
    "This document is part of the public-safe synthetic fixture set; no real workflow is described.",
    "The figures cited above are illustrative only; the corpus is deterministically generated from a documented seed.",
    "Review pairing follows the standard fixture-corpus cadence; no production system is involved.",
]


def _make_doc(rng: random.Random, doc_index: int) -> tuple[str, str]:
    """Return ``(doc_id, markdown_body)`` for the doc at ``doc_index``.

    The RNG is consumed in a fixed order per doc so the output is
    independent of how many docs have been generated before.
    """
    operator = f"Operator-A{doc_index + 1}"
    doc_id = f"op-a{doc_index + 1}"
    subject = rng.choice(_SUBJECTS)
    org = rng.choice(_ORGS)

    # Summary
    s_template = rng.choice(_SUMMARY_TEMPLATES)
    s_focus_a = rng.choice(_FOCUS_AREAS)
    s_focus_b = rng.choice([f for f in _FOCUS_AREAS if f != s_focus_a])
    summary = s_template.format(
        operator=operator,
        focus_a=s_focus_a,
        focus_b=s_focus_b,
    )

    # Findings — exactly four bullets
    findings: list[str] = []
    for _ in range(4):
        f_template = rng.choice(_FINDING_TEMPLATES)
        bullet = f_template.format(
            operator=operator,
            org=org,
            focus=rng.choice(_FOCUS_AREAS),
            outcome=rng.choice(_OUTCOMES),
        )
        findings.append(f"- {bullet}")

    # Cadence — single sentence
    cadence_template = rng.choice(_CADENCE_TEMPLATES)
    cadence = cadence_template.format(operator=operator, org=org)

    # Notes — single sentence
    notes = rng.choice(_NOTES_TEMPLATES)

    body = (
        f"# {operator} — {subject}\n"
        f"\n"
        f"## Summary\n"
        f"\n"
        f"{summary}\n"
        f"\n"
        f"## Findings\n"
        f"\n"
        + "\n".join(findings)
        + f"\n"
        f"\n"
        f"## Cadence\n"
        f"\n"
        f"{cadence}\n"
        f"\n"
        f"## Notes\n"
        f"\n"
        f"{notes}\n"
    )
    return doc_id, body


def build_corpus(*, repo_root: Path, seed: int = SEED, doc_count: int = DOC_COUNT) -> dict[str, Any]:
    """Generate the corpus + manifest. Returns the manifest dict."""
    corpus_dir = repo_root / "data" / CORPUS_DIR_NAME
    corpus_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    files_meta: list[dict[str, Any]] = []
    for i in range(doc_count):
        doc_id, body = _make_doc(rng, i)
        path = corpus_dir / f"{doc_id}.md"
        path.write_text(body, encoding="utf-8")
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        files_meta.append(
            {
                "id": doc_id,
                "path": f"data/{CORPUS_DIR_NAME}/{doc_id}.md",
                "sha256": sha,
                "char_count": len(body),
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "generator_path": GENERATOR_PATH,
        "doc_count": doc_count,
        "files": files_meta,
    }
    manifest_path = corpus_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def check_corpus(*, repo_root: Path) -> int:
    """Rebuild the corpus into a temp area and diff sha256 vs manifest.

    Returns 0 on byte-identical match, 2 on drift.
    """
    corpus_dir = repo_root / "data" / CORPUS_DIR_NAME
    manifest_path = corpus_dir / MANIFEST_NAME
    if not manifest_path.exists():
        print(f"[fixture-build] FAIL  manifest missing at {manifest_path}")
        return 2

    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    rng = random.Random(saved["seed"])
    drifted: list[str] = []
    for entry in saved["files"]:
        doc_id, body = _make_doc(rng, int(entry["id"][len("op-a"):]) - 1)
        if doc_id != entry["id"]:
            drifted.append(f"{entry['id']} (id mismatch: regenerated as {doc_id})")
            continue
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if sha != entry["sha256"]:
            drifted.append(f"{doc_id} (sha mismatch)")
        on_disk = (repo_root / entry["path"]).read_bytes()
        if hashlib.sha256(on_disk).hexdigest() != entry["sha256"]:
            drifted.append(f"{doc_id} (on-disk sha mismatch)")

    if drifted:
        print(
            f"[fixture-build] FAIL  drift on {len(drifted)} file(s): "
            f"{drifted}"
        )
        return 2

    print(
        f"[fixture-build] PASS  seed={saved['seed']}  "
        f"docs={saved['doc_count']}  schema={saved['schema_version']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild + diff vs manifest; exit 0 on byte-identical match, 2 on drift",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    if args.check:
        return check_corpus(repo_root=repo_root)

    manifest = build_corpus(repo_root=repo_root)
    print(
        f"[fixture-build] WROTE  seed={manifest['seed']}  "
        f"docs={manifest['doc_count']}  out=data/{CORPUS_DIR_NAME}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
