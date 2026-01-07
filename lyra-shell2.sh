#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

echo "Lyra online. Pisz normalnie. 'exit' aby wyjść."

while true; do
  read -rp "Ty > " CMD
  [[ "$CMD" == "exit" ]] && break
  ./agent.sh "$CMD"
done
