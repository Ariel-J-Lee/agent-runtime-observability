"""Captured-run emitter for the five catalogued failure modes.

Mirrors :mod:`scripts.run_policy_gates`: walks each fixture under
``tasks/failure_modes/``, drives it through a real :class:`Agent.run`
against ``policy/v1.yaml`` with per-fixture stub-tool behavior
(configured by the fixture's ``stub_behavior`` block), captures the
trace via the OTel exporter, and emits the four PACKET-046 §3.1
artifacts to ``runs/failure_modes/<mode>/``.

Usage::

    make failure-modes                              # emit every FM run
    make failure-modes SCENARIO=cycle_detection     # emit one
    python3 -m scripts.run_failure_modes --check    # diff vs committed
"""

from __future__ import annotations

import argparse
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
from src.runtime import Agent, PolicyChecker, PolicySpec
from src.tracing import new_exporter

from tests.failure_modes._stubs import (
    STUB_TOOL_SCHEMAS,
    build_tool_registry,
    make_canned_llm,
)

_FIXTURE_DIR = _REPO_ROOT / "tasks" / "failure_modes"
_RUNS_DIR = _REPO_ROOT / "runs" / "failure_modes"
_DETERMINISTIC_TIMESTAMP = "2026-05-06T00:00:00Z"
_DETERMINISTIC_WALL_CLOCK_SECONDS = 0.0


def _list_scenarios() -> list[str]:
    return sorted(p.stem for p in _FIXTURE_DIR.glob("*.json"))


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _emit_one(*, scenario: str, out_root: Path) -> Path:
    fixture = _load_fixture(scenario)
    spec = PolicySpec.from_yaml_path(_REPO_ROOT / "policy" / "v1.yaml")

    tool_registry = build_tool_registry(fixture.get("stub_behavior"))
    checker = PolicyChecker(spec, tool_schemas=STUB_TOOL_SCHEMAS)

    spans: list[tuple[str, dict[str, Any]]] = []

    def _recorder(span_class: str, attrs):
        spans.append((span_class, dict(attrs)))

    exporter = new_exporter(seed=0, time_source=deterministic_time_source())

    def _both(span_class: str, attrs):
        exporter(span_class, attrs)
        _recorder(span_class, attrs)

    max_iterations = int(spec.get("loop_budget.max_iterations", 10))
    agent = Agent(
        llm=make_canned_llm(fixture["canned_llm_tool_calls"]),
        tool_registry=tool_registry,
        policy_checker=checker,
        span_recorder=_both,
        max_iterations=max_iterations,
        max_retries=2,
    )

    prefix = compute_run_id_policy_prefix(repo_root=_REPO_ROOT)
    run_id = f"{RUN_ID_DATE}_{prefix}_{scenario}"

    t0 = time.perf_counter()
    result = agent.run(fixture["question"], run_id=run_id)
    _ = time.perf_counter() - t0
    manifest = compute_manifest(
        repo_root=_REPO_ROOT,
        run_id=run_id,
        task_id=scenario,
        seed=0,
        timestamp=_DETERMINISTIC_TIMESTAMP,
        wall_clock_seconds=_DETERMINISTIC_WALL_CLOCK_SECONDS,
    )

    run_dir = out_root / scenario
    emit_run(
        run_dir=run_dir,
        repo_root=_REPO_ROOT,
        agent_result=result,
        exporter=exporter,
        spans=spans,
        manifest=manifest,
        task_name=fixture.get("question", scenario),
        corpus_description=(
            "Adversarial fixture (no corpus); the stub tool layer is rigged per "
            "tasks/failure_modes/ to fire the catalogued failure mode"
        ),
    )
    return run_dir


def _drop_dotted(d: dict, dotted: str) -> None:
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        cur = cur[p]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _diff_against_committed(*, scenarios: list[str]) -> int:
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
            fresh_manifest = json.loads((tmp_run / "manifest.json").read_text())
            committed_manifest = json.loads((committed_run / "manifest.json").read_text())
            for key in EXCLUDED_FROM_REPRODUCIBILITY_DIFF:
                _drop_dotted(fresh_manifest, key)
                _drop_dotted(committed_manifest, key)
            if fresh_manifest != committed_manifest:
                drift.append(f"{scenario}/manifest.json (excluding volatile keys)")

    if drift:
        print(f"[failure-modes] FAIL  drift on {len(drift)} file(s): {drift}")
        return 2
    print(f"[failure-modes] PASS  byte-identical re-emission for {len(scenarios)} scenario(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.run_failure_modes",
        description="Emit committed failure-mode evidence runs.",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Emit a single scenario by id (e.g. cycle_detection)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Emit every FM scenario (default when --scenario is omitted)",
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
        print(f"[failure-modes] WROTE  {run_dir.relative_to(_REPO_ROOT)}")
        return 0

    run_dirs = [_emit_one(scenario=s, out_root=_RUNS_DIR) for s in scenarios]
    print(
        f"[failure-modes] WROTE  scenarios={len(run_dirs)}  "
        f"out=runs/failure_modes/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
