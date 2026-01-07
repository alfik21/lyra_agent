# brain.py — NOWA WERSJA
import subprocess, json, os
from modules.model_manager import get_active_local_model_path

def query_brain(prompt: str) -> str:
    """
    Ogólny interfejs do 'lokalnego mózgu' Lyry.
    Wywołuje aktywny model lokalny przez Ollama / llama.cpp.
    """
    model_path = get_active_local_model_path()

    if not model_path:
        return "[BŁĄD] Brak aktywnego modelu lokalnego. Użyj: lyra użyj <model>"

    try:
        cmd = [
            "ollama",
            "run",
            model_path,
            prompt
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            return f"[Błąd lokalnego modelu]: {result.stderr}"

        return result.stdout.strip()

    except Exception as e:
        return f"[Błąd lokalnego mózgu] {e}"

