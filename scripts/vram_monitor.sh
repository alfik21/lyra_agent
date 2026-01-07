#!/usr/bin/env bash
set -euo pipefail

LOG="/home/tomek/lyra_agent/logs/vram_monitor.log"
INTERVAL="${1:-10}"

mkdir -p "$(dirname "$LOG")"

while true; do
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  line="$ts"
  found=0
  for used in /sys/class/drm/card*/device/mem_info_vram_used; do
    if [ -r "$used" ]; then
      total="${used%_used}_total"
      u_bytes="$(cat "$used")"
      t_bytes="0"
      if [ -r "$total" ]; then
        t_bytes="$(cat "$total")"
      fi
      u_mib=$((u_bytes / 1024 / 1024))
      t_mib=$((t_bytes / 1024 / 1024))
      card="$(basename "$(dirname "$used")")"
      line+=" ${card}=${u_mib}MiB/${t_mib}MiB"
      found=1
    fi
  done
  if [ "$found" -eq 0 ]; then
    line+=" vram=unavailable"
  fi
  echo "$line" >> "$LOG"
  sleep "$INTERVAL"
done
