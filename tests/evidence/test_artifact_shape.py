"""Tests that committed evidence runs match the PACKET-046 §3.1-§3.7 spec.

Each committed run under ``runs/`` must carry exactly four files
(``trace.json``, ``state.jsonl``, ``run_report.md``, ``manifest.json``)
with the documented shape. This suite locks the contract so a future
slice that drifts the artifact format fails CI loudly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.tracing import validate_otlp_subset

_RUNS_DIR = _REPO_ROOT / "runs"
_REQUIRED_ARTIFACTS = ("trace.json", "state.jsonl", "run_report.md", "manifest.json")
_REQUIRED_MANIFEST_TOP_KEYS = (
    "run_id",
    "task_id",
    "corpus",
    "policy",
    "code",
    "llm",
    "seed",
    "timestamp",
    "wall_clock_seconds",
    "regression_baseline",
)
_REQUIRED_REPORT_HEADERS = (
    "## Setup",
    "## Outcome",
    "## Notes",
)


def _committed_run_dirs() -> list[Path]:
    """Every directory under ``runs/`` that holds a real captured run."""
    out: list[Path] = []
    for p in sorted(_RUNS_DIR.iterdir()):
        if p.is_dir() and p.name not in ("policy_gates", "failure_modes"):
            out.append(p)
    for sub in ("policy_gates", "failure_modes"):
        sub_dir = _RUNS_DIR / sub
        if sub_dir.is_dir():
            out.extend(sorted(p for p in sub_dir.iterdir() if p.is_dir()))
    return out


def test_runs_dir_contains_canonical_and_pg_and_fm_runs():
    dirs = _committed_run_dirs()
    assert any(p.parent == _RUNS_DIR for p in dirs), (
        "missing canonical run under runs/<canonical-run-id>/"
    )
    assert any(p.parent.name == "policy_gates" for p in dirs), "missing policy_gates runs"
    assert any(p.parent.name == "failure_modes" for p in dirs), "missing failure_modes runs"


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_run_directory_carries_all_four_required_artifacts(run_dir: Path):
    for artifact in _REQUIRED_ARTIFACTS:
        path = run_dir / artifact
        assert path.exists(), f"{run_dir.name}: missing {artifact}"
        assert path.stat().st_size > 0, f"{run_dir.name}: empty {artifact}"


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_trace_json_validates_against_otlp_subset_schema(run_dir: Path):
    doc = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))
    validate_otlp_subset(doc)


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_state_jsonl_parses_line_by_line_with_required_keys(run_dir: Path):
    text = (run_dir / "state.jsonl").read_text(encoding="utf-8")
    records = [json.loads(line) for line in text.splitlines() if line.strip()]
    assert records, f"{run_dir.name}: empty state.jsonl"
    required = {"run_id", "step_index", "intended_tool_calls", "policy_decisions",
                "tool_results", "errors"}
    for i, rec in enumerate(records):
        missing = required - rec.keys()
        assert not missing, f"{run_dir.name}: record[{i}] missing {missing}"


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_run_report_carries_required_headers(run_dir: Path):
    body = (run_dir / "run_report.md").read_text(encoding="utf-8")
    for header in _REQUIRED_REPORT_HEADERS:
        assert header in body, f"{run_dir.name}: run_report.md missing {header!r}"
    assert body.startswith("# Runtime Demo Run "), (
        f"{run_dir.name}: run_report.md missing canonical title"
    )


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_manifest_carries_all_required_top_level_keys(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    missing = set(_REQUIRED_MANIFEST_TOP_KEYS) - manifest.keys()
    assert not missing, f"{run_dir.name}: manifest missing {missing}"


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_manifest_corpus_block_pins_snapshot_id(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    corpus = manifest["corpus"]
    assert corpus["source"] == "synthetic-fixture-corpus"
    assert corpus["doc_count"] == 25
    assert "data/LICENSE.fixture-corpus" in corpus["license_files"]
    snapshot = corpus["snapshot_id"]
    assert isinstance(snapshot, str) and len(snapshot) == 64, (
        f"{run_dir.name}: corpus.snapshot_id is not a 64-hex SHA-256"
    )


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_manifest_policy_block_records_spec_sha_and_version(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    policy = manifest["policy"]
    assert policy["spec_path"] == "policy/v1.yaml"
    assert isinstance(policy["spec_sha256"], str) and len(policy["spec_sha256"]) == 64
    # ``version`` matches the runtime's :class:`PolicySpec.version`
    # (12 hex chars). For runs that mutate the spec in-memory (the
    # canonical run widens ``url_allowlist``), this differs from the
    # on-disk file SHA-256 prefix; both are recorded so reviewers can
    # see what the run actually used vs. the source the manifest pins.
    assert isinstance(policy["version"], str) and len(policy["version"]) == 12


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_manifest_llm_block_pins_stub_script_sha(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    llm = manifest["llm"]
    assert llm["execution_path"] == "stub"
    assert llm["stub_script_path"] == "src/runtime/stub_llm/canned.py"
    assert isinstance(llm["stub_script_sha256"], str) and len(llm["stub_script_sha256"]) == 64


@pytest.mark.parametrize("run_dir", _committed_run_dirs(), ids=lambda p: p.name)
def test_manifest_code_block_records_tracing_subset_schema_sha(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    code = manifest["code"]
    sha = code["tracing_subset_schema_sha256"]
    assert isinstance(sha, str) and len(sha) == 64
    assert "git_sha" in code  # captured but per-run-volatile; just exists


def test_at_least_three_policy_gate_runs_committed():
    """PACKET-046 §1.3 #2 requires at least 3 of 5 PG runs committed."""
    pg_runs = [p for p in _committed_run_dirs() if p.parent.name == "policy_gates"]
    assert len(pg_runs) >= 3, f"only {len(pg_runs)} policy-gate runs committed"


def test_all_five_failure_mode_runs_committed():
    """PACKET-046 §1.3 #3 requires all five FM runs committed."""
    fm_runs = sorted(p.name for p in _committed_run_dirs() if p.parent.name == "failure_modes")
    assert set(fm_runs) >= {
        "tool_call_failure",
        "retry_exhaustion",
        "schema_mismatch",
        "cycle_detection",
        "catalogued_unhandled",
    }, f"missing failure-mode runs; have {fm_runs}"


def test_canonical_run_terminates_with_final_answer():
    canonicals = [p for p in _committed_run_dirs() if p.parent == _RUNS_DIR]
    assert len(canonicals) == 1
    body = (canonicals[0] / "run_report.md").read_text(encoding="utf-8")
    assert "Result: success" in body, "canonical run did not terminate with success"


def test_each_policy_gate_run_carries_at_least_one_deny_span():
    """Per PACKET-046 §1.3 #2, every PG trace must show ``decision=deny``,
    EXCEPT for the documented PG3 loop-budget gap (PACKET-049 / 050 /
    051): the agent's loop-budget exhaustion does not currently emit a
    ``policy_check`` deny span; the run terminates with
    ``terminal_reason=loop_budget`` instead. T-EVIDENCE captures the
    artifacts as-is rather than retrofitting the runtime.
    """
    pg3_documented_gaps = {"pg3_loop_budget", "pg3_loop_budget_tokens"}
    for run_dir in _committed_run_dirs():
        if run_dir.parent.name != "policy_gates":
            continue
        if run_dir.name in pg3_documented_gaps:
            continue
        trace = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))
        deny_count = 0
        for rs in trace.get("resourceSpans", []):
            for ss in rs.get("scopeSpans", []):
                for span in ss.get("spans", []):
                    if span.get("name") != "policy_check":
                        continue
                    for attr in span.get("attributes", []):
                        if (
                            attr.get("key") == "agent.policy.decision"
                            and attr.get("value", {}).get("stringValue") == "deny"
                        ):
                            deny_count += 1
        assert deny_count >= 1, f"{run_dir.name}: no deny span in trace.json"


def test_pg3_runs_terminate_with_loop_budget_reason():
    """Lock the documented PG3 runtime gap: pg3_loop_budget runs
    terminate via ``terminal_reason=loop_budget`` rather than via a
    ``policy_check`` deny span. When the runtime extension that closes
    the gap lands, this test will start failing on at least one of the
    pg3 runs and the dual assertion in
    ``test_each_policy_gate_run_carries_at_least_one_deny_span`` should
    drop the corresponding skip."""
    for run_dir in _committed_run_dirs():
        if run_dir.parent.name != "policy_gates" or "pg3" not in run_dir.name:
            continue
        body = (run_dir / "run_report.md").read_text(encoding="utf-8")
        assert "loop_budget" in body, (
            f"{run_dir.name}: expected loop_budget in run_report.md"
        )
