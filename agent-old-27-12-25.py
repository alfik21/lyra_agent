#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

import requests
from openai import OpenAI

# ======= IMPORTY MODUŁÓW =======
from modules.app_tools import tool_APP_CONTROL
from modules.audio_tools import tool_AUDIO_DIAG, tool_AUDIO_FIX
from modules.net_tools import tool_NET_INFO, tool_NET_DIAG, tool_NET_FIX
from modules.system_tools import tool_SYSTEM_DIAG, tool_SYSTEM_FIX, tool_AUTO_OPTIMIZE
from modules.app_guard import (
    tool_APP_GUARD,
    tool_APP_GUARD_STOP,
    tool_APP_GUARD_REMOVE,
    tool_APP_GUARD_LIST,
    tool_APP_GUARD_LOGS
)
from modules.tmux_tools import tool_TMUX_SCREEN_DIAG
from modules.brain import query_brain
from modules.system_monitor import get_status, analyze_status
from modules.systeminfo import tool_SYSINFO
from modules.watchdog import tool_WATCHDOG
from modules.voice_input import tool_VOICE_INPUT
from modules.memory_ai import tool_MEMORY_ANALYZE
from modules.desktop_tools import tool_DESKTOP_DIAG, tool_DESKTOP_FIX
from modules.log_analyzer import tool_LOG_ANALYZE
from modules.model_manager import tool_MODEL_MANAGER
from modules.model_router import query_model
from modules.mode_manager import tool_MODE_MANAGER
from modules.status_monitor import tool_STATUS_MONITOR
from modules.switch_model import switch_model
from modules.model_switcher import tool_MODEL_SWITCHER
from modules.opisy_modelow import tool_MODEL_INFO
from modules.model_list import tool_MODEL_LIST
from modules.model_describe import tool_MODEL_DESCRIBE
from modules.disk_tools import tool_DISK_DIAG

PENDING_CONFIRMATION = None

# ===============================
#    MAPA INTENCJI → NARZĘDZI
# ===============================

def detect_intent(user_text: str):
    t = user_text.lower().strip()

    # SYSTEM / DYSKI
    if "sprawdź dyski" in t or "sprawdz dyski" in t or "dyski" in t:
        return "DISK_DIAG", ""

    # INTERNET
    if "zdiagnozuj internet" in t or "diagnoza internetu" in t:
        return "NET_DIAG", "auto"
    if "napraw internet" in t:
        return "NET_FIX", "auto"

    # DŹWIĘK
    if "zdiagnozuj dźwięk" in t or "zdiagnozuj dzwiek" in t:
        return "AUDIO_DIAG", ""
    if "napraw dźwięk" in t or "napraw dzwiek" in t:
        return "AUDIO_FIX", ""

    # MODELE
    if t == "lista modeli" or t == "modele":
        return "MODEL_LIST", ""

    if t.startswith("użyj modelu") or t.startswith("uzyj modelu") or t.startswith("lyra użyj"):
        model = t.replace("lyra","").replace("użyj modelu","").replace("uzyj modelu","").strip()
        return "MODEL_SWITCHER", model

    # MÓZG TEST
    if "przetestuj połączenie z mózgiem" in t or "test mózgu" in t:
        return "BRAIN_TEST", ""

    return None, None

def disk_diag():
    out = []
    out.append("=== DYSKI I SYSTEM PLIKÓW ===\n")

    out.append("➤ lsblk:")
    out.append(system_tool("lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE"))

    out.append("\n➤ df -h:")
    out.append(system_tool("df -h"))

    out.append("\n➤ blkid:")
    out.append(system_tool("blkid"))

    return "\n".join(out)

# Dodatkowe funkcje związane z obsługą modeli AI:

def tool_APP_GUARD(app, system_tool, log):
    """
    Watchdog dla aplikacji (np. Lutris).
    Zwraca prosty SYSTEM, który monitoruje proces.
    """
    if not app:
        return "[APP_GUARD] Nie podano aplikacji."

    # Log informacyjny
    log(f"[APP_GUARD] Monitorowanie aplikacji: {app}", "agent.log")

    # Na razie zwracamy prosty SYSTEM – pełny watchdog mogę Ci dopisać później
    return f"SYSTEM: ps -ef | grep {app}"

def tool_SYSTEM_FIX(arg, system_tool, log):
    global PENDING_CONFIRMATION
    #pm = detect_package_manager(system_tool)

    #if not pm:
    #    return "[BŁĄD] Nie wykryto menedżera pakietów (ani dnf, ani apt)."

   # if pm == "dnf":
   #     cmd = "sudo dnf upgrade -y"
   # else:
    #    cmd = "sudo apt update && sudo apt upgrade -y"

    PENDING_CONFIRMATION = cmd_to_run
    return "Czy chcesz wykonać aktualizację systemu? (tak/nie)"

def scan_models(base_dirs):
    """
    Przeszukuje podane katalogi i ich podkatalogi w poszukiwaniu plików modeli AI
    (np. z rozszerzeniami .gguf, .ggml, .bin, .pt) i zwraca słownik
    {nazwa_modelu: pełna_ścieżka}.
    """
    found = {}
    for base in base_dirs:
        # Jeśli katalog nie istnieje, pomiń go
        if not base:
            continue
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            for fname in files:
                low = fname.lower()
                if low.endswith(('.gguf', '.ggml', '.bin', '.pt')):
                    model_name = Path(fname).stem
                    found[model_name] = os.path.join(root, fname)
    return found

def tool_MODEL_LIST(arg: str, *unused) -> str:
    """
    Odczytuje plik models.json (zgodnie z konfiguracją) i zwraca listę
    dostępnych modeli w postaci czytelnego tekstu. Jeśli plik lub lista są
    puste, zwraca odpowiedni komunikat.
    """
    path = MODELS_FILE
    if not path or not os.path.exists(path):
        return "Plik models.json nie został znaleziony."
    try:
        data = json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return "Nie udało się odczytać models.json."
    available = data.get("available", {})
    if not available:
        return "Lista modeli jest pusta."
    out_lines = []
    for i, (mname, mpath) in enumerate(available.items(), start=1):
        out_lines.append(f"{i}. {mname} -> {mpath}")
    return "\n".join(out_lines)

def tool_MODEL_SCAN(arg: str, *unused) -> str:
    """
    Skanuje system plików w poszukiwaniu plików modeli AI i aktualizuje
    plik models.json. Argument może zawierać ścieżkę katalogu do przeszukania;
    jeśli jest pusty, używa domyślnego katalogu z konfiguracji (klucz
    'models_dir') lub katalogu bieżącego.
    Zwraca informację o liczbie znalezionych modeli.
    """
    # Ustal katalogi do skanowania
    search_dirs = []
    if arg:
        search_dirs.append(arg)
    # Jeśli w konfiguracji podany jest katalog modeli, użyj go
    cfg_dir = cfg.get("models_dir")
    if cfg_dir:
        search_dirs.append(cfg_dir)
    # Dodaj katalog lokalny z config local_model_path, jeśli istnieje
    lm_path = cfg.get("local_model_path")
    if lm_path:
        search_dirs.append(str(Path(lm_path).resolve().parent))
    # Jeśli nadal brak katalogów, przeszukaj katalog bazy programu
    if not search_dirs:
        search_dirs.append(str(BASE_DIR))
    # Wykonaj skan
    found = scan_models(search_dirs)
    if not found:
        return "Nie znaleziono żadnych modeli AI w podanych katalogach."
    # Wczytaj istniejące dane
    data = {"available": {}}
    if MODELS_FILE and os.path.exists(MODELS_FILE):
        try:
            data = json.load(open(MODELS_FILE, "r", encoding="utf-8"))
        except Exception:
            data = {"available": {}}
    # Zaktualizuj lub uzupełnij plik
    if "available" not in data:
        data["available"] = {}
    data["available"].update(found)
    try:
        with open(MODELS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        return "Błąd zapisu do models.json."
    return f"Dodano lub zaktualizowano {len(found)} modeli."

def tool_MODEL_RECOMMEND(arg: str, *unused) -> str:
    """
    Proponuje optymalny model AI do uruchomienia na lokalnym sprzęcie na
    podstawie dostępnych modeli oraz ogólnych wytycznych dotyczących RAM/VRAM.
    Jeśli nie jesteśmy w stanie zebrać informacji o sprzęcie, zwraca ogólne
    wskazówki.
    Argument może pozostać pusty.
    """
    # Wczytaj listę modeli
    path = MODELS_FILE
    if not path or not os.path.exists(path):
        return "Plik models.json nie istnieje, najpierw wykonaj skan modeli."
    try:
        data = json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return "Nie udało się odczytać models.json."
    available = data.get("available", {})
    if not available:
        return "Brak modeli w models.json. Wykonaj skan, aby je dodać."
    # Spróbuj odczytać pamięć RAM za pomocą polecenia 'free -m'
    ram_total = None
    try:
        out = system_tool("free -m")
        for line in out.splitlines():
            if line.lower().startswith("mem:"):
                parts = line.split()
                # kolumna 1: total, 2: used, 3: free
                ram_total = int(parts[1])
                break
    except Exception:
        ram_total = None
    # Logika wyboru modelu: preferuj modele z sufiksem Q8_0 lub Q4_0 przy mniejszej pamięci
    preferred = []
    for name in available.keys():
        lname = name.lower()
        if "q8" in lname or "q4" in lname:
            preferred.append(name)
    # Przykład minimalnych wymagań: Mistral 7B Q4 ~8GB RAM, Q8 ~12GB RAM;
    # Bielik 11B Q8 ~12GB VRAM, pełny ~24GB VRAM.
    if ram_total:
        if ram_total < 16 * 1024:  # mniej niż 16 GB RAM
            if preferred:
                return ("Masz mniej niż 16 GB RAM. Zalecane są silnie skwantyzowane modele, "
                        f"np. {preferred[0]}, które zużywają mniej pamięci.")
            else:
                return ("Masz mniej niż 16 GB RAM i nie znaleziono modeli skwantyzowanych. "
                        "Rozważ pobranie wersji Q4 lub Q8 modelu Bielik lub Mistral.")
        elif ram_total < 32 * 1024:  # 16-32 GB RAM
            if preferred:
                return ("Masz od 16 do 32 GB RAM. Możesz uruchomić modele w wersjach Q8. "
                        f"Dostępne modele: {', '.join(preferred)}.")
            else:
                return ("Masz od 16 do 32 GB RAM, ale brak wersji Q8/Q4 w models.json. "
                        "Rozważ pobranie takiej wersji quantized.")
        else:
            # 32 GB RAM lub więcej
            full_models = [n for n in available if not any(x in n.lower() for x in ["q8", "q4", "q5"])]
            if full_models:
                return ("Masz co najmniej 32 GB RAM. Możesz uruchomić pełne wersje modeli. "
                        f"Dostępne pełne modele: {', '.join(full_models)}.")
            else:
                return ("Masz co najmniej 32 GB RAM, ale brak pełnych wersji modeli w models.json. "
                        "Możesz używać wersji Q8/Q4 lub pobrać pełną wersję z internetu.")
    else:
        # Nie udało się określić RAM – podaj ogólne wskazówki
        if preferred:
            return ("Nie mogę odczytać ilości RAM w systemie. Polecam użyć modeli Q8 lub Q4, "
                    f"np. {preferred[0]}, które mają niższe wymagania sprzętowe. Jeśli masz dużo RAM, "
                    "możesz spróbować pełnej wersji modelu.")
        else:
            return ("Nie mogę odczytać ilości RAM w systemie i brak wersji Q8/Q4 w models.json. "
                    "Rozważ pobranie modelu quantized (Q8, Q4) lub podaj liczbę dostępnego RAM, "
                    "aby zaproponować odpowiedni model.")

# Funkcja detect_intent_local definiowana lokalnie zamiast oddzielnego modułu.
def detect_intent_local(user_prompt: str):
    """
    Lokalny router intencji użytkownika (BEZ użycia LLM).

    Zadanie funkcji:
    - na podstawie słów kluczowych rozpoznać, CO użytkownik chce zrobić
    - zwrócić krotkę: (NAZWA_NARZĘDZIA, ARGUMENT)
    - jeżeli nie rozpozna intencji → (None, None)

    Dlaczego to ważne:
    - chroni „mózg” (LLM) przed zalewem niepotrzebnych promptów
    - zapobiega błędom typu: Argument list too long (ollama)
    - przyspiesza reakcję agenta
    """

    # Normalizacja wejścia:
    # - lowercase
    # - usunięcie nadmiarowych spacji
    prompt = user_prompt.lower().strip()

    # =========================================================
    # 🧠 TEST POŁĄCZENIA / MÓZGU
    # =========================================================
    # Różne warianty, literówki, język potoczny
    if any(k in prompt for k in [
        "przetestuj połączenie",
        "test połączenia",
        "czy połączenie działa",
        "czy polaczenie dziala",
        "czy po laczenie dziala",
        "czy działa połączenie",
        "czy dziala",
        "czy mózg działa",
        "czy mozg dziala"
    ]):
        return "BRAIN_TEST", ""

    # =========================================================
    # 🌐 SIEĆ / INTERNET
    # =========================================================
    if any(k in prompt for k in [
        "sprawdź internet",
        "sprawdz internet",
        "zdiagnozuj internet",
        "internet nie działa",
        "problem z internetem",
        "diagnostyka sieci"
    ]):
        return "NET_DIAG", "auto"
        
        
        
        
    # ===============================================
# SYSTEM INFO
# ===============================================
    if any(k in prompt for k in [
        "system info",
        "system-info",
        "sprawdź system",
        "sprawdz system",
        "informacje o systemie",
        "w jakim systemie",
        "w jakim systemie jesteś",
        "w jakim systemie jestes",
        "jaki to system",
    ]):
        return "SYSINFO", ""

# ===============================================
# SYSTEM DIAG
# ===============================================
    if any(k in prompt for k in [
        "zdiagnozuj system",
        "diagnoza systemu",
        "diagnostyka systemu",
    ]):
        return "SYSTEM_DIAG", ""

# ===============================================
# STATUS / GDZIE JESTES
# ===============================================
    if any(k in prompt for k in [
        "gdzie jesteś",
        "gdzie jestes",
        "status systemu",
        "monitor systemu",
    ]):
        return "STATUS_MONITOR", ""


    # =========================================================
    # 💽 DYSKI / SYSTEM PLIKÓW
    # =========================================================
    


    
    if any(k in prompt for k in [
        "sprawdź dyski",
        "pokaż dyski",
        "dyski",
        "partycje",
        "system plików",
        "wolne miejsce",
        "ile mam miejsca"
    ]):
        return "DISK_DIAG", ""

    # =========================================================
    # 🧾 PAMIĘĆ / RETROSPEKCJA
    # =========================================================
    if any(k in prompt for k in [
        "co było",
        "co bylo",
        "co się popsuło",
        "co sie popsuło",
        "ostatnio",
        "dlaczego nie działało",
        "co naprawialiśmy",
        "jaki był problem",
        "jaki byl problem"
    ]):
        return "MEMORY_SUMMARY", ""

    # =========================================================
    # 🧠 MODELE AI – LISTA DOSTĘPNYCH MODELI
    # =========================================================
    if any(k in prompt for k in [
        "lista modeli",
        "pokaż modele",
        "pokaż listę modeli",
        "modele lokalne",
        "lokalne modele",
        "lista lokalnych modeli"
    ]):
        return "MODEL_LIST", ""

    # =========================================================
    # 🔍 MODELE AI – SKANOWANIE / ODŚWIEŻANIE
    # =========================================================
    if any(k in prompt for k in [
        "szukaj modeli",
        "poszukaj modeli",
        "odśwież listę modeli",
        "przeszukaj dysk",
        "przeszukaj komputer",
        "przeskanuj modele",
        "skanuj modele"
    ]):
        return "MODEL_SCAN", ""

    # =========================================================
    # 🤖 MODELE AI – REKOMENDACJA / WYBÓR
    # =========================================================
    if any(k in prompt for k in [
        "optymalny model",
        "jaki model",
        "który model",
        "lepszy model",
        "jaki model wybrać",
        "model do mojego komputera"
    ]):
        return "MODEL_RECOMMEND", ""

    # =========================================================
    # 🔊 DŹWIĘK / AUDIO
    # =========================================================
    if any(k in prompt for k in [
        "zdiagnozuj dźwięk",
        "diagnostyka dźwięku",
        "problemy z dźwiękiem",
        "brak dźwięku"
    ]):
        return "AUDIO_DIAG", "auto"

    # =========================================================
    # 🖥️ ŚRODOWISKO GRAFICZNE – CINNAMON
    # =========================================================
    if "cinnamon" in prompt:
        # Jeżeli użytkownik wyraźnie chce naprawy
        if any(k in prompt for k in ["napraw", "fix", "naprawa"]):
            return "DESKTOP_FIX", "cinnamon"
        # Domyślnie: diagnostyka
        return "DESKTOP_DIAG", "cinnamon"

    # =========================================================
    # 📄 ANALIZA LOGÓW
    # =========================================================
    # Akceptuje polecenia typu:
    # - "analizuj log ~/.xsession-errors"
    # - "analiza log /var/log/syslog"
    if "analizuj log" in prompt or "analiza log" in prompt:
        parts = user_prompt.split("log", 1)
        arg_path = parts[1].strip() if len(parts) > 1 else ""
        return "LOG_ANALYZE", arg_path
        
    # ============================================
    # ===========================
    #   APLIKACJE – WATCHDOG
    # ===========================
    if any(k in prompt for k in [
        "pilnuj", "watchdog", "monitoruj", "nadzoruj", "pilnowanie",
        "strzeż", "kontroluj aplikację", "pilnuj lutris"
    ]):
        # wyciągamy nazwę aplikacji po słowie „pilnuj”
        parts = prompt.split()
        try:
            app = parts[parts.index("pilnuj") + 1]
        except:
            app = "auto"
        return "APP_GUARD", app
 

    if any(k in prompt for k in [
        "updatuj system",
        "update systemu",
        "zaktualizuj system",
        "wykonaj aktualizacje systemu",
        "aktualizacja systemu",
        "aktualizacje"
    ]):
        return "SYSTEM_FIX", "update"

    if prompt.startswith("pilnuj "):
        return "APP_GUARD", prompt.replace("pilnuj ", "")

    if prompt.startswith("zatrzymaj watchdog "):
        return "APP_GUARD_STOP", prompt.replace("zatrzymaj watchdog ", "")

    if prompt.startswith("usuń watchdog "):
        return "APP_GUARD_REMOVE", prompt.replace("usuń watchdog ", "")

    if "pilnowane" in prompt:
        return "APP_GUARD_LIST", ""

    if prompt.startswith("logi "):
        return "APP_GUARD_LOGS", prompt.replace("logi ", "")
    # =========================================================
    # ❓ BRAK ROZPOZNANEJ INTENCJI
    # =========================================================
    return None, None


# ======= ŚCIEŻKI I KONFIGURACJA =======
BASE_DIR = Path(__file__).resolve().parent
CFG_PATH = BASE_DIR / "config.json"
PAMIEC_ROBOCZA = (BASE_DIR / "agent_memory.json").resolve()
PAMIEC_DLUGA = (BASE_DIR / "agent_memory_long.json").resolve()
PAMIEC_ARCHIWUM = (BASE_DIR / "agent_memory_archive.json").resolve()

for sciezka, domyslna in [
    (PAMIEC_ROBOCZA, []),
    (PAMIEC_DLUGA, {}),
    (PAMIEC_ARCHIWUM, [])
]:
    if not sciezka.exists():
        sciezka.write_text(
            json.dumps(domyslna, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


# Upewnij się, że plik konfiguracyjny istnieje.
if not CFG_PATH.exists():
    raise SystemExit(f"[Lyra] Brak {CFG_PATH}. Utwórz config.json.")

# Wczytaj konfigurację i upewnij się, że wymagane klucze mają wartości domyślne.
cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
default_keys = {
    "api_key": "key"
    "user_name": "Tomek",
    "temperature": 0.4,
    "backend": "local",
    "local_model": "aya-23-8B-f16",
    "openai_model": "gpt-5.1",
    "ollama_model": "mistral",
    "n_ctx": 4096,
    "n_batch": 512,
    "mlock": False,
    "tools_enabled": "true",
    "threads": 12,
    "model": "aya-23-8B-f16",
    
    "local_model_path": "/media/tomek/arhiwum/AI_MODELS/aya-23-8B-f16.gguf",
    "memory_file": "agent_memory.json",
    "state_file": "agent_state.json",
    "models_file": "models.json",
    "logs_dir": "logs",
    # cfg.get("logs_dir", "logs")
    }
#for k, v in default_keys.items():
 #   if k not in cfg:
  #      cfg[k] = v
#FILTR ŚMIECI (BARDZO WAŻNE)

# =========================
# FILTR OCHRONNY (ŚMIECI / LOGI / BŁĘDY)
# =========================

def czy_warto_zapamietac(tekst: str) -> bool:
    if not tekst:
        return False

    zakazane = [
        "Argument list too long",
        "timed out",
        "Traceback",
        "[Errno",
        "HTTPConnectionPool",
        "Read timed out",
        "ollama",
        "ERROR",
        "Exception"
    ]
    return not any(z in tekst for z in zakazane)

# =========================
# LIMITY BEZPIECZEŃSTWA
# =========================

MAX_KONTEKST = 5
MAX_DLUGOSC_TEKSTU = 1200
MAX_DLUGOSC_PROMPTU = 3500

# =========================
# PAMIĘĆ ROBOCZA (KRÓTKA)
# =========================

def wczytaj_pamiec():
    return json.loads(PAMIEC_ROBOCZA.read_text(encoding="utf-8"))

def zapisz_pamiec(wpis: dict):
    pamiec = wczytaj_pamiec()

    tresc = wpis.get("assistant") or wpis.get("output") or ""
    if tresc and not czy_warto_zapamietac(tresc):
        return

    if wpis.get("assistant") and len(wpis["assistant"]) > MAX_DLUGOSC_TEKSTU:
        wpis["assistant"] = wpis["assistant"][:MAX_DLUGOSC_TEKSTU] + " …[ucięto]"

    pamiec.append(wpis)

    PAMIEC_ROBOCZA.write_text(
        json.dumps(pamiec, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    kompresuj_pamiec_jesli_trzeba()

# =========================
# KOMPRESJA → ARCHIWUM (NIC NIE GINIE)
# =========================

def kompresuj_pamiec_jesli_trzeba():
    pamiec = wczytaj_pamiec()
    if len(pamiec) < 25:
        return

    archiwum = json.loads(PAMIEC_ARCHIWUM.read_text(encoding="utf-8"))

    stare = pamiec[:-10]
    archiwum.extend(stare)

    podsumowanie = {
        "time": datetime.now().isoformat(),
        "type": "PODSUMOWANIE",
        "content": "Starsza rozmowa przeniesiona do archiwum."
    }

    PAMIEC_ARCHIWUM.write_text(
        json.dumps(archiwum, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    PAMIEC_ROBOCZA.write_text(
        json.dumps(pamiec[-10:] + [podsumowanie], indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

# =========================
# PAMIĘĆ DŁUGOTERMINOWA (NIEŚMIERTELNA)
# =========================

def zapamietaj_na_zawsze(klucz: str, wartosc):
    dane = json.loads(PAMIEC_DLUGA.read_text(encoding="utf-8"))
    dane[klucz] = wartosc

    PAMIEC_DLUGA.write_text(
        json.dumps(dane, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

# =========================
# BUDOWA KONTEKSTU DO MÓZGU
# =========================

def pobierz_kontekst_do_promptu():
    pamiec = wczytaj_pamiec()
    return [
        m for m in pamiec
        if m.get("type") == "TEXT"
    ][-MAX_KONTEKST:]

# =========================
# OCHRONA MÓZGU (PROMPT)
# =========================

def zabezpiecz_prompt(prompt: str) -> str:
    if len(prompt) > MAX_DLUGOSC_PROMPTU:
        log("PROMPT ZA DŁUGI → SKRACAM", "agent.log")
        return prompt[-MAX_DLUGOSC_PROMPTU:]
    return prompt


## =========================
# TEST MÓZGU (FUNKCJA POMOCNICZA – BEZPIECZNA)
# =========================

def test_mozgu(cfg):
    """
    Test połączenia z lokalnym mózgiem.
    Zawsze zwraca aktualnie załadowany model.
    """
    model = (
        cfg.get("model")
        or cfg.get("local_model")
        or cfg.get("ollama_model")
        or "nieznany"
    )
    out = query_brain("Odpowiedz krótko: czy działasz?")
    return f"Myślenie lokalne działa, Tomek. Aktywny model: {model}.\n\n{out}"
    local_model = cfg.get("local_model")
    
def polish_guard(text: str) -> str:
    return (
        "ODPOWIADAJ WYŁĄCZNIE PO POLSKU.\n"
        "NIE UŻYWAJ JĘZYKA ANGIELSKIEGO.\n"
        "BĄDŹ TECHNICZNY I KONKRETNY.\n\n"
        + text
    )
    

#lyra przetestuj połączenie z mózgiem
#lyra zdiagnozuj dźwięk
#lyra sprawdź dyski
#lyra zdiagnozuj cinnamon



# Zapisz zaktualizowaną konfigurację na dysk, aby nowe klucze się zachowały.
CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# Ustaw domyślną nazwę użytkownika, jeśli brak.
if "user_name" not in cfg:
    cfg["user_name"] = "Tomek"
    CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# ======= LOGOWANIE =======
# Zdefiniuj katalog logów i upewnij się, że istnieje.
LOGS_DIR = BASE_DIR / cfg.get("logs_dir", "logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def log(line: str, filename: str = "agent.log"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (LOGS_DIR / filename).open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")

# ======= ZARZĄDZANIE PAMIĘCIĄ =======
# Ścieżki do plików pamięci i stanu na podstawie konfiguracji.
MEMORY_PATH = (BASE_DIR / cfg.get("memory_file", "agent_memory.json")).resolve()
STATE_PATH = (BASE_DIR / cfg.get("state_file", "agent_state.json")).resolve()

# Upewnij się, że pliki pamięci i stanu istnieją.
if not MEMORY_PATH.exists():
    MEMORY_PATH.write_text("[]", encoding="utf-8")
if not STATE_PATH.exists():
    STATE_PATH.write_text("{}", encoding="utf-8")

def load_memory():
    """Wczytaj historię rozmowy z dysku."""
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_memory(entry: dict):
    """Dodaj wpis pamięci do historii rozmowy."""
    mem = load_memory()
    mem.append(entry)
    MEMORY_PATH.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")

def remember(user: str, assistant: str):
    """Zapamiętaj wymianę tekstową użytkownik/asystent."""
    save_memory({
        "time": datetime.now().isoformat(),
        "type": "TEXT",
        "user": user,
        "assistant": assistant
    })

def remember_entry(entry_type: str, **fields):
    """Zapamiętaj zdarzenie inne niż tekstowe, np. użycie narzędzia lub wykonanie systemowe."""
    entry = {"time": datetime.now().isoformat(), "type": entry_type}
    entry.update(fields)
    save_memory(entry)

# ======= STAN PRACY (STATE) =======
def load_state() -> dict:
    """Wczytaj zapisany stan agenta z dysku."""
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_state(state: dict):
    """Zapisz stan agenta na dysku."""
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def update_state(patch: dict):
    """Uaktualnij zapamiętany stan częściową poprawką."""
    st = load_state()
    st.update(patch)
    save_state(st)

# ======= NARZĘDZIA SYSTEMOWE =======
def system_tool(cmd: str, timeout: int = 15) -> str:
    """Wykonaj polecenie powłoki, opcjonalnie prosząc o potwierdzenie sudo."""
    log(f"SYSTEM CMD: {cmd}", "system.log")
    # optional guard for sudo
    if "sudo" in cmd:
        print("⚠️ Polecenie wymaga sudo. Potwierdź: TAK")
        if input("> ").strip().lower() != "tak":
            return "❌ Anulowano przez użytkownika."
    try:
        return subprocess.check_output(
            cmd, shell=True,
            stderr=subprocess.STDOUT,
            timeout=timeout, text=True
        )
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] {cmd}"
    except subprocess.CalledProcessError as e:
        return e.output or "[ERROR]"
        
        
def handle_confirmation(user_prompt: str):
    global PENDING_CONFIRMATION
    if not PENDING_CONFIRMATION:
        return None

    p = user_prompt.lower().strip()

    if p in ["tak", "y", "yes", "potwierdzam", "lyra tak", "lyra potwierdzam"]:
        cmd = PENDING_CONFIRMATION
        PENDING_CONFIRMATION = None
        print(f"SYSTEM: {cmd}")
        return system_tool(cmd)

    if p in ["nie", "n", "no", "anuluj"]:
        print("❎ Anulowano.")
        PENDING_CONFIRMATION = None
        return ""

    print("❗ Oczekuję potwierdzenia (tak/nie).")
    return ""

def detect_package_manager(system_tool):
    """
    Automatyczna detekcja menedżera pakietów:
    - dnf (Fedora / Nobara / RHEL)
    - apt (Ubuntu / Mint / Debian)
    """
    if system_tool("command -v dnf").strip():
        return "dnf"
    if system_tool("command -v apt").strip():
        return "apt"
    return None

def tmux_capture(lines: int = 500) -> str:
    """Przechwyć dane z panelu tmux."""
    cmd = f"tmux capture-pane -pS -{lines}"
    return system_tool(cmd, timeout=3)

# ======= WYBÓR MODELU =======
MODELS_FILE = cfg.get("models_file")

def pick_local_model(cfg: dict):
    """Wybierz model lokalny z models.json na podstawie konfiguracji."""
    wanted = (cfg.get("local_model") or "").lower()
    if not MODELS_FILE or not os.path.exists(MODELS_FILE):
        return "[Lyra-System] Brak odpowiedzi z narzędzia."
    data = json.load(open(MODELS_FILE, "r", encoding="utf-8"))
    for name, path in data.get("available", {}).items():
        if wanted and wanted in name.lower():
            # Zapisz ścieżkę w konfiguracji do późniejszego użycia
            cfg["local_model_path"] = path
            return name, path
    return None, None

# Określ, którego modelu użyć przy starcie: lokalnego czy OpenAI.
local_name, local_path = pick_local_model(cfg)
if cfg.get("backend") == "local" and local_path:
    cfg["model"] = local_name
    cfg["local_model_path"] = local_path
else:
    cfg["backend"] = "openai"

def pick_openai_model(cfg: dict) -> str:
    """Zwróć nazwę modelu OpenAI z konfiguracji lub domyślną."""
    return cfg.get("openai_model") or cfg.get("model") or "gpt-5.1"

# Zainicjuj klienta OpenAI, jeśli podano klucz API.
client = OpenAI(api_key=cfg.get("api_key", "")) if cfg.get("api_key") else None

# ======= URUCHAMIANIE NARZĘDZI =======
# ============================
#   NARZĘDZIA LYRY – DISPATCH
# ============================
def tool_dispatch(name: str, arg: str) -> str:
    """
    Centralny router narzędzi. Każda komenda Lyry po wykryciu intencji
    trafia tutaj, a dalej jest kierowana do odpowiedniego modułu.
    """
    name = (name or "").strip().upper()

    # --- test mózgu ---
    if name == "BRAIN_TEST":
        return test_mozgu(cfg)

    # --- pamięć tekstowa ---
    if name == "MEMORY_SUMMARY":
        mem = load_memory()
        if not mem:
            return "Brak zapisanej historii."
        last = mem[-20:]
        out = ["Ostatnie wpisy pamięci:"]
        for m in last:
            u = m.get("user", "").strip()
            a = m.get("assistant", "").strip()
            if u or a:
                out.append(f"- {u} → {a[:120]}")
        return "\n".join(out)

    # =========================
    #        SIEĆ
    # =========================
    if name == "NET_INFO":
        return tool_NET_INFO(arg, system_tool, log)

    if name == "NET_DIAG":
        return tool_NET_DIAG(arg, system_tool, log)

    if name == "NET_FIX":
        return tool_NET_FIX(arg, system_tool, log)

    # =========================
    #        DŹWIĘK
    # =========================
    if name == "AUDIO_DIAG":
        return tool_AUDIO_DIAG(arg, system_tool, log)

    if name == "AUDIO_FIX":
        return tool_AUDIO_FIX(arg, system_tool, log)

    # =========================
    #        SYSTEM
    # =========================
    if name == "SYSTEM_DIAG":
        return tool_SYSTEM_DIAG(arg, system_tool, log)

    if name == "SYSTEM_FIX":
        return tool_SYSTEM_FIX(arg, system_tool, log)

    if name == "AUTO_OPTIMIZE":
        return tool_AUTO_OPTIMIZE(arg, system_tool, log)

    if name == "SYSINFO":
        return tool_SYSINFO(arg, system_tool, log)

    # =========================
    #        DESKTOP / GUI
    # =========================
    if name in ["CINNAMON_DIAG", "KDE_DIAG", "GNOME_DIAG", "XFCE_DIAG", "DESKTOP_DIAG"]:
        return tool_DESKTOP_DIAG(arg, system_tool, log)

    if name in ["CINNAMON_FIX", "KDE_FIX", "GNOME_FIX", "XFCE_FIX", "DESKTOP_FIX"]:
        return tool_DESKTOP_FIX(arg, system_tool, log)

    # =========================
    #        TMUX
    # =========================
    if name == "TMUX_SCREEN_DIAG":
        return tool_TMUX_SCREEN_DIAG(arg, system_tool, log)

    # =========================
    #       WATCHDOG / STATUS
    # =========================
    if name == "STATUS_MONITOR":
        return tool_STATUS_MONITOR(arg, system_tool, log)

    if name == "WATCHDOG":
        return tool_WATCHDOG(arg, system_tool, log)

    # =========================
    #          LOGI
    # =========================
    if name == "LOG_ANALYZE":
        return tool_LOG_ANALYZE(arg, system_tool, log)

    # =========================
    #        PAMIĘĆ AI
    # =========================
    if name == "MEMORY_ANALYZE":
        return tool_MEMORY_ANALYZE(arg, system_tool, log)

    # =========================
    #        MODELE
    # =========================
    if name == "MODEL_LIST":
        return tool_MODEL_LIST(arg, system_tool, log)

    if name == "MODEL_MANAGER":
        return tool_MODEL_MANAGER(arg, system_tool, log)

    if name in ["MODEL_SWITCHER", "PRZEŁĄCZNIK_MODELI"]:
        return switch_model(arg, log)

    if name == "MODEL_DESCRIBE":
        return tool_MODEL_DESCRIBE(arg, system_tool, log)

    if name == "MODEL_INFO":
        return tool_MODEL_INFO(arg, system_tool, log)
    
        # =========================
    # MODELE – SKANOWANIE / INFO / REKOMENDACJA
    # =========================

    if name == "MODEL_SCAN":
        return tool_MODEL_SCAN(arg)

   # if name == "MODEL_LIST":
    #    return tool_MODEL_LIST(arg)

    if name == "MODEL_RECOMMEND":
        return tool_MODEL_RECOMMEND(arg)

    
    # =========================
    #        APLIKACJE
    # =========================
    if name == "APP_CONTROL":
        return tool_APP_CONTROL(arg, system_tool, log)

    #if name == "APP_GUARD":
     #   return tool_APP_GUARD(arg, system_tool, log)

    # =========================
    #        DYSKI
    # =========================
    if name == "DISK_DIAG":
        return disk_diag()

    # =========================
    #    WEJŚCIE GŁOSOWE
    # =========================
    if name == "VOICE_INPUT":
        return tool_VOICE_INPUT(arg, system_tool, log)


    # ==========================
    #   WATCHDOG / APLIKACJE
    # ==========================
    if name == "APP_GUARD":
        return tool_APP_GUARD(arg, system_tool, log)

    # ==========================
    #   SYSTEM FIX / UPDATE
    # ==========================
    #if name == "SYSTEM_FIX":
     #   return tool_SYSTEM_FIX(arg)


    if name == "APP_GUARD": return tool_APP_GUARD(arg)
    if name == "APP_GUARD_STOP": return tool_APP_GUARD_STOP(arg)
    if name == "APP_GUARD_REMOVE": return tool_APP_GUARD_REMOVE(arg)
    if name == "APP_GUARD_LIST": return tool_APP_GUARD_LIST(arg)
    if name == "APP_GUARD_LOGS": return tool_APP_GUARD_LOGS(arg)

    # =========================
    #     BRAK NARZĘDZI
    # =========================
    return f"[Lyra] Nie znam narzędzia: {name}"


# ======= BANER INFORMACYJNY =======
def print_lyra_banner(cfg):
    """
    Drukuje baner informacyjny podsumowujący wybrany backend, model oraz dostępność internetu.
    """
    mode = "LOCAL" if cfg.get("backend") == "local" else "ONLINE"
    model = cfg.get("model") if mode == "LOCAL" else pick_openai_model(cfg)
    net = "✅ jest" if cfg.get("internet", True) else "❌ brak"
    print(f"[Lyra] Żądany model lokalny: {cfg.get('local_model', '')}")
    if mode == "LOCAL":
        print(f"[Lyra MODEL] Wybrano model lokalny: {cfg.get('model')}")
        print(f"[Lyra MODEL] Ścieżka: {cfg.get('local_model_path')}")
    else:
        print(f"[Lyra MODEL] Backend zdalny (OpenAI)")
    print(f"[Lyra • Tryb: {mode} • Model: {model} • Internet: {net}]")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ======= GŁÓWNA PĘTLA WYKONAWCZA =======
# ======= GŁÓWNA PĘTLA WYKONAWCZA =======
def run_once(user_prompt: str):
    # ============================================
    # SYSTEM POTWIERDZANIA OPERACJI
    # ============================================
    result = handle_confirmation(user_prompt)
    if result is not None:
        return result

# ============================================
# SYSTEM POTWIERDZANIA POLECEŃ
# ============================================
def handle_confirmation(user_prompt: str):
    global PENDING_CONFIRMATION

    if not PENDING_CONFIRMATION:
        return None  # nic nie potwierdzamy

    normalized = user_prompt.lower().strip()

    # POTWIERDZENIE
    if normalized in ["tak", "yes", "y", "lyra tak", "potwierdzam", "lyra potwierdzam"]:
        cmd = PENDING_CONFIRMATION
        PENDING_CONFIRMATION = None
        print(f"SYSTEM: {cmd}")
        return system_tool(cmd)

    # ANULOWANIE
    if normalized in ["nie", "no", "n", "lyra nie", "anuluj", "lyra anuluj"]:
        print("❎ Operacja anulowana.")
        PENDING_CONFIRMATION = None
        return ""

    # Inne odpowiedzi → dalej czekamy
    print("❗ Oczekuję na potwierdzenie (tak/nie).")
    return ""

    # ======= TU DOPIERO RESZTA KODU run_once =======
    # ===============================
    #  INTENT ROUTER — wykrywanie narzędzi
    # ===============================
   # intent, arg = detect_intent(user_prompt)
    
   # if intent:
    
    #    return tool_dispatch(intent, arg)
    # jeśli brak narzędzia → odpowiedź LLM
    #return answer_from_llm    
    """
    Obsługuje pojedyncze zapytanie użytkownika.

    Zasada działania (kolejność jest bardzo ważna):
    0) normalizacja wejścia
    1) wykrycie intencji lokalnej (bez LLM) -> tool_name/arg
    2) szybkie komendy i skróty (BRAIN_TEST, zmiana modelu, SYSTEM:, TOOL:)
    3) narzędzia wykryte lokalnie
    4) filtry bezpieczeństwa (krótkie i czytelne komunikaty)
    5) budowa kontekstu/pamięci
    6) wywołanie modelu (local/openai)
    7) fallback (mózg) jeśli LLM padnie lub zwróci pustkę
    """

    # ---------------------------------------------------------
    # 0) NORMALIZACJA WEJŚCIA
    # ---------------------------------------------------------
    prompt_lower = (user_prompt or "").lower().strip()

    # ---------------------------------------------------------
    # 1) INTENCJE LOKALNE – MUSZĄ BYĆ WCZEŚNIE (żeby nie było UnboundLocalError)
    # ---------------------------------------------------------
   # global PENDING_CONFIRMATION

# JEŚLI CZEKA NA POTWIERDZENIE
    #if PENDING_CONFIRMATION:
     #   if user_prompt.lower() in ("tak", "y", "yes"):
      #      cmd = PENDING_CONFIRMATION
      #      PENDING_CONFIRMATION = None
      #      print(f"SYSTEM: {cmd}")
      #      return
      #  elif user_prompt.lower() in ("nie", "n", "no"):
      #      print("❎ Anulowano wykonanie polecenia.")
      #      PENDING_CONFIRMATION = None
      #      return
      #  else:
      #      print("⚠️ Oczekuję odpowiedzi: tak / nie.")
      #      return
    # Dzięki temu tool_name istnieje ZAWSZE, zanim cokolwiek go użyje.
    # tool_name, arg = detect_intent_local(user_prompt) or (None, "")
    tool_name, arg = detect_intent_local(user_prompt)
    # ---------------------------------------------------------
    # 2) TEST MÓZGU: OBSŁUGA LOKALNA (BEZ LLM / BEZ OLLAMA)
    # ---------------------------------------------------------
    if tool_name:
        out = tool_dispatch(tool_name, arg or "")
        print(out)
        remember_entry(
            "TOOL",
            user=user_prompt,
            tool=tool_name,
            args=arg,
            output=str(out)[:4000]
        )
        return
    # To jest krytyczne: test połączenia nie może przepychać ogromnego promptu do LLM.
    if tool_name == "BRAIN_TEST":
        model = cfg.get("local_model", cfg.get("model", "nieznany"))
        msg = (
            f"Myślenie lokalne działa, Tomek.\n"
            f"Aktywny model: {model}.\n\n"
            "Mózg jest aktywny i reaguje lokalnie."
        )
        print(msg)
        remember(user_prompt, msg)
        return

    # ---------------------------------------------------------
    # 3) „PRZETESTUJ POŁĄCZENIE Z MÓZGIEM” – stary skrót zostaje (nie usuwam)
    # ---------------------------------------------------------
    # Pozostawiamy, bo Ty tego używasz, a to jest czytelne.
    # To NIE wywoła LLM, bo tool_dispatch(BRAIN_TEST) ma być lokalne.
    if "przetestuj połączenie z mózgiem" in prompt_lower:
        out = tool_dispatch("BRAIN_TEST", "")
        print(out)
        remember(user_prompt, out)
        return

    # --- NATYCHMIASTOWY TEST MÓZGU (BEZ MODELU) ---
    if any(k in prompt_lower for k in [
        "czy połączenie działa",
        "czy polaczenie dziala",
        "czy po laczenie dziala",
        "czy działa połączenie",
        "czy mózg działa",
        "przetestuj połączenie"
    ]):
        model = cfg.get("local_model", cfg.get("model", "nieznany"))
        msg = (
            "✅ POŁĄCZENIE DZIAŁA\n\n"
            f"Aktywny model lokalny: {model}\n"
            "Silnik lokalny odpowiada poprawnie.\n"
            "Nie używam modelu zewnętrznego."
        )
        print(msg)
        remember(user_prompt, msg)
        return



    # ---------------------------------------------------------
    # 4) WYBÓR MODELU LOKALNEGO / MAPOWANIE NA NAZWY „SILNIKA”
    # ---------------------------------------------------------
    # Ten blok zostaje, ale dodaję komentarze i minimalną ochronę.
    # Uwaga: To mapuje cfg["model"] na nazwy, których używa backend (np. ollama).
    local_model = (cfg.get("local_model") or "").lower()

    if local_model == "mistral":
        cfg["model"] = "mistral:latest"
    elif local_model == "bielik":
        cfg["model"] = "bielik-11b"
    elif local_model == "llama":
        cfg["model"] = "llama3.1:latest"
    elif local_model == "mixtral":
        cfg["model"] = "mixtral:8x7b"
    elif local_model == "gemma":
        # Obsługa modelu Gemma – użyj nazwy bazowej lub suffiksu latest
        cfg["model"] = "gemma:latest"
    elif local_model == "aya":
        # Dla modelu AYA użyj nazwy z konfiguracji lub domyślnej
        cfg["model"] = cfg.get("model", "aya-23-8B-f16")

    # ---------------------------------------------------------
    # 5) ZMIANA MODELU – masz DWIE ŚCIEŻKI, nie usuwam żadnej
    # ---------------------------------------------------------
    # (A) stara: „lyra zmień model na …”
    if prompt_lower.startswith("lyra zmień model na"):
        name = user_prompt.split("na", 1)[1].strip()
        cfg["local_model"] = name
        cfg["model"] = name
        cfg["backend"] = "local"
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f"✅ Zmieniono model lokalny na: {name}")
        print_lyra_banner(cfg)
        return

    # (B) nowsza: łapie też „zmień model …”
    # Zostaje, ale zmieniam sys.exit(0) -> return, żeby nie ubijać procesu w środku (bezpieczniej).
    if "zmień model" in prompt_lower:
        try:
            new_model = user_prompt.split()[-1].lower()
        except Exception:
            new_model = ""
        if new_model:
            # state = load_state()  # zostawiam (nie usuwam), ale nie musimy go tu używać
            state = load_state()
            cfg["local_model"] = new_model
            with open(BASE_DIR / "config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            print(f"✅ Zmieniono model na: {new_model}")
            # sys.exit(0)  # NIE USUWAM W SENSIE LOGICZNYM – tylko zastępuję bezpiecznym return
            return

    # ---------------------------------------------------------
    # 6) JAWNE POLECENIE SYSTEMOWE
    # ---------------------------------------------------------
    if user_prompt.lower().startswith("system:"):
        cmd = user_prompt.split(":", 1)[1].strip()
        out = system_tool(cmd)
        print(out)
        update_state({"last_system_cmd": cmd, "last_system_output": out[:4000]})
        remember_entry("SYSTEM", user=user_prompt, command=cmd, output=out[:4000])
        return

    # ---------------------------------------------------------
    # 7) JAWNE UŻYCIE NARZĘDZIA TOOL:
    # ---------------------------------------------------------
    if user_prompt.startswith("TOOL:"):
        rest = user_prompt.split(":", 1)[1].strip()
        _tool_name, _arg = (rest.split("|", 1) + [""])[:2]
        _tool_name, _arg = _tool_name.strip(), _arg.strip()
        out = tool_dispatch(_tool_name, _arg)
        print(out)
        remember_entry("TOOL", user=user_prompt, tool=_tool_name, args=_arg, output=str(out)[:4000])
        return

    # ---------------------------------------------------------
    # 8) SZYBKIE INFO O KERNELU
    # ---------------------------------------------------------
    if prompt_lower in ["sprawdź kernel", "jaki kernel", "kernel", "wersja kernela"]:
        out = system_tool("uname -r")
        print(out)
        remember_entry("SYSTEM", user=user_prompt, command="uname -r", output=out[:4000])
        return

    # ---------------------------------------------------------
    # 9) INTENCJE LOKALNE (sieć, pamięć, lista modeli, audio, cinnamon, logi itd.)
    # ---------------------------------------------------------
    # Uwaga: tool_name i arg już mamy z punktu (1). Nie wywołujemy detect_intent_local drugi raz,
    # ale NIC nie usuwam — zostawiam Twoją logikę, tylko porządkuję i stabilizuję.
    

    # ---------------------------------------------------------
    # 10) FILTR BEZPIECZEŃSTWA DLA NIEZNANYCH / ZBYT DŁUGICH PYTAŃ
    # ---------------------------------------------------------
    # Zostawiam Twoje komunikaty, ale porządkuję indentację i usuwam „martwe” returny.
    if len(user_prompt) > 120:
        print(
            "❗ Nie rozumiem polecenia (literówka lub zbyt ogólne pytanie).\n"
            "👉 Spróbuj krócej albo użyj jednego z poleceń:\n"
            "- przetestuj połączenie z mózgiem\n"
            "- zdiagnozuj dźwięk\n"
            "- sprawdź internet\n"
            "- sprawdź dyski\n"
            "- lista modeli\n"
            "- zmień model na <nazwa>\n"
        )
        return

    # ---------------------------------------------------------
    # 11) DODATKOWY TEST „CZY POŁĄCZENIE DZIAŁA?” – NIE MOŻE ZWRACAĆ RETURN KROTKI
    # ---------------------------------------------------------
    # U Ciebie było: return "BRAIN_TEST", ""  -> to NIE MA SENSU w run_once() i psuje logikę.
    # Nic nie usuwam, tylko naprawiam wykonanie: kieruję to na tool_dispatch.
    if any(k in prompt_lower for k in [
        "czy połączenie działa",
        "czy polaczenie dziala",
        "czy po laczenie dziala",
        "czy działa połączenie",
        "czy dziala",
        "czy mózg działa",
        "czy mozg dziala"
    ]):
        out = tool_dispatch("BRAIN_TEST", "")
        print(out)
        remember(user_prompt, out)
        return

    # ---------------------------------------------------------
    # 12) STATUS SYSTEMU (monitor/status)
    # ---------------------------------------------------------
    if "monitor" in prompt_lower or "status" in prompt_lower:
        s = get_status()
        report = analyze_status(s)
        print(report)
        remember(user_prompt, report)
        return

    # ---------------------------------------------------------
    # 13) SNAPSHOT STANU I AKTUALIZACJA
    # ---------------------------------------------------------
    update_state({
        "last_seen": datetime.now().isoformat(),
        "kernel": system_tool("uname -a", timeout=3)[:300],
        "session": system_tool("echo $XDG_SESSION_TYPE", timeout=3).strip(),
        "os": system_tool("cat /etc/os-release", timeout=3)[:500],
    })
    st = load_state()

    # ---------------------------------------------------------
    # 14) BANNER (informacyjny)
    # ---------------------------------------------------------
    print_lyra_banner(cfg)

    # ---------------------------------------------------------
    # 15) BUDOWA SYSTEM_MESSAGE Z KONTEKSTEM
    # ---------------------------------------------------------
    system_state_block = (
        f"last_seen: {st.get('last_seen','')}\n"
        f"kernel: {st.get('kernel','')}\n"
        f"os:\n{st.get('os','')}\n"
        f"last_tool: {st.get('last_tool','')} | {st.get('last_tool_arg','')}\n"
        f"last_tool_output:\n{st.get('last_tool_output','')}\n"
        f"last_system_cmd: {st.get('last_system_cmd','')}\n"
        f"last_system_output:\n{st.get('last_system_output','')}\n"
    )

    system_message = {
        "role": "system",
        "content": (
            "Jesteś techniczną asystentką Tomka w terminalu Linux. Masz na imię LYRA. "
            "Użytkownik ma na imię Tomek. Odpowiadaj po polsku, konkretnie.\n"
            "Tryb: agresywny (3) — działaj, nie filozofuj.\n\n"
            "Masz TRZY typy odpowiedzi:\n\n"
            "1) Zwykła odpowiedź tekstowa po polsku – wyjaśnienia, analizy, podsumowania.\n\n"
            "2) Odpowiedź narzędziowa:\n"
            "   - SYSTEM: <komenda bash>\n"
            "   - TOOL: <NAZWA_NARZĘDZIA> | <argument>\n\n"
            "3) PROPOSE_TOOL:\n"
            "   NAME:\n"
            "   DESCRIPTION:\n"
            "   CODE:\n\n"
            "ZASADY:\n"
            "- SYSTEM / TOOL → ZERO dodatkowego tekstu\n"
            "- ryzykowne akcje tylko jako PROPOSE_TOOL\n"
            "- *_FIX i AUTO_OPTIMIZE tylko jeśli są odwracalne\n\n"
            "- Nie zgaduj imion\n"
            "- Korzystaj z pamięci rozmowy\n"
            "- Nie zmieniaj swojej tożsamości\n\n"
            "ZASADA AUTOMATYCZNEJ DECYZJI:\n"
            "- Jesli polecenie dotyczy diagnozy, uzyj *_DIAG.\n"
            "- Jesli dotyczy naprawy, uzyj *_FIX.\n"
            "- Jesli dotyczy informacji, uzyj *_INFO.\n"
            "- Jesli dotyczy uruchomienia programu lub strony, uzyj: TOOL: APP_CONTROL | <opis>.\n"
            "- Jesli dotyczy pilnowania aplikacji, uzyj: TOOL: APP_GUARD | <opis>.\n"
            "- Jesli dotyczy plikow/katalogow/archiwow (find/cp/mv/grep/tar/unzip), uzyj: SYSTEM: <komenda>.\n"
            "- Jesli mozna wykonac od razu, NIE opisuj - zwroc tylko SYSTEM: albo TOOL:.\n"
            "- Jesli nie jest oczywiste, zapytaj krotko o doprecyzowanie.\n"
            "\n\n=== SYSTEM STATE (DO ZAPAMIĘTANIA) ===\n"
            f"session: {st.get('session','')}\n"
            f"kernel: {st.get('kernel','')}\n"
            f"os:\n{st.get('os','')}\n"
            f"last_tool: {st.get('last_tool','')} {st.get('last_tool_arg','')}\n"
            f"last_tool_output:\n{st.get('last_tool_output','')}\n"
            f"last_system_cmd: {st.get('last_system_cmd','')}\n"
            f"last_system_output:\n{st.get('last_system_output','')}\n"
            f"=== SYSTEM_STATE ===\n{system_state_block}\n=== END STATE ===\n"
        )
    }

    # ---------------------------------------------------------
    # 16) KONTEKST Z PAMIĘCI (ostatnie wpisy TEXT)
    # ---------------------------------------------------------
    mem = load_memory()[-6:]
    context_lines = []
    for m in mem:
        if m.get("type") == "TEXT":
            context_lines.append(f"User: {m.get('user','')}")
            context_lines.append(f"Lyra: {m.get('assistant','')}")
    context = "\n".join(context_lines)

    prompt = (
        f"Jesteś LYRA.\nRozmawiasz z Tomkiem.\nZnasz jego imię: Tomek.\n\n"
        f"KONTEKST ROZMOWY:\n{context}\n\n"
        f"AKTUALNE PYTANIE:\n{user_prompt}"
    )

    messages = [system_message, {"role": "user", "content": prompt}]

    # ---------------------------------------------------------
    # 17) WYBÓR BACKENDU I WYWOŁANIE MODELU
    # ---------------------------------------------------------
    backend = cfg.get("backend", "local")
    msg = ""
    mode = ""

    if backend == "local":
        try:
            ollama_model = cfg.get("ollama_model") or cfg.get("model") or "mistral"
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": ollama_model, "prompt": prompt},
                timeout=60,
                stream=True
            )
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    msg += chunk.get("response", "")
            mode = f"local:{ollama_model}"
        except Exception as e:
            msg = f"[Błąd lokalnego modelu] {e}"
            mode = "local:error"
    else:
        if not client:
            msg = "[Błąd] Brak api_key w config.json."
            mode = "openai:error"
        else:
            try:
                openai_model = pick_openai_model(cfg)
                msg, mode = query_model(
                    user_prompt,
                    openai_model,
                    openai_model,
                    client,
                    messages
                )
            except Exception as e:
                msg = f"[Błąd OpenAI] {e}"
                mode = "openai:error"

    msg = (msg or "").strip()

    # ---------------------------------------------------------
    # 18) FALLBACK DO „MÓZGU” GDY LLM PADŁ / TIMEOUT / BŁĄD
    # ---------------------------------------------------------
    if mode.endswith(":error") or msg.startswith("[Błąd lokalnego modelu]"):
        log("Local model error → fallback to brain", "agent.log")
        fallback = query_brain(polish_guard(prompt))


        # Jeśli model lokalny nie jest Mistral, zaktualizuj komunikat w fallbacku
        model_name = cfg.get("local_model", "Mistral")
        if model_name and model_name.lower() != "mistral" and "Mistral" in fallback:
            fallback = fallback.replace("Mistral", model_name)

        print(fallback)
        remember(user_prompt, fallback)
        return

    # ---------------------------------------------------------
    # 19) FALLBACK DO MÓZGU, GDY MODEL ZWRÓCIŁ PUSTKĘ
    # ---------------------------------------------------------
    if not msg:
        log("LLM EMPTY → fallback to brain", "agent.log")
        out = query_brain(prompt)
        print(out)
        remember(user_prompt, out)
        return

    # ---------------------------------------------------------
    # 20) OBSŁUGA ODPOWIEDZI: SYSTEM / TOOL / PROPOSE_TOOL / TEKST
    # ---------------------------------------------------------
    if msg.startswith("SYSTEM:"):
        cmd = msg[len("SYSTEM:"):].strip()
        out = system_tool(cmd)
        print(out)
        remember_entry("SYSTEM", user=user_prompt, command=cmd, output=str(out)[:4000])
        update_state({"last_system_cmd": cmd, "last_system_output": str(out)[:4000]})
        return

    if msg.startswith("TOOL:"):
        rest = msg[len("TOOL:"):].strip()
        _tool_name, _arg = (rest.split("|", 1) + [""])[:2]
        _tool_name, _arg = _tool_name.strip(), _arg.strip()
        out = tool_dispatch(_tool_name, _arg)
        print(out)
        remember_entry("TOOL", user=user_prompt, tool=_tool_name, args=_arg, output=str(out)[:4000])
        update_state({
            "last_tool": _tool_name,
            "last_tool_arg": _arg,
            "last_tool_output": str(out)[:4000]
        })
        return

    if msg.startswith("PROPOSE_TOOL:"):
        print(msg)
        remember_entry("PROPOSE_TOOL", user=user_prompt, proposal=msg[:4000])
        return

    # ---------------------------------------------------------
    # 21) NORMALNY TEKST
    # ---------------------------------------------------------
    print(msg)
    remember(user_prompt, msg)
    log(f"MODEL USED: {mode}", "agent.log")


# ======= PUNKT WEJŚCIA =======
if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_once(" ".join(sys.argv[1:]))
    else:
        print("Lyra online. 'exit' aby wyjść.")
        while True:
            try:
                user_input = input("Ty > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break
            run_once(user_input)

           
