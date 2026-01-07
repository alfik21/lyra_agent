#!/usr/bin/env bash
set -euo pipefail

LOG="/home/tomek/lyra_agent/logs/llama_server.log"
MODEL="/media/tomek/arhiwum/AI_MODELS/Bielik-11B-v3.0-Instruct.f16.gguf"
BIN="/home/tomek/lyra_agent/llama.cpp/build/bin/llama-server"

if [ ! -x "$BIN" ]; then
  echo "Brak binarki: $BIN"
  exit 1
fi
if [ ! -f "$MODEL" ]; then
  echo "Brak modelu: $MODEL"
  exit 1
fi

sudo pkill -f "$BIN" >/dev/null 2>&1 || true
sudo nohup "$BIN" \
  -m "$MODEL" \
  --host 127.0.0.1 \
  --port 11434 \
  --ctx-size 16384 \
  --gpu-layers 99 \
  --tensor-split 8,4 \
  > "$LOG" 2>&1 &

echo "OK: llama-server uruchomiony jako root"
echo "Log: $LOG"
