.PHONY: help smoke smoke-runtime canonical policy-gates failure-modes regression

help:
	@echo "agent-runtime-observability — v0 controlled scaffold"
	@echo ""
	@echo "Targets:"
	@echo "  smoke         verify v0 file structure (real test, passes when shell is intact)"
	@echo "  smoke-runtime pytest tests/test_runtime_smoke.py (requires 'pip install -r requirements-dev.txt')"
	@echo "  policy-gates  run the policy-gate scenario tests; SCENARIO=<id> selects one (requires 'pip install -r requirements.txt requirements-dev.txt')"
	@echo "  failure-modes run the failure-mode scenario tests; SCENARIO=<id> selects one (requires 'pip install -r requirements.txt requirements-dev.txt')"
	@echo "  canonical     placeholder; lands at Tier 4 in a future implementation packet"
	@echo "  regression    placeholder; lands at Tier 4 in a future implementation packet"

smoke:
	@bash tests/smoke.sh

smoke-runtime:
	@python3 -m pytest tests/test_runtime_smoke.py -q

canonical:
	@echo "v0 scaffold; arrives at Tier-4 in a future implementation packet."
	@exit 1

policy-gates:
ifdef SCENARIO
	@python3 -m scripts.run_policy_gates --scenario $(SCENARIO)
else
	@python3 -m scripts.run_policy_gates --all
endif

failure-modes:
ifdef SCENARIO
	@python3 -m scripts.run_failure_modes --scenario $(SCENARIO)
else
	@python3 -m scripts.run_failure_modes --all
endif

regression:
	@echo "v0 scaffold; arrives at Tier-4 in a future implementation packet."
	@exit 1
