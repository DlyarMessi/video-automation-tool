#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Usage:"
  echo "  bash scripts/quality_gate_all.sh"
  echo
  echo "Runs:"
  echo "  1) scripts/quality_gate_ui.sh"
  echo "  2) scripts/validate_canonical_registry.py"
  echo "  3) scripts/quality_gate_brand.sh Siglen"
  echo "  4) scripts/quality_gate_brand.sh _starter"
  exit 0
fi

echo "=================================================="
echo "Project Master Quality Gate"
echo "=================================================="

echo "[1/4] UI hardening quality gate"
bash scripts/quality_gate_ui.sh

echo
echo "[2/4] Canonical registry validation"
"${PYTHON_BIN}" scripts/validate_canonical_registry.py

echo
echo "[3/4] Brand quality gate | Siglen"
bash scripts/quality_gate_brand.sh Siglen

echo
echo "[4/4] Brand quality gate | _starter"
bash scripts/quality_gate_brand.sh _starter

echo
echo "=================================================="
echo "Master quality gate complete"
echo "=================================================="
