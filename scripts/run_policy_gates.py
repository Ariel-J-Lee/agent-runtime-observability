"""Captured-run emitter for the five policy-gate scenarios.

Walks each fixture under ``tasks/policy_gates/``, drives it through a
real :class:`Agent.run` against ``policy/v1.yaml`` with the
test-stub tool registry + tool schemas (PG fixtures expect denials,
not real tool execution), captures the trace via the OTel exporter,
and emits the four PACKET-046 §3.1 artifacts to
``runs/policy_gates/<slug>/``.

Usage::

    make policy-gates                                 # emit every PG run
    make policy-gates SCENARIO=pg1_off_allowlist_url  # emit one
    python3 -m scripts.run_policy_gates --check       # diff vs committed

The ``--check`` flag re-emits every run into a temp area and asserts
``trace.json`` + ``state.jsonl`` + ``run_report.md`` are byte-identical
to the committed copies (matching the PACKET-054 reproducibility
contract). Exits 0 on byte-identical match, 2 on drift.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
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
from src.runtime import Agent, PolicyChecker, PolicySpec, StateLedger
from src.tracing import new_exporter

from tests.policy_gates._stubs import (
    STUB_TOOL_REGISTRY,
    STUB_TOOL_SCHEMAS,
    make_canned_llm,
)

_FIXTURE_DIR = _REPO_ROOT / "tasks" / "policy_gates"
_RUNS_DIR = _REPO_ROOT / "runs" / "policy_gates"
_DETERMINISTIC_TIMESTAMP = "2026-05-06T00:00:00Z"
_DETERMINISTIC_WALL_CLOCK_SECONDS = 0.0

# Deterministic sandbox root for evidence emission. The trace records
# ``policy.sandbox_root`` on sandbox-escape denials, so this path must
# be stable across reruns; ``tempfile.TemporaryDirectory()`` produces
# a random suffix that would surface as drift in the captured trace.
# The path is fixed and the directory is created lazily on first use;
# nothing under the path is read or written aside from the directory
# entry itself (the policy gate denies before any file operation).
_DETERMINISTIC_SANDBOX_ROOT = Path("/tmp/agent-runtime-observability-evidence-sandbox")


def _list_scenarios() -> list[str]:
    return sorted(p.stem for p in _FIXTURE_DIR.glob("pg*.json"))


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _resolve_sandbox_root(fixture: dict) -> Path | None:
    if fixture.get("sandbox_root_setup") != "default":
        return None
    _DETERMINISTIC_SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    return _DETERMINISTIC_SANDBOX_ROOT.resolve()


def _emit_one(*, scenario: str, out_root: Path,
              deterministic_timestamp: str | None = None,
              deterministic_wall_clock: float | None = None) -> Path:
    """Emit one policy-gate run; returns the run dir."""
    fixture = _load_fixture(scenario)
    spec = PolicySpec.from_yaml_path(_REPO_ROOT / "policy" / "v1.yaml")
    sandbox_root = _resolve_sandbox_root(fixture)

    checker = PolicyChecker(
        spec,
        sandbox_root=sandbox_root,
        tool_schemas=STUB_TOOL_SCHEMAS,
    )

    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class: str, attrs):
        spans.append((span_class, dict(attrs)))

    exporter = new_exporter(seed=0, time_source=deterministic_time_source())
    # Wrap the recorder so the trace exporter captures every span; the
    # local ``spans`` list also captures for run_report.md.
    def _both(span_class: str, attrs):
        exporter(span_class, attrs)
        _recorder(span_class, attrs)

    max_iterations = int(spec.get("loop_budget.max_iterations", 10))
    agent = Agent(
        llm=make_canned_llm(fixture["canned_llm_tool_calls"]),
        tool_registry=STUB_TOOL_REGISTRY,
        policy_checker=checker,
        span_recorder=_both,
        max_iterations=max_iterations,
    )

    prefix = compute_run_id_policy_prefix(repo_root=_REPO_ROOT)
    run_id = f"{RUN_ID_DATE}_{prefix}_{scenario}"

    t0 = time.perf_counter()
    result = agent.run(fixture["question"], run_id=run_id)
    elapsed = time.perf_counter() - t0

    timestamp = deterministic_timestamp or _DETERMINISTIC_TIMESTAMP
    wall = deterministic_wall_clock if deterministic_wall_clock is not None else _DETERMINISTIC_WALL_CLOCK_SECONDS
    manifest = compute_manifest(
        repo_root=_REPO_ROOT,
        run_id=run_id,
        task_id=scenario,
        seed=0,
        timestamp=timestamp,
        wall_clock_seconds=wall,
    )

    run_dir = out_root / scenario
    emit_run(
        run_dir=run_dir,
        agent_result=result,
        exporter=exporter,
        spans=spans,
        manifest=manifest,
        task_name=fixture.get("question", scenario),
        corpus_description=(
            "Adversarial fixture (no corpus); the agent calls stub tools to trigger "
            "the policy-gate denial documented in tasks/policy_gates/"
        ),
    )
    return run_dir


def _emit_all(out_root: Path) -> list[Path]:
    return [
        _emit_one(scenario=s, out_root=out_root)
        for s in _list_scenarios()
    ]


def _diff_against_committed(*, scenarios: list[str]) -> int:
    """Re-emit each scenario into a tmp dir and assert byte-identical
    match against the committed artifacts. Returns 0 on match, 2 on drift.
    """
    drift: list[str] = []
    with tempfile.TemporaryDirectory() as raw:
        for scenario in scenarios:
            tmp_out = Path(raw) / "out"
            tmp_run = _emit_one(scenario=scenario, out_root=tmp_out)
            committed_run = _RUNS_DIR / scenario
            for filename in ("trace.json", "state.jsonl", "run_report.md"):
                fresh = (tmp_run / filename).read_bytes()
                committed = (committed_run / filename).read_bytes()
                if fresh != committed:
                    drift.append(f"{scenario}/{filename}")
            # Manifest: diff every key except the documented per-run-volatile fields.
            fresh_manifest = json.loads((tmp_run / "manifest.json").read_text())
            committed_manifest = json.loads((committed_run / "manifest.json").read_text())
            for key in EXCLUDED_FROM_REPRODUCIBILITY_DIFF:
                _drop_dotted(fresh_manifest, key)
                _drop_dotted(committed_manifest, key)
            if fresh_manifest != committed_manifest:
                drift.append(f"{scenario}/manifest.json (excluding volatile keys)")

    if drift:
        print(f"[policy-gates] FAIL  drift on {len(drift)} file(s): {drift}")
        return 2
    print(f"[policy-gates] PASS  byte-identical re-emission for {len(scenarios)} scenario(s)")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.run_policy_gates",
        description="Emit committed policy-gate evidence runs.",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Emit a single scenario by id (e.g. pg1_off_allowlist_url)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Emit every PG scenario (default when --scenario is omitted)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Re-emit into a tmp area and diff vs committed artifacts; "
             "exit 0 on byte-identical match, 2 on drift",
    )
    args = parser.parse_args(argv)

    scenarios = _list_scenarios()

    if args.check:
        return _diff_against_committed(scenarios=scenarios)

    if args.scenario:
        if args.scenario not in scenarios:
            raise SystemExit(
                f"unknown scenario {args.scenario!r}; available: {scenarios}"
            )
        run_dir = _emit_one(scenario=args.scenario, out_root=_RUNS_DIR)
        print(f"[policy-gates] WROTE  {run_dir.relative_to(_REPO_ROOT)}")
        return 0

    run_dirs = _emit_all(_RUNS_DIR)
    print(
        f"[policy-gates] WROTE  scenarios={len(run_dirs)}  "
        f"out=runs/policy_gates/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
