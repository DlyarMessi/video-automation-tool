#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=================================================="
echo "UI Hardening Quality Gate"
echo "=================================================="

echo "[1/3] Python compile check"
"${PYTHON_BIN}" -m py_compile \
  ui_app.py \
  src/ui_hardening.py \
  src/ui_brand_ops.py \
  src/ui_pool_fill_model.py \
  src/ui_state.py \
  src/ui_pool_fill_controls.py \
  src/ui_workspace.py \
  scripts/smoke_ui_foundation.py

echo
echo "[2/3] UI foundation smoke checks"
"${PYTHON_BIN}" scripts/smoke_ui_foundation.py

echo
echo "[3/3] Brand quality gate (Siglen)"
bash scripts/quality_gate_brand.sh Siglen >/dev/null
echo "PASS  brand quality gate wrapper"

echo
echo "=================================================="
echo "UI hardening gate complete"
echo "=================================================="
