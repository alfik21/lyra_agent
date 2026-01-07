#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AGENT = BASE_DIR / "agent.py"

print("🟣 Lyra online. Pisz normalnie. 'exit' aby wyjść.")

while True:
    try:
        user_input = input("Ty > ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("🟣 Lyra offline.")
            break

        # wołamy agent.py jak funkcję, NIE skrypt
        subprocess.run(
            [sys.executable, str(AGENT), user_input],
            check=False
        )

    except KeyboardInterrupt:
        print("\n⛔ Przerwano (Ctrl+C).")

