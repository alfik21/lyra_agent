#!/usr/bin/env bash

echo "🟣 Lyra shell online. Wpisz 'exit' aby wrócić do bash."
echo "🟣 Lyra online. Strzałki działają. 'exit' = powrót do bash."

# --- Kolory ---
RESET='\[\e[0m\]'
BOLD='\[\e[1m\]'
DIM='\[\e[2m\]'

PURPLE='\[\e[38;5;135m\]'
CYAN='\[\e[38;5;81m\]'
GRAY='\[\e[38;5;245m\]'
GREEN='\[\e[38;5;114m\]'

# --- Prompt Lyry ---
LYRA_PROMPT="${BOLD}${PURPLE}Lyra${RESET} ${DIM}${GRAY}›${RESET} "


while true; do
    read -rp "Lyra > " line

    if [[ "$line" == "exit" ]]; then
        echo "🔚 Powrót do bash"
        break
    fi

    # puste linie
    [[ -z "$line" ]] && continue

    # jeśli zaczyna się od !
    if [[ "$line" == !* ]]; then
        eval "${line:1}"
        continue
    fi
    
    if command -v "${line%% *}" >/dev/null 2>&1; then
        eval "$line"
    else

    # Lyra decyduje
    ./agent.sh "$line"
    fi
done

