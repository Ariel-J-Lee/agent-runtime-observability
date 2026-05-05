.PHONY: help smoke canonical policy-gates failure-modes regression

help:
	@echo "agent-runtime-observability — v0 controlled scaffold"
	@echo ""
	@echo "Targets:"
	@echo "  smoke         verify v0 file structure (real test, passes when shell is intact)"
	@echo "  canonical     placeholder; lands at Tier 4 in a future implementation packet"
	@echo "  policy-gates  placeholder; lands at Tier 4 in a future implementation packet"
	@echo "  failure-modes placeholder; lands at Tier 4 in a future implementation packet"
	@echo "  regression    placeholder; lands at Tier 4 in a future implementation packet"

smoke:
	@bash tests/smoke.sh

canonical:
	@echo "v0 scaffold; arrives at Tier-4 in a future implementation packet."
	@exit 1

policy-gates:
	@echo "v0 scaffold; arrives at Tier-4 in a future implementation packet."
	@exit 1

failure-modes:
	@echo "v0 scaffold; arrives at Tier-4 in a future implementation packet."
	@exit 1

regression:
	@echo "v0 scaffold; arrives at Tier-4 in a future implementation packet."
	@exit 1
