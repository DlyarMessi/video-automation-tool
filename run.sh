#!/usr/bin/env bash
set -e

# ==========================================================
# 🎛️ MODE SWITCH（只改这里）
# ==========================================================
# 可选值：
#   run        → 用 production script 生成视频
#   creative   → 用 creative script 生成视频（内部 compile + run）
#   compile    → 只把 creative script 编译成 production script
#   guide      → 只生成拍摄清单（Shooting Guide）
#   clean-tts  → 清空 TTS 缓存
MODE="run"

# ==========================================================
# 🏢 PROJECT CONFIG（常改的都在这）
# ==========================================================
COMPANY="Siglen"

# production script（MODE=run 用）
SCRIPT="output_videos/Siglen/test_run_v1/test_run_v1.compiled.yaml"

# creative script（MODE=creative / compile / guide 用）
CREATIVE="creative_scripts/Siglen/test_run_v1.yaml"

# 素材目录（可留空，走默认 INPUT_DIR）
INPUT_DIR="input_videos/portrait/Siglen/factory"

# TTS cache（按项目）
TTS_CACHE_DIR="output_videos/${COMPANY}/siglen_promo/cache_tts"

# ==========================================================
# 🔊 TTS ENV（与你现在的一致）
# ==========================================================
export AI302_AZURE_TTS_URL="https://api.302.ai/cognitiveservices/v1"
export TTS_HTTP_PROXY="http://127.0.0.1:8001"

# ==========================================================
# 🚀 EXECUTION（不用改）
# ==========================================================
echo "▶ MODE = ${MODE}"
echo "▶ COMPANY = ${COMPANY}"

case "$MODE" in
  run)
    echo "▶ Running production script: ${SCRIPT}"
    if [[ -n "$INPUT_DIR" ]]; then
      python3 src/main.py run --company "$COMPANY" --script "$SCRIPT" --input "$INPUT_DIR"
    else
      python3 src/main.py run --company "$COMPANY" --script "$SCRIPT"
    fi
    ;;

  creative)
    echo "▶ Running from creative script: ${CREATIVE}"
    if [[ -n "$INPUT_DIR" ]]; then
      python3 src/main.py run --company "$COMPANY" --creative "$CREATIVE" --input "$INPUT_DIR"
    else
      python3 src/main.py run --company "$COMPANY" --creative "$CREATIVE"
    fi
    ;;

  compile)
    echo "▶ Compiling creative → production"
    python3 src/main.py compile --company "$COMPANY" --creative "$CREATIVE"
    ;;

  guide)
    echo "▶ Generating shooting guide"
    python3 src/main.py guide --company "$COMPANY" --creative "$CREATIVE"
    ;;

  clean-tts)
    echo "▶ Cleaning TTS cache: ${TTS_CACHE_DIR}"
    rm -rf "$TTS_CACHE_DIR"
    echo "✅ TTS cache cleaned"
    ;;

  *)
    echo "❌ Unknown MODE: $MODE"
    exit 1
    ;;
esac