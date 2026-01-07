#!/usr/bin/env bash

AGENT="./agent.sh"

# kolory – BEZPIECZNE
RESET='\[\e[0m\]'
BOLD='\[\e[1m\]'
PURPLE='\[\e[38;5;135m\]'
GRAY='\[\e[38;5;245m\]'

PROMPT="${BOLD}${PURPLE}Lyra${RESET} ${GRAY}›${RESET} "

echo "🟣 Lyra online. Strzałki działają. 'exit' = powrót do bash."

while true; do
    # readline, HISTORIA, STRZAŁKI
    read -e -p "$PROMPT" line

    [[ $? -ne 0 ]] && echo && break
    [[ -z "$line" ]] && continue

    history -s "$line"

    if [[ "$line" == "exit" ]]; then
        echo "👋 Powrót do bash"
        break
    fi

    # KOMENDY SYSTEMOWE
    if command -v "${line%% *}" >/dev/null 2>&1; then
        bash -c "$line"
    else
        "$AGENT" "$line"
    fi
done

