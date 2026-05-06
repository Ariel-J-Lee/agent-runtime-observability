#!/usr/bin/env bash
# v0 scaffold smoke test: verify the documented file structure exists and
# every stub module carries the v0 placeholder marker. Real test, minimal,
# passes when the shell is intact.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REQUIRED_FILES=(
  README.md
  LICENSE
  ROADMAP.md
  Makefile
  failure_modes.md
  .gitignore
  src/runtime/agent.py
  src/runtime/policy.py
  src/runtime/retry.py
  src/runtime/state.py
  src/tracing/otel_exporter.py
  src/fail/catalog.py
  tasks/README.md
  policy/README.md
  tools/README.md
  runs/README.md
  data/DATA-SOURCE.md
  docs/runtime-model.md
  docs/policy-gates.md
  docs/failure-modes.md
  docs/evidence-tier.md
  docs/architecture.md
)

failed=0

for f in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f" >&2
    failed=1
  fi
done

# The src/runtime/*.py modules graduated from v0 placeholders to real
# implementations in the runtime-skeleton slice; src/fail/catalog.py
# graduated in the failure-mode slice. Only the trace exporter still
# ships as a v0 stub at this commit.
STUB_FILES=(
  src/tracing/otel_exporter.py
)

for f in "${STUB_FILES[@]}"; do
  if [[ -f "$f" ]] && ! grep -q "v0 PLACEHOLDER" "$f"; then
    echo "MISSING v0 PLACEHOLDER marker in stub: $f" >&2
    failed=1
  fi
done

if [[ "$failed" == "1" ]]; then
  echo "v0 smoke check FAILED" >&2
  exit 1
fi

echo "v0 smoke check OK: file structure intact, placeholder markers present"
