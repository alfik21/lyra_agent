#!/usr/bin/env python3
import subprocess
import sys
import readline
AGENT = "./agent.py"

print("🟣 Lyra online. Pisz normalnie. 'exit' aby wyjść.\n")

while True:
    try:
        user_input = input("Ty > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n👋 Lyra: do zobaczenia")
        break

    if not user_input:
        continue

    if user_input.lower() in ("exit", "quit", "wyjdz"):
        print("👋 Lyra: zamykam sesję")
        break

    try:
        result = subprocess.run(
            [sys.executable, AGENT, user_input],
            text=True,
            capture_output=True
        )

        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print("\n--- [LOG: ostatnie 20 linii agent.log] ---")
            subprocess.run(["tail", "-n", "20", "logs/agent.log"])
            print(result.stderr.strip())

    except Exception as e:
        print(f"❌ Krytyczny błąd: {e}")

