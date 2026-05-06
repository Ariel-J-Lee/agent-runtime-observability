"""Local canonical-task smoke runner + evidence emitter.

Drives the canonical task fixture (``tasks/canonical/v1.json``) through
a real :class:`Agent.run` against:

- the deterministic 25-document fixture corpus at ``data/corpus/v1/``
- the real v1 tool layer (``tools.default_registry``)
- ``PolicyChecker(arg_schema_enforcement="strict",
  tool_schemas=tools.TOOL_SCHEMAS)`` with a per-run ``url_allowlist``
  widened in-process to admit ``file://`` URLs (canonical
  ``policy/v1.yaml`` stays untouched on disk)
- the deterministic stub LLM at ``src.runtime.stub_llm.canned``
- ``sandbox_root = data/corpus/v1/`` so the canonical ``read`` step
  passes the ``sandbox_path`` policy gate

Three modes:

- ``python3 -m scripts.run_canonical_smoke`` — local PASS/FAIL smoke;
  no disk writes (matches PACKET-053 behavior).
- ``python3 -m scripts.run_canonical_smoke --emit`` — writes the four
  PACKET-046 §3.1 artifacts to ``runs/<canonical-run-id>/`` (the
  T-EVIDENCE captured-run path).
- ``python3 -m scripts.run_canonical_smoke --check`` — re-emits into
  a tmp area and diffs ``trace.json`` / ``state.jsonl`` /
  ``run_report.md`` byte-identically against the committed copy
  (manifest fields ``timestamp`` / ``wall_clock_seconds`` /
  ``code.git_sha`` are documented as per-run-volatile and excluded).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.evidence import (
    EXCLUDED_FROM_REPRODUCIBILITY_DIFF,
    RUN_ID_DATE,
    compute_manifest,
    compute_run_id_policy_prefix,
    deterministic_time_source,
    emit_run,
)
from src.runtime import (
    Agent,
    PolicyChecker,
    PolicySpec,
    make_canned_llm,
)
from src.tracing import new_exporter
from tools import TOOL_SCHEMAS, default_registry


_CANONICAL_FIXTURE = _REPO_ROOT / "tasks" / "canonical" / "v1.json"
_CORPUS_DIR = _REPO_ROOT / "data" / "corpus" / "v1"
_POLICY_YAML = _REPO_ROOT / "policy" / "v1.yaml"
_RUNS_DIR = _REPO_ROOT / "runs"
_DETERMINISTIC_TIMESTAMP = "2026-05-06T00:00:00Z"
_DETERMINISTIC_WALL_CLOCK_SECONDS = 0.0


def _load_corpus_dict() -> dict[str, str]:
    return {
        p.stem: p.read_text(encoding="utf-8")
        for p in sorted(_CORPUS_DIR.glob("op-a*.md"))
    }


def _substitute_templates(value, *, corpus_dir: Path):
    if isinstance(value, dict):
        return {k: _substitute_templates(v, corpus_dir=corpus_dir) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_templates(v, corpus_dir=corpus_dir) for v in value]
    if isinstance(value, str):
        s = value
        if "{{corpus_url:" in s:
            for doc_id in (p.stem for p in corpus_dir.glob("op-a*.md")):
                s = s.replace(
                    "{{corpus_url:" + doc_id + "}}",
                    (corpus_dir / f"{doc_id}.md").as_uri(),
                )
        if "{{corpus_path:" in s:
            for doc_id in (p.stem for p in corpus_dir.glob("op-a*.md")):
                s = s.replace(
                    "{{corpus_path:" + doc_id + "}}",
                    str(corpus_dir / f"{doc_id}.md"),
                )
        return s
    return value


def _build_run(*, with_exporter: bool, run_id: str | None = None):
    """Drive the canonical task and return ``(result, spans, exporter)``.

    When ``with_exporter`` is True, the OTel exporter is wired with a
    deterministic time source so ``trace.json`` is byte-identical
    across reruns. When False, no exporter is constructed.
    """
    fixture = json.loads(_CANONICAL_FIXTURE.read_text(encoding="utf-8"))
    corpus = _load_corpus_dict()
    if not corpus:
        raise SystemExit(
            f"corpus empty at {_CORPUS_DIR}; run `make fixture-build` first"
        )

    canned = _substitute_templates(
        copy.deepcopy(fixture["canned_llm_tool_calls"]),
        corpus_dir=_CORPUS_DIR,
    )

    raw = copy.deepcopy(PolicySpec.from_yaml_path(_POLICY_YAML).raw)
    raw["url_allowlist"] = list(raw.get("url_allowlist", [])) + [""]
    spec = PolicySpec.from_dict(raw)

    checker = PolicyChecker(
        spec,
        tool_schemas=TOOL_SCHEMAS,
        sandbox_root=_CORPUS_DIR.resolve(),
    )

    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class, attrs):
        spans.append((span_class, dict(attrs)))

    if with_exporter:
        exporter = new_exporter(seed=0, time_source=deterministic_time_source())

        def _both(span_class, attrs):
            exporter(span_class, attrs)
            _recorder(span_class, attrs)

        recorder = _both
    else:
        exporter = None
        recorder = _recorder

    agent = Agent(
        llm=make_canned_llm(
            canned,
            default_final_answer=fixture["canned_llm_tool_calls"][-1].get("final_answer"),
        ),
        tool_registry=default_registry(corpus=corpus),
        policy_checker=checker,
        span_recorder=recorder,
    )

    result = agent.run(fixture["question"], run_id=run_id)
    return fixture, corpus, result, spans, exporter, spec


def _smoke_assertions(fixture, result, spans) -> int:
    denies = [
        attrs.get("agent.policy.rule_id")
        for cls, attrs in spans
        if cls == "policy_check" and attrs.get("agent.policy.decision") == "deny"
    ]
    if denies:
        print(f"[canonical] FAIL  unexpected policy denials: {denies}")
        return 2

    failure_modes = [r.failure_mode for r in result.records if r.failure_mode]
    if failure_modes:
        print(f"[canonical] FAIL  classified failure modes: {failure_modes}")
        return 2

    if result.terminal_reason != "final_answer":
        print(
            f"[canonical] FAIL  terminal_reason={result.terminal_reason!r} "
            "(expected final_answer)"
        )
        return 2

    tool_calls = [
        attrs.get("agent.tool_name")
        for cls, attrs in spans
        if cls == "tool_call"
    ]
    expected_seq = fixture["expected"]["tool_call_sequence"]
    if tool_calls != expected_seq:
        print(
            f"[canonical] FAIL  tool_call sequence {tool_calls!r} "
            f"!= expected {expected_seq!r}"
        )
        return 2
    return 0


def _resolve_canonical_run_dir() -> tuple[str, Path]:
    prefix = compute_run_id_policy_prefix(repo_root=_REPO_ROOT)
    run_id = f"{RUN_ID_DATE}_{prefix}_0"
    return run_id, _RUNS_DIR / run_id


def _emit(*, out_root: Path | None = None) -> int:
    run_id, default_dir = _resolve_canonical_run_dir()
    fixture, corpus, result, spans, exporter, spec = _build_run(with_exporter=True, run_id=run_id)
    rc = _smoke_assertions(fixture, result, spans)
    if rc != 0:
        return rc

    target = (out_root / run_id) if out_root is not None else default_dir
    manifest = compute_manifest(
        repo_root=_REPO_ROOT,
        run_id=run_id,
        task_id="canonical",
        seed=0,
        timestamp=_DETERMINISTIC_TIMESTAMP,
        wall_clock_seconds=_DETERMINISTIC_WALL_CLOCK_SECONDS,
        policy_version=spec.version,
    )

    emit_run(
        run_dir=target,
        repo_root=_REPO_ROOT,
        agent_result=result,
        exporter=exporter,
        spans=spans,
        manifest=manifest,
        task_name=fixture.get("question", "canonical"),
        corpus_description=(
            "Synthetic 25-document corpus at data/corpus/v1/ "
            "(seed 20260506; CC0-1.0; PACKET-053 fixture)"
        ),
    )
    print(
        f"[canonical] WROTE  run_id={run_id}  "
        f"out={target.relative_to(_REPO_ROOT) if target.is_relative_to(_REPO_ROOT) else target}"
    )
    return 0


def _drop_dotted(d: dict, dotted: str) -> None:
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        cur = cur[p]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _check() -> int:
    run_id, committed_dir = _resolve_canonical_run_dir()
    if not committed_dir.exists():
        print(f"[canonical] FAIL  no committed run at {committed_dir}; "
              "run `make canonical` to emit one first")
        return 2
    drift: list[str] = []
    with tempfile.TemporaryDirectory() as raw:
        rc = _emit(out_root=Path(raw))
        if rc != 0:
            return rc
        tmp_dir = Path(raw) / run_id
        for filename in ("trace.json", "state.jsonl", "run_report.md"):
            fresh = (tmp_dir / filename).read_bytes()
            committed = (committed_dir / filename).read_bytes()
            if fresh != committed:
                drift.append(filename)
        fresh_manifest = json.loads((tmp_dir / "manifest.json").read_text())
        committed_manifest = json.loads((committed_dir / "manifest.json").read_text())
        for key in EXCLUDED_FROM_REPRODUCIBILITY_DIFF:
            _drop_dotted(fresh_manifest, key)
            _drop_dotted(committed_manifest, key)
        if fresh_manifest != committed_manifest:
            drift.append("manifest.json (excluding volatile keys)")

    if drift:
        print(f"[canonical] FAIL  drift on {len(drift)} file(s): {drift}")
        return 2
    print(f"[canonical] PASS  byte-identical re-emission against committed run {run_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.run_canonical_smoke",
        description="Local canonical-task smoke + evidence emitter.",
    )
    parser.add_argument(
        "--emit",
        action="store_true",
        help="Write the four PACKET-046 §3.1 artifacts to runs/<canonical-run-id>/",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Re-emit into a tmp area and diff vs the committed canonical run",
    )
    args = parser.parse_args(argv)

    if args.check:
        return _check()
    if args.emit:
        return _emit()

    fixture, corpus, result, spans, _, _ = _build_run(with_exporter=False)
    rc = _smoke_assertions(fixture, result, spans)
    if rc != 0:
        return rc
    tool_calls = [
        attrs.get("agent.tool_name")
        for cls, attrs in spans
        if cls == "tool_call"
    ]
    print(
        f"[canonical] PASS  steps={result.step_count}  "
        f"terminal={result.terminal_reason}  tools={len(tool_calls)}  "
        f"corpus_docs={len(corpus)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
