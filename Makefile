.PHONY: help smoke smoke-runtime trace-smoke tool-smoke fixture-build canonical canonical-check policy-gates policy-gates-check failure-modes failure-modes-check evidence-build evidence-check regression

help:
	@echo "agent-runtime-observability — v0 controlled scaffold"
	@echo ""
	@echo "Targets:"
	@echo "  smoke         verify v0 file structure (real test, passes when shell is intact)"
	@echo "  smoke-runtime pytest tests/test_runtime_smoke.py (requires 'pip install -r requirements-dev.txt')"
	@echo "  policy-gates  run the policy-gate scenario tests; SCENARIO=<id> selects one (requires 'pip install -r requirements.txt requirements-dev.txt')"
	@echo "  failure-modes run the failure-mode scenario tests; SCENARIO=<id> selects one (requires 'pip install -r requirements.txt requirements-dev.txt')"
	@echo "  trace-smoke   drive the in-tree trace fixture through the OTLP-JSON exporter and validate against the subset schema (requires 'pip install -r requirements.txt')"
	@echo "  tool-smoke    drive the five v1 tools through a real Agent.run with strict-mode arg_schema enforcement (requires 'pip install -r requirements.txt')"
	@echo "  fixture-build (re)build the deterministic fixture corpus under data/corpus/v1/ from the documented seed; --check verifies on-disk files match the manifest"
	@echo "  canonical     emit the canonical run under runs/<canonical-run-id>/ from the canonical task fixture (requires 'pip install -r requirements.txt')"
	@echo "  canonical-check     re-emit the canonical run into a tmp area and diff against the committed copy"
	@echo "  evidence-build      emit canonical + every PG + every FM run under runs/"
	@echo "  evidence-check      re-emit every committed run into a tmp area and diff byte-identically against the committed copies"
	@echo "  regression    placeholder; lands at Tier 4 in a future implementation packet"

smoke:
	@bash tests/smoke.sh

smoke-runtime:
	@python3 -m pytest tests/test_runtime_smoke.py -q

trace-smoke:
	@python3 -m scripts.run_trace_smoke

tool-smoke:
	@python3 -m scripts.run_tool_smoke

fixture-build:
	@python3 -m scripts.build_fixture_corpus

canonical:
	@python3 -m scripts.run_canonical_smoke --emit

canonical-check:
	@python3 -m scripts.run_canonical_smoke --check

evidence-build: canonical
	@python3 -m scripts.run_policy_gates
	@python3 -m scripts.run_failure_modes

evidence-check: canonical-check policy-gates-check failure-modes-check

policy-gates-check:
	@python3 -m scripts.run_policy_gates --check

failure-modes-check:
	@python3 -m scripts.run_failure_modes --check

policy-gates:
ifdef SCENARIO
	@python3 -m scripts.run_policy_gates --scenario $(SCENARIO)
else
	@python3 -m scripts.run_policy_gates
endif

failure-modes:
ifdef SCENARIO
	@python3 -m scripts.run_failure_modes --scenario $(SCENARIO)
else
	@python3 -m scripts.run_failure_modes
endif

regression:
	@echo "v0 scaffold; arrives at Tier-4 in a future implementation packet."
	@exit 1
