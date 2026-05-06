"""Tests for the deterministic fixture-corpus builder."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_fixture_corpus import (
    DOC_COUNT,
    SEED,
    SCHEMA_VERSION,
    build_corpus,
    check_corpus,
)


_CORPUS_DIR = _REPO_ROOT / "data" / "corpus" / "v1"
_MANIFEST_PATH = _CORPUS_DIR / "manifest.json"


def _load_manifest() -> dict:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_committed_corpus_matches_committed_manifest():
    """Every committed file's bytes must hash to the manifest's recorded sha."""
    manifest = _load_manifest()
    for entry in manifest["files"]:
        on_disk = (_REPO_ROOT / entry["path"]).read_bytes()
        sha = hashlib.sha256(on_disk).hexdigest()
        assert sha == entry["sha256"], f"drift on {entry['id']}"


def test_manifest_pins_seed_and_doc_count():
    manifest = _load_manifest()
    assert manifest["seed"] == SEED
    assert manifest["doc_count"] == DOC_COUNT
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["generator_path"] == "scripts/build_fixture_corpus.py"


def test_manifest_has_no_timestamp_field():
    """Reproducibility: two reviewers running the builder must emit
    byte-identical manifests, so the manifest must not record any
    build-time clock value."""
    manifest = _load_manifest()
    assert "generated_at" not in manifest
    assert "timestamp" not in manifest


def test_committed_corpus_has_exactly_25_doc_files():
    docs = sorted(p.name for p in _CORPUS_DIR.glob("op-a*.md"))
    assert len(docs) == 25
    expected = sorted(f"op-a{i}.md" for i in range(1, 26))
    assert docs == expected


def test_every_committed_doc_is_within_char_count_bounds():
    """Per PACKET-046 §2.2 the corpus is ~500-1500 chars per doc."""
    manifest = _load_manifest()
    for entry in manifest["files"]:
        body = (_REPO_ROOT / entry["path"]).read_text(encoding="utf-8")
        assert 500 <= len(body) <= 1500, (
            f"{entry['id']} char_count {len(body)} outside 500-1500 bound"
        )
        assert len(body) == entry["char_count"]


def test_builder_is_byte_deterministic_under_same_seed(tmp_path):
    """Rebuild into a temp area and assert sha matches the committed manifest."""
    fake_root = tmp_path / "repo"
    fake_root.mkdir()
    rebuilt = build_corpus(repo_root=fake_root, seed=SEED, doc_count=DOC_COUNT)

    committed = _load_manifest()

    assert rebuilt["seed"] == committed["seed"]
    assert rebuilt["doc_count"] == committed["doc_count"]
    assert rebuilt["schema_version"] == committed["schema_version"]
    by_id = {e["id"]: e for e in committed["files"]}
    for entry in rebuilt["files"]:
        assert entry["sha256"] == by_id[entry["id"]]["sha256"], (
            f"non-deterministic regen on {entry['id']}"
        )


def test_check_corpus_returns_zero_against_committed_state():
    rc = check_corpus(repo_root=_REPO_ROOT)
    assert rc == 0


def test_committed_corpus_contains_no_obvious_pii_tokens():
    """Lightweight scan for common PII shapes; PACKET-003 §6.3 attestation."""
    manifest = _load_manifest()
    pii_substrings = ("@", " SSN ", " ssn ")
    for entry in manifest["files"]:
        body = (_REPO_ROOT / entry["path"]).read_text(encoding="utf-8")
        for needle in pii_substrings:
            assert needle not in body, (
                f"{entry['id']} contains PII-shaped token {needle!r}"
            )


def test_every_committed_doc_references_only_fictitious_entities():
    """Every doc must mention Operator-AN; no real-entity names should
    appear in the committed corpus per PACKET-014 §5.3."""
    manifest = _load_manifest()
    for entry in manifest["files"]:
        body = (_REPO_ROOT / entry["path"]).read_text(encoding="utf-8")
        op_index = entry["id"][len("op-a"):]
        assert f"Operator-A{op_index}" in body, (
            f"{entry['id']} does not reference its operator name"
        )
