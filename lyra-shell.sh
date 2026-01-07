#!/usr/bin/env bash

AGENT="./agent.sh"

# kolory (bezpieczne dla readline)
RESET='\[\e[0m\]'
BOLD='\[\e[1m\]'
PURPLE='\[\e[38;5;135m\]'
BLUE='\[\e[38;5;75m\]'
GRAY='\[\e[38;5;245m\]'

MODE="lyra"

prompt() {
    if [[ "$MODE" == "lyra" ]]; then
        echo -ne "${BOLD}${PURPLE}Lyra${RESET} ${GRAY}›${RESET} "
    else
        echo -ne "${BOLD}${BLUE}bash${RESET} ${GRAY}›${RESET} "
    fi
}

echo "🟣 Lyra online"
echo "Komendy: :bash  :lyra  exit"
echo

while true; do
    read -e -p "$(prompt)" line || { echo; break; }
    [[ -z "$line" ]] && continue
    history -s "$line"

    case "$line" in
        exit)
            echo "👋 Wyjście z Lyry"
            break
            ;;
        :bash)
            MODE="bash"
            continue
            ;;
        :lyra)
            MODE="lyra"
            continue
            ;;
    esac

    if [[ "$MODE" == "bash" ]]; then
        bash -c "$line"
    else
    output=$("$AGENT" "$line" 2>&1)

if [[ "$output" == SYSTEM:* ]]; then
    echo -e "${GREEN}$output${RESET}"
elif [[ "$output" == TOOL:* ]]; then
    echo -e "${BLUE}$output${RESET}"
elif [[ "$output" == PROPOSE_TOOL:* ]]; then
    echo -e "${YELLOW}$output${RESET}"
elif [[ "$output" == *"Błąd"* || "$output" == *"ERROR"* ]]; then
    echo -e "${RED}$output${RESET}"
else
    echo -e "${PURPLE}$output${RESET}"
fi
 
done

