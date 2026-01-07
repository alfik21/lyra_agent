#!/bin/bash
set -euo pipefail

MODEL_PATH="/media/tomek/arhiwum/AI_MODELS/gemma-2-2b-it-Q4_K_M.gguf"
OUT_LOG="/tmp/llama_test.log"
VRAM_LOG="/tmp/llama_vram.log"

if [ ! -f "$MODEL_PATH" ]; then
  echo "Model file not found: $MODEL_PATH" >&2
  exit 1
fi

# Start VRAM monitor in background
(while true; do
  ts=$(date +%s)
  v1=$(cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null || echo 0)
  v2=$(cat /sys/class/drm/card2/device/mem_info_vram_used 2>/dev/null || echo 0)
  echo "$ts card1=$v1 card2=$v2" >> "$VRAM_LOG"
  sleep 1
done) &
MON_PID=$!

# Run llama-cli with tensor split
/home/tomek/lyra_agent/llama.cpp/build/bin/llama-cli \
  -m "$MODEL_PATH" \
  --tensor-split 8,4 \
  --gpu-layers 99 \
  -n 32 \
  -p "Napisz 2 zdania o AI." \
  > "$OUT_LOG" 2>&1 || true

# Stop monitor
kill "$MON_PID" 2>/dev/null || true

# Print last VRAM samples
echo "== VRAM samples =="
if [ -f "$VRAM_LOG" ]; then
  tail -n 10 "$VRAM_LOG"
else
  echo "no vram log"
fi

# Print key llama-cli lines
echo "== llama-cli log (filtered) =="
rg -n "ggml_vulkan|tensor|split|device|offload|GPU" "$OUT_LOG" | head -n 80 || true
