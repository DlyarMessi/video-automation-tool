#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage:"
  echo "  bash scripts/quality_gate_brand.sh <brand_name> [--plan PLAN] [--write-report]"
  echo
  echo "Examples:"
  echo "  bash scripts/quality_gate_brand.sh Siglen"
  echo "  bash scripts/quality_gate_brand.sh _starter --write-report"
  exit 1
fi

BRAND_NAME="$1"
shift || true

PLAN_NAME="default"
WRITE_REPORT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)
      PLAN_NAME="${2:-default}"
      shift 2
      ;;
    --write-report)
      WRITE_REPORT=1
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=================================================="
echo "Brand Quality Gate"
echo "=================================================="
echo "Brand : ${BRAND_NAME}"
echo "Plan  : ${PLAN_NAME}"
echo "Write report : ${WRITE_REPORT}"
echo

echo "[1/5] Validate canonical registry"
"${PYTHON_BIN}" scripts/validate_canonical_registry.py

echo
echo "[2/5] Validate pool plan"
"${PYTHON_BIN}" scripts/validate_pool_plan.py "${BRAND_NAME}" --plan "${PLAN_NAME}"

echo
echo "[3/5] Audit brand setup"
if [[ "${WRITE_REPORT}" -eq 1 ]]; then
  "${PYTHON_BIN}" scripts/audit_brand_setup.py "${BRAND_NAME}" --plan "${PLAN_NAME}" --write-report
else
  "${PYTHON_BIN}" scripts/audit_brand_setup.py "${BRAND_NAME}" --plan "${PLAN_NAME}"
fi

echo
echo "[4/5] Registry sync dry-run"
"${PYTHON_BIN}" scripts/sync_pool_plan_from_registry.py "${BRAND_NAME}" --plan "${PLAN_NAME}"

echo
echo "[5/5] Consolidated preflight"
if [[ "${WRITE_REPORT}" -eq 1 ]]; then
  "${PYTHON_BIN}" scripts/preflight_brand.py "${BRAND_NAME}" --plan "${PLAN_NAME}" --write-report
else
  "${PYTHON_BIN}" scripts/preflight_brand.py "${BRAND_NAME}" --plan "${PLAN_NAME}"
fi

echo
echo "=================================================="
echo "Quality gate complete"
echo "=================================================="
