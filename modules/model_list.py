import json
from modules.model_paths import get_models_path, get_models_dir

MAP_FILE = get_models_path()
MODELS_DIR = get_models_dir()

def tool_MODEL_LIST(arg, system, log):
    # Sprawdzenie katalogu z modelami
    if not MODELS_DIR.exists():
        return "❌ Katalog AI_MODELS nie istnieje lub nie jest zamontowany.\nSprawdź dysk /media/tomek/arhiwum."

    # Sprawdzenie pliku
    if not MAP_FILE.exists():
        return "[Lyra] Brak pliku models.json – uruchom: lyra aktualizuj modele"

    # Próba odczytu JSON
    try:
        data = json.loads(MAP_FILE.read_text())
    except Exception as e:
        return f"❌ Błąd podczas odczytu models.json: {e}"

    active = data.get("active", "")
    available = data.get("available", {})

    # Jeśli brak dostępnych modeli
    if not available:
        return "⚠️ models.json istnieje, ale nie ma w nim listy modeli.\nUżyj: lyra aktualizuj modele"

    msg = "📦 Dostępne modele lokalne:\n\n"

    # Sortuj alfabetycznie — czytelniej
    for name in sorted(available.keys(), key=lambda s: s.lower()):
        path = available[name]
        flag = " (AKTYWNY)" if name == active else ""
        msg += f" • {name}{flag}\n"
        msg += f"    ↳ {path}\n"

    msg += "\nUżyj: lyra użyj <model>\n"
    msg += "Przykład: lyra użyj hernes\n"

    return msg

