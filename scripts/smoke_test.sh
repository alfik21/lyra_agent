#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/smoke_test.log"
CONFIG="$ROOT/config.json"
BACKUP="$ROOT/config.json.smoke.bak"

mkdir -p "$LOG_DIR"
echo "=== Lyra smoke test $(date) ===" > "$LOG_FILE"

if [ -f "$CONFIG" ]; then
  cp "$CONFIG" "$BACKUP"
fi

python3 - "$CONFIG" <<'PY'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path))
except Exception:
    data = {}
data.setdefault("cloud_consent", "never")
open(path, "w").write(json.dumps(data, indent=2, ensure_ascii=True) + "\n")
PY

run_cmd() {
  local cmd="$1"
  echo "" >> "$LOG_FILE"
  echo "$ cmd: $cmd" >> "$LOG_FILE"
  python3 "$ROOT/agent.py" "$cmd" >> "$LOG_FILE" 2>&1
}

COMMANDS=(
  ":state"
  "status"
  ":lyra"
  ":bash"
  ":code"
  "lyra lista modeli"
  "lyra pokaz model"
  "lyra komendy"
  "lyra status"
  "zgoda gpt nie"
  "Lyra wracaj na rozkaz"
  "Lyra przejdź przez szkarłatne drzwi"
  "lyra gdzie sie znajduje plik group"
  "sprawdz dyski"
  "sprawdz internet"
  "sprawdz system"
  "sprawdz cpu"
  "sprawdz audio"
  "sprawdz pulpit"
  "sprawdz logi"
  "test vram"
  "lyra stress 2 1"
  "zacznij plik \"bash\" $ROOT/plik_test.sh"
  "zacznij plik \"python\" $ROOT/plik_test2.py"
  "zacznij plik \"tekstowy\" $ROOT/plik_test.txt"
  "dodaj na koncu $ROOT/plik_test.txt \"linia A\""
  "dodaj na poczatku $ROOT/plik_test.txt \"linia B\""
  "dodaj w srodku $ROOT/plik_test.txt \"linia C\""
  "dodaj w linii numer 2 $ROOT/plik_test.txt \"linia D\""
  "zahaszuj linie nr 2 $ROOT/plik_test.txt"
  "zahaszuj linie od 1 do 3 $ROOT/plik_test.txt"
  "czytaj plik $ROOT/plik_test.txt"
  "lyra uzyj lokalny"
  "lyra uzyj gpt"
  "lyra uzyj lokalny"
  "zapamiętaj, że test pamięci działa"
  "niezapomnij: dzisiaj testowalismy smoke test"
  "zapisz log: test zapisany w logowej pamieci"
)

for c in "${COMMANDS[@]}"; do
  run_cmd "$c"
done

if [ -f "$BACKUP" ]; then
  mv "$BACKUP" "$CONFIG"
fi

echo "" >> "$LOG_FILE"
echo "=== done ===" >> "$LOG_FILE"
echo "Log: $LOG_FILE"
