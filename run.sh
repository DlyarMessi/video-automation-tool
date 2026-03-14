#!/usr/bin/env bash
set -euo pipefail

PY="./.venv/bin/python"
MODE="${MODE:-ui}"

COMPANY="${COMPANY:-Siglen}"
SCRIPT="${SCRIPT:-}"
CREATIVE="${CREATIVE:-}"
INPUT_DIR="${INPUT_DIR:-}"
POOL_PLAN_DIR="data/brands/$(echo "$COMPANY" | tr '[:upper:]' '[:lower:]')/pool_plans"

echo "▶ MODE = ${MODE}"
echo "▶ COMPANY = ${COMPANY}"

case "$MODE" in
  ui)
    echo "▶ Launching Streamlit UI"
    exec "$PY" -m streamlit run ui_app.py
    ;;

  status)
    echo "▶ Python = $PY"
    echo "▶ Company = $COMPANY"
    echo "▶ Pool plan dir = $POOL_PLAN_DIR"
    if [[ -d "$POOL_PLAN_DIR" ]]; then
      echo "▶ Available pool plans:"
      find "$POOL_PLAN_DIR" -maxdepth 1 -type f \( -name "*.yaml" -o -name "*.yml" \) | sort
    else
      echo "▶ No brand pool plan directory found"
    fi
    echo "▶ Docs:"
    find docs -maxdepth 1 -type f 2>/dev/null | sort || true
    ;;

  run)
    if [[ -z "$SCRIPT" ]]; then
      echo "❌ MODE=run requires SCRIPT=/path/to/compiled.yaml"
      exit 1
    fi
    echo "▶ Running production script: $SCRIPT"
    if [[ -n "$INPUT_DIR" ]]; then
      exec "$PY" src/main.py run --company "$COMPANY" --script "$SCRIPT" --input "$INPUT_DIR"
    else
      exec "$PY" src/main.py run --company "$COMPANY" --script "$SCRIPT"
    fi
    ;;

  guide)
    if [[ -z "$CREATIVE" ]]; then
      echo "❌ MODE=guide requires CREATIVE=/path/to/creative.yaml"
      exit 1
    fi
    echo "▶ Generating shooting guide from creative script: $CREATIVE"
    exec "$PY" src/main.py guide --company "$COMPANY" --creative "$CREATIVE"
    ;;

  clean-junk)
    echo "▶ Removing .DS_Store and __pycache__ ..."
    find . -name ".DS_Store" -delete
    find . -name "__pycache__" -type d -prune -exec rm -rf {} +
    echo "✅ Junk files cleaned"
    ;;

  *)
    echo "❌ Unknown MODE: $MODE"
    echo "Available: ui | status | run | guide | clean-junk"
    exit 1
    ;;
esac
