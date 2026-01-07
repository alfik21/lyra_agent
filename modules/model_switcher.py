import json
import os
import subprocess
from pathlib import Path

from modules.model_paths import get_models_path, get_models_dir

# JEDNA, SPÓJNA KONFIGURACJA ŚCIEŻEK
MODELS_DIR = get_models_dir()
MAP_FILE = get_models_path()

# ===========================================
# POMOCNIKI ZAPISU/ODCZYTU (Zawsze UTF-8)
# ===========================================

def _load_map():
    if not MAP_FILE.exists():
        # Jeśli plik nie istnieje, tworzymy strukturę
        return {"active": "", "available": {}}
    try:
        return json.loads(MAP_FILE.read_text("utf-8"))
    except:
        return {"active": "", "available": {}}

def _save_map(data):
    global MAP_FILE, MODELS_DIR
    try:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        MAP_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        return
    except PermissionError:
        fallback = Path.home() / "lyra_agent" / "models.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        MAP_FILE = fallback
        MODELS_DIR = fallback.parent

# ===========================================
# SKANOWANIE (JEDNA KOMPLEKSOWA FUNKCJA)
# ===========================================

def tool_SCAN_MODELS(arg, system, log):
    """Skanuje dyski i automatycznie rejestruje nowe modele w Ollama."""
    arg_l = (arg or "").lower()
    fast_scan = "szybko" in arg_l or "fast" in arg_l
    no_ollama = "bez ollama" in arg_l or "no-ollama" in arg_l
    roots = []
    models_dir = get_models_dir()
    if models_dir.exists():
        roots.append(models_dir)
    archive = Path("/media/tomek/arhiwum/AI_MODELS")
    if archive.exists() and archive not in roots:
        roots.append(archive)
    if not roots:
        roots = [Path("/media/tomek")]
    data = _load_map()
    found_count = 0
    registered_count = 0

    roots = [r for r in roots if r.exists()]
    if not roots:
        return "❌ Nie znaleziono katalogu z modelami do skanowania."

    # Pobieramy listę modeli już zarejestrowanych w Ollama
    ollama_list = ""
    if not no_ollama:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            ollama_list = result.stdout or ""
        except Exception:
            ollama_list = ""

    for search_root in roots:
        base_depth = len(Path(search_root).parts)
        for root, _, files in os.walk(search_root):
            cur_depth = len(Path(root).parts) - base_depth
            max_depth = 1 if fast_scan else 4
            if cur_depth > max_depth:
                continue
            for file in files:
                if file.endswith(".gguf"):
                    model_key = Path(file).stem.lower()
                    full_path = str(Path(root) / file)
                    
                    # 1. Dodaj do bazy JSON Lyry, jeśli brakuje
                    if model_key not in data["available"]:
                        data["available"][model_key] = full_path
                        found_count += 1

                    # 2. AUTOMATYCZNA REJESTRACJA W OLLAMA (opcjonalna)
                    if not no_ollama and ollama_list and model_key not in ollama_list.lower():
                        print(f"📦 Rejestruję nowy model w Ollama: {model_key}...")
                        modelfile_content = f"FROM {full_path}"
                        temp_mf = Path("/tmp/lyra_modelfile")
                        temp_mf.write_text(modelfile_content)
                        try:
                            subprocess.run(["ollama", "create", model_key, "-f", str(temp_mf)], check=True)
                            registered_count += 1
                        except subprocess.CalledProcessError:
                            print(f"❌ Błąd rejestracji modelu {model_key}")
                        finally:
                            if temp_mf.exists():
                                temp_mf.unlink()

    if found_count > 0 or registered_count > 0:
        _save_map(data)
        return f"✅ Skanowanie OK! Znaleziono: {found_count}, zarejestrowano w Ollama: {registered_count}."
    
    return "🔍 Wszystkie modele są już zarejestrowane i aktualne."

# ===========================================
# LISTA MODELI (CZYTELNA I POSORTOWANA)
# ===========================================

def tool_MODEL_LIST(arg, system, log):
    data = _load_map()
    models = data.get("available", {})
    active = data.get("active", "")

    if not models:
        return "❌ Brak modeli w bazie. Użyj: lyra skanuj modele"

    out = ["📦 Dostępne modele lokalne:"]
    
    # Sortowanie alfabetyczne nazw dla lepszej czytelności
    for name in sorted(models.keys()):
        path = models[name]
        # Sprawdzamy czy to ten aktywny (ignorując wielkość liter)
        flag = " 🔥 [AKTYWNY]" if name.lower() == active.lower() else ""
        out.append(f" • {name}{flag}\n    ↳ {path}")

    out.append("\nUżyj: lyra użyj <nazwa>")
    return "\n".join(out)

# ===========================================
# PRZEŁĄCZNIK (INTELIGENTNY)
# ===========================================

def tool_MODEL_SWITCHER(user_input, log):
    data = _load_map()
    available = data.get("available", {})

    # Wyciągamy czystą nazwę z komendy
    raw_name = user_input.lower().replace("użyj", "").replace("zmień model na", "").strip()
    # Usuwamy .gguf jeśli użytkownik dopisał z przyzwyczajenia
    target = raw_name.replace(".gguf", "")

    if target in available:
        data["active"] = target
        _save_map(data)
        if log: log(f"Przełączono model na {target}")
        return f"✅ Aktywny model to teraz: {target}"
    
    # Próba znalezienia podobnego, jeśli użytkownik wpisał tylko kawałek nazwy
    for name in available.keys():
        if target in name:
            data["active"] = name
            _save_map(data)
            return f"✅ Nie znaleziono '{target}', ale przełączono na podobny: {name}"

    return f"❌ Model '{target}' nie istnieje. Wpisz 'lyra modele' by zobaczyć listę."

def get_active_local_model_name():
    data = _load_map()
    return data.get("active", "brak")
def set_active_local_model(model_name: str, log=None):
    """Uproszczona wersja dla kompatybilności wstecznej."""
    data = _load_map()
    if model_name in data.get("available", {}):
        data["active"] = model_name
        _save_map(data)
        return True
    return False
