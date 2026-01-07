#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/lyra_agent"
CMD="${ROOT}/agent.py lyra konsola"

run_term() {
  "$@" && exit 0
  return 1
}

if command -v gnome-terminal >/dev/null 2>&1; then
  run_term gnome-terminal -- bash -lc "cd \"$ROOT\" && $CMD"
fi
if command -v konsole >/dev/null 2>&1; then
  run_term konsole -e bash -lc "cd \"$ROOT\" && $CMD"
fi
if command -v xfce4-terminal >/dev/null 2>&1; then
  run_term xfce4-terminal -e bash -lc "cd \"$ROOT\" && $CMD"
fi
if command -v mate-terminal >/dev/null 2>&1; then
  run_term mate-terminal -e bash -lc "cd \"$ROOT\" && $CMD"
fi
if command -v tilix >/dev/null 2>&1; then
  run_term tilix -e bash -lc "cd \"$ROOT\" && $CMD"
fi
if command -v x-terminal-emulator >/dev/null 2>&1; then
  run_term x-terminal-emulator -e bash -lc "cd \"$ROOT\" && $CMD"
fi

echo "Nie znaleziono dzialajacego terminala. Uruchom: ${CMD}" >&2
exit 1
