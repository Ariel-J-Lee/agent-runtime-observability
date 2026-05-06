"""Minimal runner stub for ``make policy-gates``.

This stub delegates to the policy-gate pytest suite so ``make
policy-gates`` is runnable from the day this slice ships. A subsequent
slice (T-EVIDENCE per the runtime proof plan) replaces this script
with a captured-run-emitting version that writes
``runs/policy_gates/<scenario>/{trace.json, state.jsonl,
run_report.md, manifest.json}`` per scenario.

Until that lane lands, ``make policy-gates`` is a test-runner: it
proves the per-scenario tests pass against the canonical
``policy/v1.yaml``. The ``--scenario`` flag selects a single scenario
by id; ``--all`` (default) runs the full suite.

Examples::

    make policy-gates                                  # full suite
    make policy-gates SCENARIO=pg1_off_allowlist_url  # one scenario
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PG_TEST_DIR = "tests/policy_gates"


def _scenario_to_test_path(scenario_id: str) -> str:
    """Map a scenario_id to the matching test file path.

    Convention: ``tests/policy_gates/test_<scenario_id>.py``. The id
    matches the fixture file's ``scenario_id`` field.
    """
    return f"{_PG_TEST_DIR}/test_{scenario_id}.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.run_policy_gates",
        description=(
            "Run the policy-gate test suite. Captured-run emission "
            "lands in a subsequent slice."
        ),
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Run a single scenario by its scenario_id (e.g. pg1_off_allowlist_url)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run every policy-gate test file (default when --scenario is omitted).",
    )
    args = parser.parse_args(argv)

    try:
        import pytest  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "pytest is not installed. Install with: pip install -r requirements-dev.txt"
        ) from exc

    if args.scenario:
        target = _scenario_to_test_path(args.scenario)
        if not (_REPO_ROOT / target).exists():
            raise SystemExit(
                f"No test file found for scenario {args.scenario!r} "
                f"(expected at {target}). "
                f"Available scenarios: {_list_scenario_ids()}"
            )
        pytest_args = [target, "-v"]
    else:
        pytest_args = [_PG_TEST_DIR, "-v"]

    return pytest.main(pytest_args)


def _list_scenario_ids() -> list[str]:
    """List scenario_id values from the test files under ``tests/policy_gates``."""
    test_dir = _REPO_ROOT / _PG_TEST_DIR
    return sorted(
        path.stem.removeprefix("test_")
        for path in test_dir.glob("test_*.py")
    )


if __name__ == "__main__":
    sys.exit(main())
