#!/bin/bash
set -euo pipefail

repo_dir="/home/tomek/lyra_agent"

say() { printf "\n%s\n" "$*"; }

say "== System =="
if command -v uname >/dev/null 2>&1; then uname -a; fi

say "== CPU =="
if command -v lscpu >/dev/null 2>&1; then lscpu | sed -n '1,20p'; else echo "lscpu not found"; fi

say "== RAM =="
if command -v free >/dev/null 2>&1; then free -h; else echo "free not found"; fi

say "== GPU =="
if command -v lspci >/dev/null 2>&1; then lspci | rg -i 'vga|3d|display' || true; else echo "lspci not found"; fi

say "== VRAM (if available) =="
if ls /sys/class/drm/card*/device/mem_info_vram_total >/dev/null 2>&1; then
  for f in /sys/class/drm/card*/device/mem_info_vram_total; do
    echo "$f: $(cat "$f")"
  done
else
  echo "VRAM info not available"
fi

say "== Ollama models =="
if command -v ollama >/dev/null 2>&1; then
  ollama list || true
else
  echo "ollama not found"
fi

say "== Lyra models.json path =="
if [ -n "${LYRA_MODELS_PATH:-}" ]; then
  echo "LYRA_MODELS_PATH=$LYRA_MODELS_PATH"
fi

say "== models.json (if found) =="
if [ -f "/media/tomek/arhiwum/AI_MODELS/models.json" ]; then
  echo "/media/tomek/arhiwum/AI_MODELS/models.json"
  sed -n '1,200p' /media/tomek/arhiwum/AI_MODELS/models.json
elif [ -f "$repo_dir/models.json" ]; then
  echo "$repo_dir/models.json"
  sed -n '1,200p' "$repo_dir/models.json"
else
  echo "models.json not found"
fi

say "== Local model files (sample) =="
if [ -d "/media/tomek/arhiwum/AI_MODELS" ]; then
  find /media/tomek/arhiwum/AI_MODELS -type f -name '*.gguf' | head -n 50
else
  echo "/media/tomek/arhiwum/AI_MODELS not found"
fi
