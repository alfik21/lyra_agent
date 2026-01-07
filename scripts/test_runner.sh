#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/test_runner.log"

mkdir -p "$LOG_DIR"
echo "=== Lyra test runner $(date) ===" > "$LOG_FILE"

PASS=0
FAIL=0
SKIP=0

run_cmd() {
  local cmd="$1"
  echo "" >> "$LOG_FILE"
  echo "$ cmd: $cmd" >> "$LOG_FILE"
  out="$(python3 "$ROOT/agent.py" "$cmd" 2>&1)"
  echo "$out" >> "$LOG_FILE"
  case "$cmd" in
    ":state"|"status")
      if echo "$out" | rg -q "Config: OK"; then
        echo "PASS: $cmd"
        PASS=$((PASS+1))
        return
      fi
      if echo "$out" | rg -q "llama-server: ERROR"; then
        echo "SKIP: $cmd"
        SKIP=$((SKIP+1))
        return
      fi
      ;;
    "sprawdz dyski")
      if echo "$out" | rg -q "DISK_DIAG"; then
        echo "PASS: $cmd"
        PASS=$((PASS+1))
        return
      fi
      ;;
    "sprawdz audio")
      if echo "$out" | rg -q "AUDIO_DIAG"; then
        echo "PASS: $cmd"
        PASS=$((PASS+1))
        return
      fi
      ;;
    "sprawdz pulpit")
      if echo "$out" | rg -q "DESKTOP_DIAG"; then
        echo "PASS: $cmd"
        PASS=$((PASS+1))
        return
      fi
      ;;
    "lyra start llama"|"lyra stop llama"|"lyra status llama")
      if echo "$out" | rg -qi "no_new_privs|bez nowych uprawnień"; then
        echo "SKIP: $cmd"
        SKIP=$((SKIP+1))
        return
      fi
      ;;
  esac
  if echo "$out" | rg -qi "no_new_privs|bez nowych uprawnień"; then
    echo "SKIP: $cmd"
    SKIP=$((SKIP+1))
    return
  fi
  if echo "$out" | rg -qi "traceback|error|exception|failed"; then
    echo "FAIL: $cmd"
    FAIL=$((FAIL+1))
  else
    echo "PASS: $cmd"
    PASS=$((PASS+1))
  fi
}

COMMANDS=(
  ":state"
  "status"
  "lyra komendy"
  "lyra lista modeli"
  "lyra pokaz model"
  "lyra dry-run status"
  "lyra dry-run on"
  "lyra dry-run status"
  "lyra dry-run off"
  "lyra zmien silnik na llama"
  "lyra zmien silnik na ollama"
  "lyra start llama"
  "lyra status llama"
  "lyra stop llama"
  "lyra gdzie sie znajduje plik group"
  "lyra test odpowiedzi"
  "sprawdz dyski"
  "sprawdz internet"
  "sprawdz system"
  "sprawdz audio"
  "sprawdz pulpit"
  "sprawdz logi"
  "test vram"
  "lyra stress 2 1"
  "zacznij plik \"tekstowy\" $ROOT/test_runner_file.txt"
  "dodaj na koncu $ROOT/test_runner_file.txt \"A\""
  "dodaj na poczatku $ROOT/test_runner_file.txt \"B\""
  "dodaj w srodku $ROOT/test_runner_file.txt \"C\""
  "dodaj w linii numer 2 $ROOT/test_runner_file.txt \"D\""
  "zahaszuj linie nr 2 $ROOT/test_runner_file.txt"
  "zahaszuj linie od 1 do 3 $ROOT/test_runner_file.txt"
  "czytaj plik $ROOT/test_runner_file.txt"
  "zapamietaj: test pamieci dlugiej"
  "niezapomnij: test pamieci biezacej"
  "zapisz: test pamieci logowej"
)

for c in "${COMMANDS[@]}"; do
  run_cmd "$c"
done

echo "" >> "$LOG_FILE"
echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP" >> "$LOG_FILE"
echo "Log: $LOG_FILE"
echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
