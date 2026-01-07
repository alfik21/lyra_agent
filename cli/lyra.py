#!/usr/bin/env python3
import os, sys, subprocess

# pełna ścieżka do agenta
AGENT = os.path.expanduser("~/lyra_agent/agent.py")
VENV_PY = os.path.expanduser("~/lyra_agent/venv/bin/python")

def main():
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        print("Lyra → powiedz co robimy, np. 'lyra sprawdź internet'")
        return

    # uruchomienie agenta w tym samym venv
    result = subprocess.run(
        [VENV_PY, AGENT, prompt],
        capture_output=True,
        text=True
    )
    if result.stdout.strip():
        print(result.stdout)
    if result.stderr.strip():
        print(result.stderr)

if __name__ == "__main__":
    main()

