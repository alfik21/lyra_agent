#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SH="$BASE_DIR/agent.sh"

if [ ! -x "$AGENT_SH" ]; then
  echo "Brakuje agent.sh w $BASE_DIR"
  exit 1
fi

echo "Uruchamiam Lyra jako root..."
exec sudo "$AGENT_SH"
