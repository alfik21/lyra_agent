import os
import json
import re
from datetime import datetime, timedelta

LOG_DIR = os.path.expanduser("~/lyra_agent/logs")
MEMORY_FILE = os.path.expanduser("~/lyra_agent/memory.json")

# --- AUTO-TWORZENIE KATALOGU LOGÓW ---
os.makedirs(LOG_DIR, exist_ok=True)

def tool_MEMORY_ANALYZE(arg, system_tool, log):
    """
    Analizuje logi i historię działań Lyry.
    Uczy się, które komendy pomogły i które błędy się powtarzają.
    """
    result = "🧠 Analiza pamięci Lyry:\n"

    try:
        recent = []

        # --- Wczytaj logi z ostatnich 7 dni ---
        for file in os.listdir(LOG_DIR):
            if file.endswith(".log"):
                path = os.path.join(LOG_DIR, file)
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if mtime > datetime.now() - timedelta(days=7):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        # ogranicz do 2000 linii żeby nie zjechać RAM-u
                        recent += lines[-2000:]

        corpus = " ".join(recent)

        # --- Liczenie zjawisk powtarzających się ---
        summary = {
            "audio_fixes": len(re.findall(r"pipewire|alsa|audio", corpus, re.I)),
            "net_fixes": len(re.findall(r"ping|nmcli|network|dns", corpus, re.I)),
            "system_errors": len(re.findall(r"error|failed|traceback", corpus, re.I)),
            "optimizations": len(re.findall(r"optimize|drop_caches|autoremove", corpus, re.I)),
        }

        result += (
            f"- Błędy systemowe: {summary['system_errors']}\n"
            f"- Naprawy sieci: {summary['net_fixes']}\n"
            f"- Naprawy dźwięku: {summary['audio_fixes']}\n"
            f"- Optymalizacje: {summary['optimizations']}\n"
        )

        # --- Heurystyki rekomendacji ---
        if summary["audio_fixes"] > 2:
            result += "\n🎧 Często naprawiam dźwięk — proponuję automatyczne monitorowanie PipeWire."

        if summary["net_fixes"] > 3:
            result += "\n🌐 Problemy z siecią pojawiają się regularnie — mogę aktywować auto-ping co 5 minut."

        if summary["system_errors"] > 5:
            result += "\n⚠️ Dużo błędów — proponuję `lyra zoptymalizuj system`."

        if log:
            log(result, "memory_ai.log")
        return result

    except Exception as e:
        return f"[Błąd MEMORY_ANALYZE] {e}"

def search_memory(query):
    """Przeszukuje bazę pamięci w poszukiwaniu podobnych tematów."""
    if not os.path.exists(MEMORY_FILE):
        return None

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memory_data = json.load(f)

        # Proste wyszukiwanie słów kluczowych w historii
        query_words = query.lower().split()
        for entry in reversed(memory_data):
            user_msg = entry.get("user", "").lower()
            if any(word in user_msg for word in query_words):
                return entry.get("assistant")
    except Exception as e:
        print(f"[DEBUG] Błąd przeszukiwania pamięci: {e}")

    return None
