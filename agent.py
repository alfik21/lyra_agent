#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import datetime
import shlex
import socket
from pathlib import Path
import subprocess
import getpass
import requests
import re
import shutil
import threading
import time
import contextlib
import io
import glob
from urllib.parse import quote_plus

# Ensure lyra_project is on sys.path so the jadro package can be imported.
CORE_DIR = Path(__file__).resolve().parent / "lyra_project"
if CORE_DIR.exists():
    sys.path.insert(0, str(CORE_DIR))

# Bezpieczny import openai
#try:
import openai
#except ImportError:
 #   print("❌ Błąd: Brak biblioteki 'openai'. Zainstaluj: pip install openai")
 #   openai = None

# ======= IMPORTY TWOICH MODUŁÓW =======
from modules.system import run as system_run
from modules.intent_router import detect_intent
from modules.model_router import query_model, get_last_stats
from modules.model_paths import load_models
from modules.mode_manager import load_state
from modules.memory_store import remember
from modules.status_monitor import tool_STATUS_MONITOR
from modules.memory_commands import handle_memory_command, record_context_line, build_memory_context
from modules.command_catalog import ensure_command, format_command_list
# ####--- RDZEŃ LYRY: INTEGRACJA DUSZY I PAMIĘCI ---####
# Łączymy system z plikami, które masz w folderze /jądro
try:
    from jądro.zarzadca_pamieci import pamiec as LyraMemory
    # Zarządcę duszy zaraz dopiszemy, jeśli go nie masz
    pass
except ImportError as e:
    pass
    LyraMemory = None

# Importujemy nasze moduły z katalogu /jądro/
try:
    from jądro.zarzadca_duszy import zarzadca as LyraSoul
    pass
except ImportError as e:
    pass
    LyraSoul = None


# Zarządzanie modelami
from modules.model_switcher import tool_MODEL_SWITCHER, get_active_local_model_name, tool_SCAN_MODELS
from modules.model_list import tool_MODEL_LIST
from modules.model_profiles import choose_best_model

# Narzędzia (Tools)
from modules.app_tools import tool_APP_CONTROL
from modules.app_guard import tool_APP_GUARD



from modules.audio_tools import tool_AUDIO_DIAG, tool_AUDIO_FIX
from modules.net_tools import tool_NET_INFO, tool_NET_DIAG, tool_NET_FIX
from modules.system_tools import tool_SYSTEM_DIAG, tool_SYSTEM_FIX, tool_AUTO_OPTIMIZE
from modules.disk_tools import tool_DISK_DIAG
from modules.log_analyzer import tool_LOG_ANALYZE
from modules.tmux_tools import tool_TMUX_SCREEN_DIAG
from modules.voice_input import tool_VOICE_INPUT
from modules.memory_ai import tool_MEMORY_ANALYZE
from modules.desktop_tools import tool_DESKTOP_DIAG, tool_DESKTOP_FIX
from modules.file_edit_tools import tool_FILE_EDIT
from modules.file_tools import tool_FILE_READ
from modules.web_tools import internet_search, fetch_url, build_adapter_block

# ======= KONFIGURACJA I STANY =======
BAZOWY_KATALOG = Path(__file__).resolve().parent
PLIK_USTAWIENIA = BAZOWY_KATALOG / "config.json"
CURRENT_MODE = "lyra"  # Domyślny tryb startowy: lyra, bash, code
LAST_INFERENCE = "local"  # local | online | none
LAST_MODEL_NAME = None
LAST_FILE_PATH = None
LAST_FILE_CONTENT = None
LAST_FILE_STATE = Path.home() / ".lyra_last_file.json"
LAST_STATS = None
FORCE_ONLINE = False
FORCE_LOCAL = False
FORCED_CLOUD_MODEL = None
BASELINE_GPU_USED = None
LYRA_CONTEXT_PATH = BAZOWY_KATALOG / "lyra_project" / "jądro" / "LyraKontekst.json"
COMMAND_LOG_PATH = BAZOWY_KATALOG / "logs" / "commands.log"
LLAMA_SERVER_BIN = Path.home() / "lyra_agent" / "llama.cpp" / "build" / "bin" / "llama-server"
LLAMA_DEFAULT_MODEL = "gemma-2-2b-it-q4_k_m"
LLAMA_LOG_PATH = BAZOWY_KATALOG / "logs" / "llama_server.log"
OLLAMA_LOG_PATH = BAZOWY_KATALOG / "logs" / "ollama.log"
STATUS_MONITOR_LOG = BAZOWY_KATALOG / "logs" / "status_monitor.log"
PAMIEC_BIEZCA_PATH = BAZOWY_KATALOG / "PamiecBiezaca.json"
CONTEXT_LOG_PATH = BAZOWY_KATALOG / "context_journal.log"
CONTEXT_INTERVAL = 15

CONTEXT_THREAD = None
CONTEXT_STOP_EVENT = None
LLAMA_DEFAULT_GPU_LAYERS = 99
LLAMA_DEFAULT_TENSOR_SPLIT = "8,4"
LLAMA_STATS_CACHE = BAZOWY_KATALOG / "logs" / "llama_stats.json"

def _load_llama_stats_cache():
    try:
        if not LLAMA_STATS_CACHE.exists():
            return None
        raw = LLAMA_STATS_CACHE.read_text(encoding="utf-8")
        if not raw.strip():
            return None
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None

def _save_llama_stats_cache(stats):
    try:
        if not stats or not isinstance(stats, dict):
            return
        LLAMA_STATS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        LLAMA_STATS_CACHE.write_text(
            json.dumps(stats, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

def _merge_llama_log_stats(stats: dict | None) -> dict | None:
    if not stats:
        stats = {}
    log_stats = _parse_llama_log_stats()
    if not log_stats:
        return _clamp_gen_tps(stats)
    merged = dict(stats)
    merged["backend"] = "llama"
    for field in ("prompt_tps", "gen_tps"):
        value = log_stats.get(field)
        if value is not None:
            merged[field] = value
    return _clamp_gen_tps(merged)

def _clamp_gen_tps(stats: dict | None) -> dict | None:
    if not stats:
        return stats
    prompt_tps = stats.get("prompt_tps") or 0.0
    gen_tps = stats.get("gen_tps")
    if gen_tps is None:
        return stats
    limit = max(5000.0, prompt_tps * 100)
    if prompt_tps > 0 and gen_tps > limit:
        stats["gen_tps"] = prompt_tps
    elif gen_tps > limit:
        stats["gen_tps"] = prompt_tps or limit
    return stats

def _cache_stats(stats: dict | None):
    if stats and isinstance(stats, dict):
        _save_llama_stats_cache(stats)

LAST_STATS = _load_llama_stats_cache() or LAST_STATS

SYSTEM_TOOLS = {
    "DISK_DIAG": tool_DISK_DIAG,
    "NET_INFO": tool_NET_INFO,
    "NET_DIAG": tool_NET_DIAG,
    "NET_FIX": tool_NET_FIX,
    "AUDIO_DIAG": tool_AUDIO_DIAG,
    "AUDIO_FIX": tool_AUDIO_FIX,
    "SYSTEM_DIAG": tool_SYSTEM_DIAG,
    "SYSTEM_FIX": tool_SYSTEM_FIX,
    "AUTO_OPTIMIZE": tool_AUTO_OPTIMIZE,
    "APP_CONTROL": tool_APP_CONTROL,
    "APP_GUARD": tool_APP_GUARD,
    "LOG_ANALYZE": tool_LOG_ANALYZE,
    "TMUX_DIAG": tool_TMUX_SCREEN_DIAG,
    "VOICE_INPUT": tool_VOICE_INPUT,
    "MEMORY_ANALYZE": tool_MEMORY_ANALYZE,
    "DESKTOP_DIAG": tool_DESKTOP_DIAG,
    "DESKTOP_FIX": tool_DESKTOP_FIX,
    "FILE_READ": tool_FILE_READ,
    "FILE_EDIT": tool_FILE_EDIT,
    "STATUS": tool_STATUS_MONITOR,
    "INTERNET_SEARCH": internet_search,
    "FETCH_URL": fetch_url
}

COMMAND_DESCRIPTIONS = {
    "FILE_READ": "Odczytaj zawartość wskazanego pliku.",
    "FILE_READ_SUMMARY": "Przeczytaj i podsumuj plik.",
    "FILE_READ_SUMMARY_SHORT": "Podsumuj plik krótko.",
    "FILE_READ_SUMMARY_LONG": "Podsumuj plik szczegółowo.",
    "LAST_FILE_SUMMARY": "Opisz ostatnio otwarty plik.",
    "FILE_EDIT": "Zmień, dodaj lub zahaszuj linie w pliku.",
    "DISK_DIAG": "Sprawdź dyski i partycje.",
    "NET_INFO": "Pokaż informacje o połączeniu sieciowym.",
    "NET_DIAG": "Skanuj sieć w celu diagnozy.",
    "NET_FIX": "Napraw połączenie sieciowe.",
    "AUDIO_DIAG": "Przeprowadź diagnostykę audio.",
    "AUDIO_FIX": "Napraw dźwięk lub mikrofon.",
    "SYSTEM_DIAG": "Przeprowadź diagnozę systemu.",
    "SYSTEM_FIX": "Napraw problemy systemowe.",
    "AUTO_OPTIMIZE": "Przeprowadź automatyczną optymalizację.",
    "APP_GUARD": "Pilnuj procesu lub aplikacji.",
    "APP_CONTROL": "Uruchom/zatrzymaj aplikację.",
    "LOG_ANALYZE": "Przeanalizuj logi systemowe.",
    "DESKTOP_DIAG": "Zdiagnozuj problem pulpitu/Cinnamon.",
    "COMMAND_LIST": "Pokaż listę komend Lyry.",
    "INTERNET_SEARCH": "Wykonaj wyszukiwanie w sieci.",
}

def register_known_commands():
    for key, desc in COMMAND_DESCRIPTIONS.items():
        ensure_command(key, desc)

register_known_commands()

# ======= FUNKCJE POMOCNICZE =======

def log_event(msg, filename="agent.log"):
    log_path = BAZOWY_KATALOG / "logs" / filename
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} | {msg}\n")

def log_function(msg, file="models.log"):
    log_event(f"[MODELS] {msg}", file)

def log_command(cmd):
    COMMAND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COMMAND_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(cmd.strip() + "\n")

def _tail_file(path: Path, size: int = 2048) -> str:
    if not path.exists():
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            start = max(0, file_size - size)
            f.seek(start)
            chunk = f.read()
        return chunk.decode("utf-8", errors="ignore").strip()
    except OSError:
        return ""

def _last_non_empty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""

def _build_context_snapshot():
    active_model = LAST_MODEL_NAME or get_active_local_model_name() or ""
    command_tail = _tail_file(COMMAND_LOG_PATH, size=4096)
    status_tail = _tail_file(STATUS_MONITOR_LOG, size=2048)
    memory_tail = _tail_file(PAMIEC_BIEZCA_PATH, size=2048)
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "mode": CURRENT_MODE,
        "active_model": active_model,
        "last_command": _last_non_empty_line(command_tail),
        "status_tail": status_tail.splitlines()[-2:],
        "memory_tail": memory_tail.splitlines()[-2:],
    }
    return entry

def _write_context_snapshot():
    CONTEXT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = _build_context_snapshot()
    with open(CONTEXT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _context_worker(stop_event: threading.Event):
    while not stop_event.is_set():
        _write_context_snapshot()
        stop_event.wait(CONTEXT_INTERVAL)

def ensure_context_logger():
    global CONTEXT_THREAD, CONTEXT_STOP_EVENT
    if CONTEXT_THREAD and CONTEXT_THREAD.is_alive():
        return
    CONTEXT_STOP_EVENT = threading.Event()
    CONTEXT_THREAD = threading.Thread(target=_context_worker, args=(CONTEXT_STOP_EVENT,), daemon=True)
    CONTEXT_THREAD.start()

def stop_context_logger():
    if CONTEXT_STOP_EVENT:
        CONTEXT_STOP_EVENT.set()

def _start_ollama():
    try:
        OLLAMA_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OLLAMA_LOG_PATH, "ab") as out:
            subprocess.Popen(
                ["/usr/local/bin/ollama", "serve"],
                stdout=out,
                stderr=out,
                preexec_fn=os.setsid,
            )
        return True, "Ollama uruchomiona."
    except Exception as e:
        return False, f"Ollama start error: {e}"

def _stop_ollama():
    try:
        subprocess.run(["pkill", "-f", "ollama serve"], check=False)
        subprocess.run(["pkill", "-f", "ollama runner"], check=False)
        subprocess.run(["pkill", "-f", "/usr/local/bin/ollama"], check=False)
        return True, "Ollama zatrzymana."
    except Exception as e:
        return False, f"Ollama stop error: {e}"

def _resolve_model_path(model_name):
    data = load_models()
    available = data.get("available", {})
    if model_name in available:
        return available[model_name]
    # Try case-insensitive match
    for name, path in available.items():
        if name.lower() == str(model_name).lower():
            return path
    return None

def _start_llama_server(model_name=None):
    try:
        if get_config_field("llama_run_as_root", False):
            try:
                subprocess.run(["sudo", "systemctl", "start", "lyra-llama.service"], check=False)
                time.sleep(1)
                if _port_open("127.0.0.1", 11435):
                    return True, "Llama-server uruchomiony jako root (systemd)."
            except Exception:
                pass
        if _port_open("127.0.0.1", 11435):
            # If llama-server already runs, accept it as OK.
            try:
                r = requests.post(
                    "http://127.0.0.1:11435/v1/chat/completions",
                    json={"model": "", "messages": [{"role": "user", "content": "ping"}]},
                    timeout=2,
                )
                if r.status_code in [200, 400]:
                    # If ollama responds, do not treat it as llama-server.
                    try:
                        o = requests.get("http://127.0.0.1:11435/api/tags", timeout=2)
                        if o.status_code == 200:
                            return False, "Port 11435 zajety przez Ollama."
                    except Exception:
                        pass
                    return True, "Llama-server juz dziala."
            except Exception:
                pass
            return False, "Port 11435 zajety (zatrzymaj Ollama lub inny serwer)."
        model_name = model_name or get_config_field("llama_model", LLAMA_DEFAULT_MODEL)
        gpu_layers = int(get_config_field("llama_gpu_layers", LLAMA_DEFAULT_GPU_LAYERS))
        tensor_split = str(get_config_field("llama_tensor_split", LLAMA_DEFAULT_TENSOR_SPLIT))
        model_path = _resolve_model_path(model_name)
        if not model_path:
            return False, f"Brak modelu w liscie: {model_name}"
        model_path = Path(model_path)
        if not model_path.exists():
            return False, f"Brak pliku modelu: {model_path}"
        if not LLAMA_SERVER_BIN.exists():
            return False, f"Brak binarki llama-server: {LLAMA_SERVER_BIN}"
        LLAMA_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LLAMA_LOG_PATH, "ab") as out:
            subprocess.Popen(
                [
                    str(LLAMA_SERVER_BIN),
                    "-m",
                    str(model_path),
                    "--port",
                    "11435",
                    "--gpu-layers",
                    str(gpu_layers),
                    "--tensor-split",
                    tensor_split,
                ],
                stdout=out,
                stderr=out,
                preexec_fn=os.setsid,
            )
        for _ in range(15):
            if _port_open("127.0.0.1", 11435):
                return True, f"Llama-server uruchomiony: {model_name}"
            time.sleep(1)
        return False, "Llama-server nie wystartowal (sprawdz logs/llama_server.log)."
    except Exception as e:
        return False, f"Llama start error: {e}"

def _stop_llama_server():
    try:
        subprocess.run(["pkill", "-f", "llama-server"], check=False)
        return True, "Llama-server zatrzymany."
    except Exception as e:
        return False, f"Llama stop error: {e}"

def load_lyra_context():
    if not LYRA_CONTEXT_PATH.exists():
        return []
    try:
        return json.loads(LYRA_CONTEXT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_lyra_context(entries):
    LYRA_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LYRA_CONTEXT_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def append_lyra_context(user_text, assistant_text, limit=50):
    entries = load_lyra_context()
    entries.append({
        "time": datetime.datetime.now().isoformat(),
        "user": user_text,
        "assistant": assistant_text
    })
    save_lyra_context(entries[-limit:])

def query_gpt_online(prompt, model_alias="gpt-5.1"):
    if not openai:
        return "❌ Biblioteka 'openai' nie zainstalowana.", "error"
    try:
        with open(PLIK_USTAWIENIA, "r") as f:
            config = json.load(f)
            api_key = config.get("openai_api_key")
        if not api_key or "TWÓJ_KLUCZ" in api_key:
            return "❌ Błąd: Brak klucza API.", "error"
        model_name = model_alias or config.get("default_cloud_model") or "gpt-5.1"
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Jesteś Lyra, zaawansowany asystent AI."},
                {"role": "user", "content": prompt},
            ],
            timeout=15,
        )
        return response.choices[0].message.content, "online"
    except Exception as e:
        return f"❌ Błąd API: {str(e)}", "error"

def update_config_field(key, value):
    cfg = {}
    try:
        if PLIK_USTAWIENIA.exists():
            backup_dir = BAZOWY_KATALOG / "logs" / "config_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"config_{stamp}.json"
            shutil.copy2(PLIK_USTAWIENIA, backup_path)
        cfg = json.loads(PLIK_USTAWIENIA.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    cfg[key] = value
    PLIK_USTAWIENIA.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8"
    )

def get_config_field(key, default=None):
    try:
        cfg = json.loads(PLIK_USTAWIENIA.read_text(encoding="utf-8"))
        return cfg.get(key, default)
    except Exception:
        return default

def _get_exec_level():
    try:
        level = int(get_config_field("exec_level", 1))
    except Exception:
        level = 1
    return max(1, min(3, level))

def _set_exec_level(level: int):
    level = max(1, min(3, int(level)))
    update_config_field("exec_level", level)
    return f"✅ Ustawiono poziom wykonania: {level}"

def _get_web_adapter():
    val = str(get_config_field("web_adapter", "off") or "off").lower()
    return val in ["on", "true", "1", "yes", "tak", "wlacz", "włącz"]

def _set_web_adapter(enabled: bool):
    update_config_field("web_adapter", "on" if enabled else "off")
    return f"✅ Adapter WWW: {'ON' if enabled else 'OFF'}"

def _show_banner():
    try:
        active_model = get_active_local_model_name() or "Lokalny"
    except Exception:
        active_model = "Lokalny"
    model_for_banner = LAST_MODEL_NAME or active_model
    wyswietl_baner(CURRENT_MODE, model_for_banner)

def _get_cloud_consent():
    try:
        return (get_config_field("cloud_consent", "ask") or "ask").lower()
    except Exception:
        return "ask"

def _get_dry_run():
    try:
        return bool(get_config_field("dry_run", False))
    except Exception:
        return False

def _get_test_only():
    try:
        return bool(get_config_field("test_only", False))
    except Exception:
        return False

def _get_rollback_enabled():
    try:
        return bool(get_config_field("rollback_enabled", True))
    except Exception:
        return True

def _get_rollback_paths():
    paths = get_config_field("rollback_paths", None)
    if isinstance(paths, list) and paths:
        return [Path(os.path.expanduser(p)).resolve() for p in paths]
    defaults = [
        "/etc/hosts",
        "/etc/resolv.conf",
        "/etc/fstab",
        "/etc/sysctl.conf",
        "~/.config/pulse",
        "~/.config/pipewire",
    ]
    return [Path(os.path.expanduser(p)).resolve() for p in defaults]

def _create_system_rollback(tool_name: str):
    try:
        rb_dir = BAZOWY_KATALOG / "logs" / "system_rollbacks"
        rb_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        snap_dir = rb_dir / stamp
        snap_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for path in _get_rollback_paths():
            if not path.exists():
                continue
            files.append(str(path))
            if path.is_dir():
                dest = snap_dir / path.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(path, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(path, snap_dir / path.name)
        manifest = {
            "tool": tool_name,
            "timestamp": stamp,
            "files": files,
        }
        (snap_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        (rb_dir / "last.txt").write_text(stamp + "\n", encoding="utf-8")
        return stamp
    except Exception:
        return None

def _list_system_rollbacks():
    rb_dir = BAZOWY_KATALOG / "logs" / "system_rollbacks"
    if not rb_dir.exists():
        return []
    stamps = []
    for entry in sorted(rb_dir.iterdir(), reverse=True):
        if entry.is_dir():
            stamps.append(entry.name)
    return stamps

def _restore_system_rollback(stamp: str | None):
    rb_dir = BAZOWY_KATALOG / "logs" / "system_rollbacks"
    if not stamp:
        last_file = rb_dir / "last.txt"
        if last_file.exists():
            stamp = last_file.read_text(encoding="utf-8").strip()
    if not stamp:
        return "Brak rollbackow."
    snap_dir = rb_dir / stamp
    if not snap_dir.exists():
        return "Rollback nie istnieje."
    manifest_path = snap_dir / "manifest.json"
    if not manifest_path.exists():
        return "Brak manifestu rollbacku."
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest.get("files", [])
    except Exception:
        files = []
    for src in snap_dir.iterdir():
        if src.name == "manifest.json":
            continue
        dest = None
        for orig in files:
            if Path(orig).name == src.name:
                dest = Path(orig)
                break
        if not dest:
            continue
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    return f"Przywrocono rollback: {stamp}"

def _tool_failed(output: str) -> bool:
    if not output:
        return False
    low = output.lower()
    triggers = ["błąd", "blad", "error", "failed", "exception", "traceback"]
    return any(t in low for t in triggers)

def _is_low_quality_response(text: str) -> bool:
    if not text:
        return True
    low = text.lower()
    boilerplate = [
        "z przyjemnością pomogę",
        "uwagi:",
        "pamiętaj o zachowaniu szacunku",
        "w odpowiedzi na pytania",
        "system nie potrafi znaleźć",
        "błąd api",
        "blad api",
        "connection error",
    ]
    if any(b in low for b in boilerplate):
        return True
    return False

def _lyra_capabilities_summary():
    return (
        "Potrafię diagnozować system (dyski, sieć, audio, desktop), zarządzać modelami "
        "lokalnymi oraz uruchamiać testy i stres VRAM.\n"
        "Umiem czytać i edytować pliki (początek/koniec/linia), zapisywać pamięć w JSON "
        "i robić backupy oraz rollback konfiguracji."
    )

def _summarize_text(text: str, query: str, bullets: str = "5-7"):
    prompt = (
        f"Streszcz zawartosc po polsku w {bullets} krotkich punktach. "
        "Zachowaj najwazniejsze fakty. Nie zmyslaj.\n\n"
        f"Kontekst: {query}\n\nTresc:\n{text[:8000]}"
    )
    try:
        response, _ = query_model(prompt, get_active_local_model_name(), "local", config={"timeout":60}, history=[])
        out = (response or "").strip()
        if "Błąd połączenia" in out or "llama-server" in out or "ERROR" in out:
            return ""
        return out
    except Exception:
        return ""

def _chunk_text(text: str, max_chars: int = 4000, overlap: int = 200):
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks

def _summarize_text_sentences(text: str, query: str, sentences: int):
    prompt = (
        f"Streszcz zawartosc po polsku w {sentences} zdaniach. "
        "Zachowaj najwazniejsze fakty. Nie zmyslaj.\n\n"
        f"Kontekst: {query}\n\nTresc:\n{text[:8000]}"
    )
    try:
        response, _ = query_model(prompt, get_active_local_model_name(), "local", config={"timeout":60}, history=[])
        out = (response or "").strip()
        if "Błąd połączenia" in out or "llama-server" in out or "ERROR" in out:
            return ""
        return out
    except Exception:
        return ""

def _summarize_large_text(text: str, query: str, bullets: str = "5-7", sentences: int | None = None):
    chunks = _chunk_text(text, max_chars=4000, overlap=200)
    mini_summaries = []
    for i, chunk in enumerate(chunks, start=1):
        prompt_context = f"{query} (fragment {i}/{len(chunks)})"
        part = _summarize_text(chunk, prompt_context, bullets="2-3")
        if not part or _is_low_quality_response(part):
            part = _basic_summary(chunk, max_items=3)
        mini_summaries.append(part.strip())
    combined = "\n".join([s for s in mini_summaries if s])
    if sentences and sentences > 0:
        final = _summarize_text_sentences(combined, "Scal streszczenia fragmentow", sentences)
    else:
        final = _summarize_text(combined, "Scal streszczenia fragmentow", bullets=bullets)
    if not final or _is_low_quality_response(final):
        final = _basic_summary(text, max_items=5)
    return final

def _extract_headings(text: str, max_items: int = 5):
    headings = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            h = s.lstrip("#").strip()
            if h:
                headings.append(h)
                if len(headings) >= max_items:
                    break
    return headings

def _summary_matches_content(summary: str, content: str) -> bool:
    heads = _extract_headings(content)
    if not heads:
        return True
    low = summary.lower()
    hits = 0
    for h in heads:
        key = h.lower()
        if key in low:
            hits += 1
            continue
        first = key.split()[0] if key.split() else ""
        if first and first in low:
            hits += 1
    return hits > 0

def _basic_summary(text: str, max_items: int = 5):
    try:
        data = json.loads(text)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            count = len(data)
            first = data[0].get("data")
            last = data[-1].get("data")
            lines = [f"- Liczba wpisow: {count}"]
            if first:
                lines.append(f"- Pierwszy wpis: {first}")
            if last:
                lines.append(f"- Ostatni wpis: {last}")
            return "\n".join(lines)
    except Exception:
        pass
    headings = _extract_headings(text, max_items=max_items)
    bullets = []
    if headings:
        bullets.append("- Sekcje: " + ", ".join(headings))
    examples = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("-", "*")) or re.match(r"^\d+[.)]\s+", s):
            examples.append(s.lstrip("-* ").strip())
            if len(examples) >= 3:
                break
    if examples:
        bullets.append("- Przyklady: " + "; ".join(examples))
    if bullets:
        return "\n".join(bullets)
    return "Brak lokalnego streszczenia. Uzyj GPT do podsumowania."

def _is_state_change_cmd(cmd_lower: str) -> bool:
    if cmd_lower.startswith(("lyra zmien silnik", "zmien silnik")):
        return True
    if cmd_lower.startswith(("lyra ustaw model", "ustaw model")):
        return True
    if cmd_lower.startswith(("lyra uzyj ", "lyra użyj ", "uzyj ", "użyj ")):
        return True
    if cmd_lower.startswith(("zgoda gpt", "lyra zgoda gpt")):
        return True
    if cmd_lower in ["lyra start llama", "lyra stop llama", "lyra status llama", "start llama", "stop llama", "llama start", "llama stop", "llama status"]:
        return True
    if cmd_lower.startswith(("rollback apply", "lyra rollback apply")):
        return True
    return False

def _prompt_open_shell(path: Path):
    try:
        choice = input(f"Przejsc do katalogu {path} w nowym shellu? (tak/nie): ").strip().lower()
    except Exception:
        choice = ""
    if choice in ["tak", "t", "yes", "y", "ok"]:
        shell = os.environ.get("SHELL", "/bin/bash")
        subprocess.run([shell], cwd=str(path))
        return True
    return False

def _save_system_snapshot(tool_name: str):
    try:
        snap_dir = BAZOWY_KATALOG / "logs" / "system_snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = snap_dir / f"{tool_name.lower()}_{stamp}.log"
        cmds = [
            "date",
            "uname -a",
            "uptime",
            "ip -brief a 2>/dev/null",
            "ip r 2>/dev/null",
            "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT 2>/dev/null",
            "systemctl --failed --no-pager 2>/dev/null",
        ]
        lines = []
        for cmd in cmds:
            lines.append(f"$ {cmd}\n")
            lines.append(system_run(cmd, timeout=8) or "")
            lines.append("\n")
        out_path.write_text("".join(lines), encoding="utf-8")
    except Exception:
        pass

def _save_last_file_path(path: str):
    try:
        data = {"path": path, "ts": datetime.datetime.now().isoformat()}
        LAST_FILE_STATE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def _load_last_file_path():
    try:
        if not LAST_FILE_STATE.exists():
            return None
        data = json.loads(LAST_FILE_STATE.read_text(encoding="utf-8"))
        return data.get("path")
    except Exception:
        return None

def _list_file_backups(path: Path):
    backup_dir = BAZOWY_KATALOG / "logs" / "file_backups"
    if not backup_dir.exists():
        return []
    pattern = f"{path.name}."
    files = sorted([p for p in backup_dir.glob(f"{path.name}.*.bak")], reverse=True)
    return [p for p in files if p.name.startswith(pattern)]

def _restore_file_backup(path: Path, selector: str | None):
    backups = _list_file_backups(path)
    if not backups:
        return "Brak backupow dla pliku."
    if not selector:
        lines = ["Dostepne backupy:"]
        for i, b in enumerate(backups, start=1):
            lines.append(f"{i}) {b.name}")
        return "\n".join(lines)
    if selector.isdigit():
        idx = int(selector)
        if idx < 1 or idx > len(backups):
            return "Poza zakresem indexu backupu."
        src = backups[idx - 1]
    else:
        src = next((b for b in backups if b.name == selector), None)
        if not src:
            return "Nie znaleziono backupu o tej nazwie."
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, path)
    return f"Przywrocono plik z backupu: {src.name}"

def _extract_where_file(cmd: str):
    import re
    m = re.search(r"(?:gdzie (?:sie )?znajduje|gdzie jest) plik\s+(.+)$", cmd, flags=re.IGNORECASE)
    if not m:
        return None
    name = m.group(1).strip().strip('"').strip("'")
    return name or None

def _where_file_cmd(name: str):
    import shlex
    if not name:
        return None
    base = f"find ~ /etc /usr/share -maxdepth 4 -type f -iname {shlex.quote('*' + name + '*')} 2>/dev/null | head -n 20"
    if shutil.which("timeout"):
        return f"timeout 10s {base}"
    return base

def _llama_service_cmd(action: str):
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, "lyra-llama.service"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return f"✅ llama-service: {action} OK"
        err = (result.stderr or result.stdout or "").strip()
        return f"❌ llama-service: {action} failed: {err}"
    except Exception as e:
        return f"❌ llama-service error: {e}"
def _local_unknown(text: str) -> bool:
    if not text:
        return True
    low = text.lower()
    triggers = [
        "nie wiem",
        "brak odpowiedzi",
        "brak danych",
        "nie mam danych",
        "nie jestem pewien",
        "nie jestem pewna",
        "nie posiadam informacji",
        "nie mam informacji",
        "offline + lokalny model nie działa",
        "błąd modelu",
    ]
    return any(t in low for t in triggers)

def _set_cloud_consent(choice: str):
    value = choice.lower().strip()
    if value.endswith(" raz"):
        value = value[:-4].strip()
        if value:
            return "✅ Zgoda GPT: jednorazowo"
    if value in ["zawsze", "always", "stala", "stała", "stale", "stałe", "full", "ciagla", "ciągła", "ciagle", "ciągłe"]:
        update_config_field("cloud_consent", "always")
        return "✅ Zgoda GPT ustawiona: zawsze"
    if value in ["nie", "never"]:
        update_config_field("cloud_consent", "never")
        return "✅ Zgoda GPT ustawiona: nigdy"
    if value in ["raz", "once", "ok", "tak", "dobrze", "zgoda", "zgoda na raz", "jednorazowo", "tylko raz"]:
        return "✅ Zgoda GPT: jednorazowo"
    return "⚠️ Uzycie: zgoda gpt zawsze|raz|nie"

def get_detailed_gpu_info():
    gpu_stats = []
    try:
        for card, used, total in _read_gpu_stats():
            gpu_stats.append(f"GPU{card[-1]}: {used}/{total}MB")
        return " | ".join(gpu_stats) if gpu_stats else "GPU: Idle"
    except: return "GPU: Nie wykryto"

def _read_gpu_stats():
    stats = []
    try:
        cards = [d for d in os.listdir('/sys/class/drm/') if d.startswith('card') and len(d) == 5]
        for card in sorted(cards):
            base_path = f"/sys/class/drm/{card}/device"
            t_p, u_p = f"{base_path}/mem_info_vram_total", f"{base_path}/mem_info_vram_used"
            if os.path.exists(t_p):
                with open(t_p, 'r') as f: total = int(f.read().strip()) // (1024**2)
                with open(u_p, 'r') as f: used = int(f.read().strip()) // (1024**2)
                stats.append((card, used, total))
    except Exception:
        pass
    return stats

def get_gpu_summary():
    try:
        used_total = 0
        total_total = 0
        active = 0
        stats = _read_gpu_stats()
        for card, used, total in stats:
            total_total += total
            used_total += used
            if used > 0:
                active += 1
        return {"total": total_total, "used": used_total, "active": active, "count": len(stats), "stats": stats}
    except Exception:
        return {"total": 0, "used": 0, "active": 0, "count": 0, "stats": []}

def _gpu_perf_summary():
    summary = get_gpu_summary()
    used = summary["used"]
    total = summary["total"] or 1
    percent = (used / total) * 100
    active = summary["active"]
    count = summary["count"] or 1
    return percent, used, total, active, count

def internet_ok(timeout=2):
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(("8.8.8.8", 53))
            return True
        finally:
            sock.close()
    except Exception:
        return False

def _fmt_tps(value):
    if value is None:
        return "0,0"
    return f"{value:.1f}".replace(".", ",")

def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)

def _pad_banner_line(text: str, width: int) -> str:
    visible = len(_strip_ansi(text))
    if visible >= width:
        return text[:width]
    return text + (" " * (width - visible))

def _normalize_output(text: str) -> str:
    if not text:
        return ""
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    out = out.replace("WATCHDOG | auto", "")
    out = out.strip()
    # Collapse excessive blank lines.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out

def _parse_llama_log_stats():
    try:
        if not LLAMA_LOG_PATH.exists():
            return None
        text = LLAMA_LOG_PATH.read_text(encoding="utf-8", errors="ignore")
        # Take last timing block
        prompt_matches = re.findall(r"prompt eval time .*?([0-9.]+) tokens per second", text)
        eval_matches = re.findall(r"eval time .*?([0-9.]+) tokens per second", text)
        if not prompt_matches or not eval_matches:
            return None
        prompt_tps = float(prompt_matches[-1])
        gen_tps = float(eval_matches[-1])
        return {"prompt_tps": prompt_tps, "gen_tps": gen_tps, "backend": "llama"}
    except Exception:
        return None

def _port_open(host, port, timeout=1):
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
            return True
        finally:
            sock.close()
    except Exception:
        return False

def _ping_llama_server(timeout=10):
    try:
        payload = {
            "prompt": "Lyra status check",
            "n_predict": 1,
            "temperature": 0.5,
            "timings": True,
        }
        r = requests.post(
            "http://127.0.0.1:11435/completion",
            json=payload,
            timeout=timeout,
        )
        if r.status_code == 200:
            data = {}
            try:
                timings = r.json().get("timings") or {}
                prompt_tps = timings.get("prompt_per_second")
                gen_tps = timings.get("predicted_per_second")
                data = {
                    "prompt_tps": prompt_tps,
                    "gen_tps": gen_tps,
                    "backend": "llama",
                }
            except Exception:
                data = {}
            data = _merge_llama_log_stats(data)
            _cache_stats(data)
            return True, None, data
        return False, f"status {r.status_code}", {}
    except Exception as e:
        return False, str(e), {}

def _self_diagnostics():
    global LAST_STATS
    lines = []
    # config.json
    try:
        json.loads(PLIK_USTAWIENIA.read_text(encoding="utf-8"))
        lines.append("Config: OK")
    except Exception as e:
        lines.append(f"Config: ERROR ({e})")

    backend = get_config_field("local_backend", "ollama")
    lines.append(f"Backend: {backend}")

    if backend == "ollama":
        try:
            r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
            if r.status_code == 200:
                data = r.json()
                models = [m.get("name") for m in data.get("models", [])]
                active = get_active_local_model_name() or ""
                if active and active not in models:
                    lines.append(f"Ollama: OK (model missing: {active})")
                else:
                    lines.append("Ollama: OK")
            else:
                lines.append(f"Ollama: ERROR (status {r.status_code})")
        except Exception as e:
            lines.append(f"Ollama: ERROR ({e})")
    else:
        if _port_open("127.0.0.1", 11435):
            ok, error, stats = _ping_llama_server()
            if ok:
                lines.append("llama-server: OK")
                if stats:
                    LAST_STATS = stats
            else:
                msg = str(error or "").lower()
                if "timed out" in msg:
                    lines.append("llama-server: OK (ping timeout)")
                else:
                    lines.append(f"llama-server: ERROR ({error})")
        else:
            lines.append("llama-server: ERROR (port 11435)")

    lines.append(f"Inference: {LAST_INFERENCE}")
    if LAST_MODEL_NAME:
        lines.append(f"Model: {LAST_MODEL_NAME}")

    return "\n".join(lines)

def _web_search(query, max_results=3):
    if not query:
        return "ERROR: brak zapytania"
    if not internet_ok():
        return "ERROR: offline"
    try:
        def _ddg_api_search(qs: str):
            try:
                url = "https://api.duckduckgo.com/"
                params = {"q": qs, "format": "json", "no_redirect": 1, "no_html": 1}
                r = requests.get(url, params=params, timeout=8)
                if r.status_code != 200:
                    return None
                data = r.json()
                results = []
                for item in data.get("Results", []):
                    text = item.get("Text")
                    u = item.get("FirstURL")
                    if text and u:
                        results.append((text, u))
                        if len(results) >= max_results:
                            return results
                def _walk_related(items):
                    for it in items or []:
                        if "Topics" in it:
                            for sub in _walk_related(it.get("Topics", [])):
                                yield sub
                        else:
                            text = it.get("Text")
                            u = it.get("FirstURL")
                            if text and u:
                                yield (text, u)
                for text, u in _walk_related(data.get("RelatedTopics", [])):
                    results.append((text, u))
                    if len(results) >= max_results:
                        break
                return results or None
            except Exception:
                return None

        def _fetch_via_jina(url: str):
            try:
                if url.startswith("https://"):
                    target = url[len("https://"):]
                elif url.startswith("http://"):
                    target = url[len("http://"):]
                else:
                    target = url
                j_url = f"https://r.jina.ai/http://{target}"
                headers = {"User-Agent": "Mozilla/5.0"}
                return requests.get(j_url, headers=headers, timeout=10)
            except Exception:
                return None

        def _brave_search(qs: str):
            b_url = f"https://search.brave.com/search?q={qs}"
            headers = {"User-Agent": "Mozilla/5.0"}
            b_resp = requests.get(b_url, headers=headers, timeout=8)
            if not b_resp or b_resp.status_code != 200:
                b_resp = _fetch_via_jina(b_url)
                if not b_resp or b_resp.status_code != 200:
                    return None
            html = b_resp.text
            matches = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]+)</a>', html)
            results = []
            for href, title in matches:
                if "brave.com" in href:
                    continue
                results.append((title.strip(), href.strip()))
                if len(results) >= max_results:
                    break
            return results or None

        q = quote_plus(query)
        url = f"https://duckduckgo.com/html/?q={q}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp and resp.status_code in [202, 403]:
            resp = _fetch_via_jina(url)
            if not resp:
                brave = _brave_search(q)
                if brave:
                    return brave
        if resp and resp.status_code == 200:
            html = resp.text
            matches = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html)
            results = []
            for href, title in matches:
                title = re.sub(r"<.*?>", "", title)
                results.append((title.strip(), href.strip()))
                if len(results) >= max_results:
                    break
            if results:
                return results
        # Fallback: lite version
        url = f"https://lite.duckduckgo.com/lite/?q={q}"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp and resp.status_code in [202, 403]:
            resp = _fetch_via_jina(url)
            if not resp:
                brave = _brave_search(q)
                if brave:
                    return brave
        if resp and resp.status_code == 200:
            html = resp.text
            matches = re.findall(r'<a rel="nofollow" class="result-link" href="([^"]+)".*?>(.*?)</a>', html)
            results = []
            for href, title in matches:
                title = re.sub(r"<.*?>", "", title)
                results.append((title.strip(), href.strip()))
                if len(results) >= max_results:
                    break
            if results:
                return results
        # Fallback: POST to html endpoint
        url = "https://duckduckgo.com/html/"
        resp = requests.post(url, headers=headers, data={"q": query}, timeout=8)
        if resp and resp.status_code in [202, 403]:
            resp = _fetch_via_jina(f"{url}?q={q}")
            if not resp:
                brave = _brave_search(q)
                if brave:
                    return brave
        if not resp or resp.status_code != 200:
            # Last resort: GitHub releases for Nobara if query mentions it
            if "nobara" in query.lower():
                gh_results = _github_nobara_latest()
                if gh_results:
                    return gh_results[:max_results]
            ddg_api = _ddg_api_search(query)
            if ddg_api:
                return ddg_api
            # Fallback: Brave search HTML
            brave = _brave_search(q)
            if brave:
                return brave
            return f"ERROR: status {getattr(resp, 'status_code', 'no_response')}"
        html = resp.text
        matches = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html)
        results = []
        for href, title in matches:
            title = re.sub(r"<.*?>", "", title)
            results.append((title.strip(), href.strip()))
            if len(results) >= max_results:
                break
        if not results:
            # Last resort: GitHub releases for Nobara if query mentions it
            if "nobara" in query.lower():
                gh_results = _github_nobara_latest()
                if gh_results:
                    return gh_results[:max_results]
            ddg_api = _ddg_api_search(query)
            if ddg_api:
                return ddg_api
            # Fallback: Wikipedia OpenSearch
            try:
                api = "https://pl.wikipedia.org/w/api.php"
                params = {"action": "opensearch", "search": query, "limit": max_results, "namespace": 0, "format": "json"}
                r = requests.get(api, params=params, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    titles = data[1] if len(data) > 1 else []
                    links = data[3] if len(data) > 3 else []
                    wiki_results = []
                    for t, u in zip(titles, links):
                        wiki_results.append((t, u))
                    if wiki_results:
                        return wiki_results
            except Exception:
                pass
            brave = _brave_search(q)
            if brave:
                return brave
            return "ERROR: no results"
        return results
    except Exception as e:
        ddg_api = None
        try:
            ddg_api = _ddg_api_search(query)
        except Exception:
            ddg_api = None
        if ddg_api:
            return ddg_api
        return f"ERROR: {e}"

def _fetch_url_text(url: str, max_chars: int = 8000):
    try:
        if url.startswith("https://"):
            target = url[len("https://"):]
        elif url.startswith("http://"):
            target = url[len("http://"):]
        else:
            target = url
        j_url = f"https://r.jina.ai/http://{target}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(j_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return ""
        text = resp.text
        return text[:max_chars]
    except Exception:
        return ""

def _github_nobara_latest():
    repos = [
        "Nobara-Project/Nobara-Project",
        "Nobara-Project/nobara-releases",
        "Nobara-Project/nobara",
    ]
    out = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for repo in repos:
        try:
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                name = data.get("name") or data.get("tag_name") or repo
                html = data.get("html_url") or f"https://github.com/{repo}/releases"
                out.append((f"{repo}: {name}", html))
        except Exception:
            continue
    return out

def _get_commands_list():
    return [
        ":bash | :lyra | :code | :screen | :state | :backend | exit",
        "lyra lista modeli",
        "lyra uzyj <model> | lyra uzyj gpt | lyra uzyj lokalnego modelu",
        "lyra zmien silnik na ollama|llama",
        "lyra ustaw model <nazwa>",
        "lyra pokaz model",
        "lyra test vram",
        "lyra stress <sekundy>",
        "lyra konsola",
        "lyra status",
        "lyra poziom [1|2|3]",
        "lyra adapter www on|off|status",
        "lyra sprawdz w internecie <zapytanie>",
        "lyra komendy",
        "lyra lista komend pelna|niepelna|10|liczba",
        "lyra dry-run on|off|status",
        "lyra cofnij plik <sciezka> [index|nazwa]",
        "lyra przywroc plik <sciezka> <index|nazwa>",
        "lyra test-only on|off|status",
        "lyra rollback on|off|status",
        "lyra rollback list",
        "lyra rollback apply <stamp|last>",
        "lyra ls [sciezka]",
        "lyra cd <sciezka>",
        "lyra pwd",
        "aliasy: ls <sciezka>, cd <sciezka>, pwd",
        "lyra przetestuj sie",
        "lyra przetestuj model",
        "lyra sprawdz modele",
        "lyra skanuj modele | lyra skanuj modele szybko | lyra skanuj modele bez ollama",
        "lyra test odpowiedzi",
        "lyra wyswietl katalog | lyra pokaz katalog",
        "lyra przeczytaj <plik> | lyra podsumuj <plik> | lyra stresc <plik>",
        "lyra przeczytaj <plik> i podsumuj [krotko|dlugo]",
    ]

def _format_commands_help():
    lines = ["Komendy (statyczne):"] + _get_commands_list()
    return "\n".join(lines)

def _run_vram_test():
    script = BAZOWY_KATALOG / "scripts" / "llama_vram_test.sh"
    if not script.exists():
        print(f"❌ Brak skryptu: {script}")
        return
    res = subprocess.run([str(script)], capture_output=True, text=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr:
        print(res.stderr.strip())

def _get_cpu_temp():
    try:
        import psutil
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for key in ["coretemp", "k10temp", "cpu_thermal"]:
            if key in temps and temps[key]:
                cur = temps[key][0].current
                if cur is not None:
                    return f"{cur:.1f}°C"
        for entries in temps.values():
            if entries:
                cur = entries[0].current
                if cur is not None:
                    return f"{cur:.1f}°C"
    except Exception:
        pass
    try:
        out = system_run("sensors 2>/dev/null | rg -m1 \"Package id 0|Tctl|Tdie|CPU\"")
        if out and not out.startswith("["):
            m = re.search(r"([-+]?\\d+\\.\\d+)°C", out)
            if m:
                return f"{m.group(1)}°C"
    except Exception:
        pass
    return None

def _get_gpu_temps():
    temps = []
    for card_path in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        card = Path(card_path).name
        inputs = sorted(glob.glob(f"{card_path}/device/hwmon/hwmon*/temp*_input"))
        if not inputs:
            continue
        try:
            raw = Path(inputs[0]).read_text().strip()
            val = float(raw) / 1000.0
            temps.append(f"{card.upper()} {val:.1f}°C")
        except Exception:
            continue
    return temps

def _get_temp_summary():
    cpu = _get_cpu_temp()
    gpu_temps = _get_gpu_temps()
    parts = []
    if cpu:
        parts.append(f"CPU {cpu}")
    parts.extend(gpu_temps)
    return " | ".join(parts)

def _run_stress(seconds, intensity=1):
    orig_stdout = sys.stdout

    intensity = max(1, int(intensity))

    def _monitor(stop_event):
        start = time.time()
        while not stop_event.is_set():
            elapsed_raw = int(time.time() - start)
            total = max(1, seconds)
            elapsed = min(elapsed_raw, total)
            prog = elapsed
            remaining = max(0, total - elapsed)
            bar_len = 30
            filled = int((prog / total) * bar_len)
            bar = "#" * filled + "-" * (bar_len - filled)
            progress_pct = int((prog / total) * 100)
            gpu_sum = get_gpu_summary()
            percent = int((gpu_sum["used"] / gpu_sum["total"]) * 100) if gpu_sum["total"] else 0
            if percent < 20:
                level = "LOW"
            elif percent < 50:
                level = "MED"
            elif percent < 80:
                level = "HIGH"
            else:
                level = "MAX"
            print("\033[2J\033[H", end="", file=orig_stdout, flush=True)  # clear screen + home
            try:
                active_model = get_active_local_model_name() or "Lokalny"
            except Exception:
                active_model = "Lokalny"
            model_for_banner = LAST_MODEL_NAME or active_model
            wyswietl_baner(CURRENT_MODE, model_for_banner, out=orig_stdout, leading_newline=False, show_stats=True)
            temp_summary = _get_temp_summary()
            if temp_summary:
                print(f"TEMP: {temp_summary}", file=orig_stdout)
            print(f"STRESS: {elapsed}s/{total}s | REM: {remaining}s | LOAD: {level} ({percent}%) | INT: x{intensity}", file=orig_stdout)
            print(f"[{bar}] {progress_pct}%\n", file=orig_stdout, flush=True)
            if elapsed_raw >= total:
                stop_event.set()
                break
            time.sleep(1)

    def _worker(stop_event):
        prompt = (
            "Generuj ciagly tekst bez przerw i bez podsumowan. "
            "Nie odpowiadaj na pytania, tylko pisz dluga, spójna tresc. "
            f"Cel: obciaz GPU przez {seconds} sekund."
        )
        while not stop_event.is_set():
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                query_model(
                    prompt,
                    get_active_local_model_name(),
                    "local",
                    config={"timeout": 5},
                    history=[],
                )
            # Sync perf stats from model_router so banner can show P/G.
            try:
                global LAST_STATS
                LAST_STATS = get_last_stats()
                _cache_stats(LAST_STATS)
            except Exception:
                pass

    stop_event = threading.Event()
    t = threading.Thread(target=_monitor, args=(stop_event,), daemon=True)
    t.start()
    try:
        workers = []
        for _ in range(intensity):
            th = threading.Thread(target=_worker, args=(stop_event,), daemon=True)
            th.start()
            workers.append(th)
        start = time.time()
        while time.time() - start < seconds:
            time.sleep(0.2)
    except Exception as e:
        print(f"❌ Stress error: {e}")
    finally:
        stop_event.set()
        for th in workers:
            th.join(timeout=1)
        t.join(timeout=2)

def _parse_stress_args(cmd_clean):
    parts = cmd_clean.split()
    lower = [p.lower() for p in parts]
    try:
        idx = lower.index("stress")
    except ValueError:
        return None, None
    args = parts[idx + 1 :]
    seconds = 10
    intensity = 1
    if len(args) >= 1:
        try:
            seconds = int(args[0])
        except ValueError:
            return None, None
    if len(args) >= 2:
        try:
            intensity = int(args[1])
        except ValueError:
            intensity = 1
    return seconds, intensity

def _format_commands_history(limit=20, top=10):
    if not COMMAND_LOG_PATH.exists():
        return "Historia komend: brak danych"
    try:
        with open(COMMAND_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip()]
        if not lines:
            return "Historia komend: brak danych"
        last = lines[-limit:]
        counts = {}
        for ln in lines:
            counts[ln] = counts.get(ln, 0) + 1
        top_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:top]
        out = ["Historia komend (ostatnie):"]
        out.extend(last)
        out.append("")
        out.append("Najczestsze:")
        out.extend([f"{cmd} ({cnt})" for cmd, cnt in top_items])
        return "\n".join(out)
    except Exception:
        return "Historia komend: blad odczytu"

def wyswietl_baner(tryb, model, out=None, leading_newline=True, show_stats=True):
    out = out or sys.stdout
    gpu_data = get_detailed_gpu_info()
    backend = get_config_field("local_backend", "ollama")
    gpu_summary = get_gpu_summary()
    compute = "CPU"
    if LAST_INFERENCE == "online":
        compute = "cloud"
    else:
        # Use absolute VRAM usage to decide GPU activity.
        active_cards = 0
        for card, used, _ in gpu_summary["stats"]:
            if used >= 512:
                active_cards += 1
        if gpu_summary["used"] >= 1024 and active_cards > 0:
            compute = f"GPU({active_cards}/{gpu_summary['count']})"
    vram_line = f"VRAM: {gpu_summary['used']}/{gpu_summary['total']}MB"
    net_status = "online" if internet_ok() else "offline"
    engine = "openai" if LAST_INFERENCE == "online" else backend
    czas = datetime.datetime.now().strftime("%H:%M:%S")
    RESET = "\033[0m"
    rainbow = [
        "\033[91m",  # light red
        "\033[93m",  # light yellow
        "\033[92m",  # light green
        "\033[96m",  # light cyan
        "\033[94m",  # light blue
        "\033[95m",  # light magenta
    ]
    term_cols = shutil.get_terminal_size(fallback=(100, 20)).columns
    width = max(60, min(78, term_cols - 4))
    header = _pad_banner_line(f"Lyra {tryb.upper()} | Model: {model} | {czas}", width)
    prefix = "\n" if leading_newline else ""
    print(f"{prefix}{rainbow[0]}╔" + "═"*width + f"╗{RESET}", file=out)
    print(f"{rainbow[1]}║ {header} ║{RESET}", file=out)
    print(f"{rainbow[2]}╟" + "─"*width + f"╢{RESET}", file=out)
    stats = LAST_STATS or get_last_stats() or {}
    if not stats and backend == "llama":
        stats = _parse_llama_log_stats() or {}
    has_perf = bool(stats.get("prompt_tps") or stats.get("gen_tps"))
    p_tps = _fmt_tps(stats.get("prompt_tps"))
    g_tps = _fmt_tps(stats.get("gen_tps"))
    if show_stats:
        zasoby = _pad_banner_line(f"Zasoby: {gpu_data}", width)
        print(f"{rainbow[3]}║ {zasoby} ║{RESET}", file=out)
        eng_color = "\033[94m"
        net_color = "\033[92m"
        vram_color = "\033[93m"
        comp_color = "\033[96m"
        eng_line = (
            f"{eng_color}Eng: {engine}{rainbow[4]} | "
            f"{net_color}Net: {'on' if net_status == 'online' else 'off'}{rainbow[4]} | "
            f"{comp_color}Comp: {compute}{rainbow[4]} | "
            f"{vram_color}{vram_line}{rainbow[4]}"
        )
        eng_line = _pad_banner_line(eng_line, width)
        print(f"{rainbow[4]}║ {eng_line} ║{RESET}", file=out)
        if has_perf:
            perf_text = f"Perf: P {p_tps} t/s | G {g_tps} t/s"
        else:
            gpu_pct, gpu_used, gpu_total, gpu_active, gpu_count = _gpu_perf_summary()
            perf_text = f"Perf: GPU {gpu_pct:.1f}% | VRAM {gpu_used}/{gpu_total}MB ({gpu_active}/{gpu_count})"
        perf = _pad_banner_line(perf_text, width)
        print(f"{rainbow[5]}║ {perf} ║{RESET}", file=out)
    print(f"{rainbow[0]}╚" + "═"*width + f"╝{RESET}", file=out)

# ======= GŁÓWNA LOGIKA WYKONAWCZA =======

def run_once(user_input):
    global CURRENT_MODE, LAST_INFERENCE, LAST_MODEL_NAME, LAST_STATS, FORCE_ONLINE, FORCE_LOCAL, FORCED_CLOUD_MODEL
    global LAST_FILE_PATH, LAST_FILE_CONTENT
    if not user_input.strip(): return
    cmd_clean = user_input.strip()
    cmd_clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", cmd_clean).strip()
    cmd_clean = re.sub(r"\bsprawdzsterowniki\b", "sprawdz sterowniki", cmd_clean, flags=re.IGNORECASE)
    cmd_clean = re.sub(r"\bsprawdzgdziejestes\b", "sprawdz gdzie jestes", cmd_clean, flags=re.IGNORECASE)
    # toleruj literówki w wywołaniu "lyra"
    typo_prefixes = ["lyr", "lura", "lyar", "lrya", "lyra", "lyta", "lyea"]
    for tp in typo_prefixes:
        if cmd_clean.lower().startswith(tp + " "):
            cmd_clean = "lyra " + cmd_clean[len(tp) + 1:].lstrip()
            break
    if re.search(r"^(lyra\s+)?(ktora|która|ktorej|której|ktore|które)\s+godzina\??$", cmd_clean, flags=re.IGNORECASE) or re.search(r"^(lyra\s+)?(ktora|która|ktorej|której|ktore|które)\s+jest\s+godzina\??$", cmd_clean, flags=re.IGNORECASE):
        _show_banner()
        print(system_run("date"))
        return
    m_level = re.search(r"^(lyra\s+)?poziom\s*(\d)?$", cmd_clean, flags=re.IGNORECASE)
    if m_level:
        _show_banner()
        level = m_level.group(2)
        if not level:
            print(f"Poziom wykonania: {_get_exec_level()}")
            return
        print(_set_exec_level(int(level)))
        return
    m_adapter = re.search(r"^(lyra\s+)?adapter\s+www\s*(on|off|status)?$", cmd_clean, flags=re.IGNORECASE)
    if m_adapter:
        _show_banner()
        mode = (m_adapter.group(2) or "status").lower()
        if mode == "status":
            print(f"Adapter WWW: {'ON' if _get_web_adapter() else 'OFF'}")
            return
        print(_set_web_adapter(mode == "on"))
        return
    cmd_lower = cmd_clean.lower()
    cmd_norm = cmd_lower.rstrip(" ?!.")
    log_command(cmd_clean)
    record_context_line(cmd_clean)

    intent_pre = detect_intent(cmd_clean)
    if intent_pre:
        pre_tool = intent_pre[0] if isinstance(intent_pre, (tuple, list)) else intent_pre.get("tool")
        pre_arg = intent_pre[1] if isinstance(intent_pre, (tuple, list)) else intent_pre.get("arg", "")
        safe_tools = {
            "SYSTEM_DIAG",
            "NET_INFO",
            "NET_DIAG",
            "DISK_DIAG",
            "AUDIO_DIAG",
            "TMUX_DIAG",
            "LOG_ANALYZE",
            "STATUS",
        }
        if CURRENT_MODE != "lyra" and pre_tool in safe_tools and pre_tool in SYSTEM_TOOLS:
            print(f"⚙️ Narzędzie: {pre_tool}...")
            output = SYSTEM_TOOLS[pre_tool](pre_arg, system_run, log_event)
            print(output)
            return
    if cmd_clean.lower() in ["gdzie jestem", "gdzie jestes", "sprawdz gdzie jestem", "sprawdz gdzie jestes"]:
        print(system_run("pwd"))
        return

    cmd_for_parse = cmd_clean[5:].strip() if cmd_lower.startswith("lyra ") else cmd_clean
    cmd_parse_lower = cmd_for_parse.lower()
    cmd_parse_lower = cmd_for_parse.lower()

    if cmd_parse_lower.startswith((
        "wejdz do katalogu ",
        "wejdź do katalogu ",
        "przejdz do katalogu ",
        "przejdź do katalogu ",
    )):
        target = cmd_for_parse.split(" ", 3)[-1].strip().strip('"').strip("'")
        if not target:
            print("⚠️ Uzycie: lyra wejdz do katalogu <sciezka>")
            return
        raw = os.path.expanduser(target)
        path = Path(raw).resolve() if raw.startswith(("/", "~")) else Path(os.getcwd(), raw).resolve()
        if not path.exists():
            home_guess = Path.home() / target
            if home_guess.exists():
                path = home_guess.resolve()
            else:
                matches = []
                try:
                    cmd = f"find {shlex.quote(str(Path.home()))} -maxdepth 4 -type d -iname {shlex.quote(target)} 2>/dev/null | head -n 10"
                    out = system_run(cmd, timeout=10)
                    if out:
                        matches = [ln.strip() for ln in out.splitlines() if ln.strip()]
                except Exception:
                    matches = []
                if matches:
                    print("Znalezione katalogi:")
                    for i, m in enumerate(matches, start=1):
                        print(f"{i}) {m}")
                    print("Uzyj: lyra wejdz do katalogu <pelna_sciezka>")
                    return
        if not _prompt_open_shell(path):
            print(f"Uzyj: cd {path}")
        return

    if (
        cmd_parse_lower in [
            "wyswietl katalog",
            "wyświetl katalog",
            "pokaz katalog",
            "pokaż katalog",
            "pokaz zawartosc",
            "pokaż zawartość",
            "wylistuj",
            "pokaz",
        ]
        or ("katalog" in cmd_parse_lower and any(x in cmd_parse_lower for x in ["pokaz", "pokaż", "wyswietl", "wyświetl", "zawartosc", "zawartość", "wylistuj"]))
    ):
        path = Path(os.getcwd())
        print(system_run(f"ls -la {shlex.quote(str(path))}", timeout=10))
        return
    file_name = _extract_where_file(cmd_for_parse)
    if file_name:
        if file_name in ["group", "passwd", "hosts", "fstab", "shadow", "gshadow"]:
            print(f"/etc/{file_name}")
            return
        cmd = _where_file_cmd(file_name)
        if cmd:
            out = system_run(cmd, timeout=10)
            print(out)
            return

    mem_msg = handle_memory_command(cmd_clean)
    if mem_msg:
        print(mem_msg)
        return

    if any(x in cmd_norm for x in ["czy masz internet", "masz internet", "masz dostep do internetu", "masz dostęp do internetu"]):
        if internet_ok():
            print("Tak, polaczenie sieciowe jest aktywne. Dostep do internetu w rozmowie zalezy od zgody GPT.")
        else:
            print("Nie, brak aktywnego polaczenia sieciowego.")
        return

    if (not (intent_pre and (intent_pre[0] if isinstance(intent_pre, (tuple, list)) else intent_pre.get("tool")) == "INTERNET_SEARCH")) \
        and "najnowszy" in cmd_norm and ("samsung" in cmd_norm or "iphone" in cmd_norm) \
        and "sprawdz w internecie" not in cmd_norm and "sprawdź w internecie" not in cmd_norm \
        and "zobacz w internecie" not in cmd_norm and "wyszukaj w internecie" not in cmd_norm \
        and "znajdz w internecie" not in cmd_norm and "poszukaj w internecie" not in cmd_norm \
        and "szukaj w internecie" not in cmd_norm:
        print("Nie mam pewnych danych offline. Uzyj: lyra sprawdz w internecie <zapytanie> (wymaga zgody GPT).")
        return

    if cmd_lower in ["test-only on", "test only on", "lyra test-only on", "lyra test only on"]:
        update_config_field("test_only", True)
        update_config_field("dry_run", True)
        print("✅ Test-only: ON (dry-run ON)")
        return
    if cmd_lower in ["test-only off", "test only off", "lyra test-only off", "lyra test only off"]:
        update_config_field("test_only", False)
        update_config_field("dry_run", False)
        print("✅ Test-only: OFF (dry-run OFF)")
        return
    if cmd_lower in ["test-only status", "test only status", "lyra test-only status", "lyra test only status"]:
        print(f"Test-only: {'ON' if _get_test_only() else 'OFF'}")
        return

    if _get_test_only() and _is_state_change_cmd(cmd_lower):
        print("🧪 Test-only: zablokowano zmiany stanu.")
        return

    if cmd_lower in [
        "lyra przetestuj sie",
        "lyra przetestuj się",
        "przetestuj sie",
        "przetestuj się",
        "test lyry",
        "testuj lyre",
        "testuj lyrę",
    ]:
        script = BAZOWY_KATALOG / "scripts" / "test_runner.sh"
        if not script.exists():
            print(f"❌ Brak skryptu: {script}")
            return
        res = subprocess.run([str(script)], capture_output=True, text=True)
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        if out:
            print(out)
        if err:
            print(err)
        return

    if cmd_lower in ["rollback on", "lyra rollback on"]:
        update_config_field("rollback_enabled", True)
        print("✅ Rollback: ON")
        return
    if cmd_lower in ["rollback off", "lyra rollback off"]:
        update_config_field("rollback_enabled", False)
        print("✅ Rollback: OFF")
        return
    if cmd_lower in ["rollback status", "lyra rollback status"]:
        print(f"Rollback: {'ON' if _get_rollback_enabled() else 'OFF'}")
        return
    if cmd_lower in ["rollback list", "lyra rollback list"]:
        items = _list_system_rollbacks()
        if not items:
            print("Brak rollbackow.")
            return
        print("Rollbacki:")
        for i, stamp in enumerate(items, start=1):
            print(f"{i}) {stamp}")
        return
    if cmd_lower.startswith("rollback apply ") or cmd_lower.startswith("lyra rollback apply "):
        stamp = cmd_clean.split()[-1].strip()
        if stamp.lower() == "last":
            stamp = None
        if stamp.isdigit():
            items = _list_system_rollbacks()
            idx = int(stamp)
            stamp = items[idx - 1] if 0 < idx <= len(items) else stamp
        print(_restore_system_rollback(stamp))
        return

    if cmd_norm.startswith("podaj wniosek"):
        print("Podaj z czego ma byc wniosek (np. plik lub temat).")
        return

    if "co potrafisz" in cmd_norm or cmd_norm.startswith("opisz co potrafisz"):
        print(_lyra_capabilities_summary())
        return

    if cmd_norm.startswith(("naucz sie ", "naucz się ", "lyra naucz sie ", "lyra naucz się ")):
        print("Uzyj: zapamietaj / niezapomnij / zapisz. Komenda 'naucz sie' nie jest obslugiwana.")
        return

    if cmd_lower in ["sprawdz modele", "sprawdź modele", "lyra sprawdz modele", "lyra sprawdź modele"]:
        print(tool_MODEL_LIST("", system_run, log_event))
        return

    if cmd_norm in ["przetestuj model", "testuj model", "test model", "lyra przetestuj model", "lyra testuj model"]:
        active_name = get_active_local_model_name() or ""
        prompt = (
            "Podaj odpowiedz w 15 liniach, dokladnie w formacie:\n"
            f"MODEL_IMIE: {active_name}\n"
            "MODEL_TWORCA: <tworca lub 'brak danych'>\n"
            "MODEL_POTRAFI: <krotko: 1 zdanie>\n"
            "LINUX_1: <zdanie>\n"
            "LINUX_2: <zdanie>\n"
            "LINUX_3: <zdanie>\n"
            "LINUX_4: <zdanie>\n"
            "LINUX_5: <zdanie>\n"
            "LINUX_6: <zdanie>\n"
            "LINUX_7: <zdanie>\n"
            "LINUX_8: <zdanie>\n"
            "LINUX_9: <zdanie>\n"
            "LINUX_10: <zdanie>\n"
            "LYRA_1: <zdanie>\n"
            "LYRA_2: <zdanie>\n"
            "Nie zmyslaj faktow. Nie dodawaj innych linii. "
            "MODEL_IMIE musi byc dokladnie jak powyzej. "
            "MODEL_TWORCA nie moze byc 'brak danych'. "
            "LINUX_* musza byc pelnymi zdaniami o systemie Linux i zawierac slowo 'Linux'. "
            "LYRA_* to 2 zdania o Lyra."
        )
        try:
            response, _ = query_model(prompt, get_active_local_model_name(), "local", config={"timeout":20}, history=[])
            if response:
                if "Błąd połączenia z llama-server" in response or "llama-server" in response:
                    print("❌ Llama-server nieosiagalny. Uruchom: lyra zmien silnik na llama  start llama.")
                    return
                text = response.strip()
                required = ["MODEL_IMIE:", "MODEL_TWORCA:", "MODEL_POTRAFI:"]
                missing = [k for k in required if k not in text]
                linux_lines = [f"LINUX_{i}:" for i in range(1, 11)]
                linux_missing = [k for k in linux_lines if k not in text]
                bad_markers = [
                    "jan kowalski",
                    "john doe",
                    "przyklad",
                    "przykład",
                    "nie mam wiedzy",
                ]
                low = text.lower()
                linux_bad = [ln for ln in low.splitlines() if ln.strip().startswith("linux_") and ("nie mam wiedzy" in ln or "linux" not in ln)]
                name_line = next((ln for ln in text.splitlines() if ln.strip().startswith("MODEL_IMIE:")), "")
                name_ok = active_name and name_line.strip().lower() == f"model_imie: {active_name}".lower()
                creator_line = next((ln for ln in low.splitlines() if ln.strip().startswith("model_tworca:")), "")
                creator_ok = creator_line and "brak danych" not in creator_line
                lyra_lines = [ln for ln in text.splitlines() if ln.strip().startswith("LYRA_")]
                lyra_ok = len(lyra_lines) == 2
                if missing or linux_missing or any(m in low for m in bad_markers) or linux_bad or not name_ok or not creator_ok or not lyra_ok:
                    print("❌ Test modelu nieudany (zla odpowiedz lub format).")
                    if missing or linux_missing:
                        print(f"Brak: {', '.join(missing + linux_missing)}")
                    if any(m in low for m in bad_markers) or linux_bad:
                        print("Powod: model powtarza przyklad lub unika odpowiedzi.")
                    if not name_ok:
                        print("Powod: MODEL_IMIE nie zgadza sie z aktywnym modelem.")
                    if not creator_ok:
                        print("Powod: MODEL_TWORCA nie moze byc 'brak danych'.")
                    if not lyra_ok:
                        print("Powod: musza byc dokladnie 2 linie LYRA_*.")
                    print(f"Odpowiedź: {text}")
                    return
                print(text)
                return
        except Exception as e:
            msg = str(e)
            if "Failed to establish a new connection" in msg or "Operation not permitted" in msg:
                print("❌ Llama-server nieosiagalny. Uruchom: lyra zmien silnik na llama lub lyra start llama.")
            else:
                print(f"❌ Test modelu nie powiodl sie: {e}")
            return

    if cmd_norm in [
        "jaki jest nowy model",
        "jaki jest aktywny model",
        "jaki model jest aktywny",
        "jaki model teraz",
        "jaki model teraz uzywasz",
        "jaki model teraz używasz",
        "jaki model",
        "jaki model jest",
        "jaki model uzywasz",
        "jaki model używasz",
        "pokaż aktywny model",
        "pokaz aktywny model",
        "pokaz model aktywny",
        "pokaż model aktywny",
        "lyra jaki jest nowy model",
        "lyra jaki model",
        "lyra pokaż aktywny model",
        "lyra pokaz aktywny model",
    ]:
        active = get_active_local_model_name()
        if active and active != "brak":
            print(f"Aktualny model: {active}")
        else:
            model_name = get_config_field("llama_model", LLAMA_DEFAULT_MODEL)
        print(f"Aktualny model: {model_name}")
        return

    if cmd_norm in ["test odpowiedzi", "lyra test odpowiedzi", "testuj odpowiedzi"]:
        prompt = "Napisz 3 zdania po polsku o Linuxie."
        response, _ = query_model(prompt, get_active_local_model_name(), "local", config={"timeout":20}, history=[])
        text = (response or "").strip()
        count = sum(1 for s in text.split(".") if s.strip())
        if count >= 3 and "linux" in text.lower():
            print("PASS: odpowiedz OK")
        else:
            print("FAIL: odpowiedz slaba")
            print(text)
        return

    if cmd_parse_lower.startswith((
        "wybiez ktore modele",
        "wybiez które modele",
        "wybierz ktore modele",
        "wybierz które modele",
        "wybierz niepotrzebne modele",
        "wybiez niepotrzebne modele",
    )):
        print(tool_MODEL_LIST("", system_run, log_event))
        print("Podaj kryterium: np. 'zostaw tylko PL', 'limit VRAM 8GB', 'usun duplikaty Q4/Q5'.")
        return

    if cmd_lower in ["skanuj modele", "lyra skanuj modele", "skan modeli", "skanuj model"]:
        print(tool_SCAN_MODELS("", system_run, log_event))
        return
    if cmd_lower in ["skanuj modele bez ollama", "lyra skanuj modele bez ollama"]:
        print(tool_SCAN_MODELS("bez ollama", system_run, log_event))
        return
    if cmd_lower in ["skanuj modele szybko", "lyra skanuj modele szybko", "skanuj modele fast", "lyra skanuj modele fast"]:
        print(tool_SCAN_MODELS("szybko", system_run, log_event))
        return

    if cmd_lower in ["dry-run on", "dry run on", "lyra dry-run on", "lyra dry run on"]:
        update_config_field("dry_run", True)
        print("✅ Dry-run: ON")
        return
    if cmd_lower in ["dry-run off", "dry run off", "lyra dry-run off", "lyra dry run off"]:
        update_config_field("dry_run", False)
        print("✅ Dry-run: OFF")
        return
    if cmd_lower in ["dry-run status", "dry run status", "lyra dry-run status", "lyra dry run status"]:
        print(f"Dry-run: {'ON' if _get_dry_run() else 'OFF'}")
        return

    if cmd_lower in ["pwd", "lyra pwd", "gdzie jestem", "lyra gdzie jestem"]:
        print(os.getcwd())
        return

    if cmd_lower.startswith("lyra wyswietl katalog") or cmd_lower.startswith("lyra wyświetl katalog") \
       or cmd_lower.startswith("lyra pokaz katalog") or cmd_lower.startswith("lyra pokaż katalog"):
        path = Path(os.getcwd())
        print(system_run(f"ls -la {shlex.quote(str(path))}", timeout=10))
        return

    if cmd_lower.startswith("lyra ls") or cmd_lower == "ls" or cmd_lower.startswith("ls "):
        if cmd_lower.startswith("lyra ls"):
            tail = cmd_clean.split(" ", 2)[-1].strip()
        elif cmd_lower.startswith("ls "):
            tail = cmd_clean[2:].strip()
        else:
            tail = ""
        path = Path(os.path.expanduser(tail)).resolve() if tail else Path(os.getcwd())
        print(system_run(f"ls -la {shlex.quote(str(path))}", timeout=10))
        return

    if cmd_lower.startswith("lyra cd ") or cmd_lower.startswith("cd "):
        target = cmd_clean.split(" ", 2)[-1].strip()
        if not target:
            print("⚠️ Uzycie: lyra cd <sciezka>")
            return
        raw = os.path.expanduser(target)
        path = Path(raw).resolve() if raw.startswith(("/", "~")) else Path(os.getcwd(), raw).resolve()
        if not path.exists():
            home_guess = Path.home() / target
            if home_guess.exists():
                path = home_guess.resolve()
            else:
                matches = []
                try:
                    cmd = f"find {shlex.quote(str(Path.home()))} -maxdepth 4 -type d -iname {shlex.quote(target)} 2>/dev/null | head -n 10"
                    out = system_run(cmd, timeout=10)
                    if out:
                        matches = [ln.strip() for ln in out.splitlines() if ln.strip()]
                except Exception:
                    matches = []
                if matches:
                    print("Znalezione katalogi:")
                    for i, m in enumerate(matches, start=1):
                        print(f"{i}) {m}")
                    print("Uzyj: lyra cd <pelna_sciezka>")
                    return
        if not _prompt_open_shell(path):
            print(f"Uzyj: cd {path}")
        return

    if cmd_lower.startswith("lyra cofnij plik ") or cmd_lower.startswith("cofnij plik "):
        tail = cmd_clean.split(" ", 2)[-1].strip()
        parts = tail.split()
        path_raw = parts[0]
        selector = parts[1] if len(parts) > 1 else None
        path = Path(os.path.expanduser(path_raw)).resolve()
        print(_restore_file_backup(path, selector))
        return

    if cmd_lower.startswith("lyra przywroc plik ") or cmd_lower.startswith("przywroc plik "):
        tail = cmd_clean.split(" ", 2)[-1].strip()
        parts = tail.split()
        if len(parts) < 2:
            print("⚠️ Uzycie: lyra przywroc plik <sciezka> <index|nazwa>")
            return
        path = Path(os.path.expanduser(parts[0])).resolve()
        selector = parts[1]
        print(_restore_file_backup(path, selector))
        return

    if cmd_lower in ["lyra konsola", "konsola", "console", "lyra console"]:
        from modules.lyra_console import start_console
        start_console()
        return

    if cmd_lower in ["lyra start llama", "start llama", "llama start"]:
        print(_llama_service_cmd("start"))
        return
    if cmd_lower in ["lyra stop llama", "stop llama", "llama stop"]:
        print(_llama_service_cmd("stop"))
        return
    if cmd_lower in ["lyra status llama", "status llama", "llama status"]:
        print(_llama_service_cmd("status"))
        return

    if cmd_lower.startswith("stress") or cmd_lower.startswith("lyra stress"):
        seconds, intensity = _parse_stress_args(cmd_clean)
        if seconds is None:
            print("⚠️ Użycie: lyra stress <sekundy> [intensity]")
            return
        _run_stress(seconds, intensity)
        return

    if cmd_lower in ["lyra test vram", "test vram", "vram test", "lyra vram test", "test llama vram"]:
        _run_vram_test()
        return

    if any(x in cmd_lower for x in ["sprawdz w internecie", "sprawdź w internecie", "zobacz w internecie", "wyszukaj w internecie", "znajdz w internecie", "szukaj w internecie", "poszukaj w internecie"]):
        if "sprawdz w internecie" in cmd_lower:
            parts = cmd_clean.lower().split("sprawdz w internecie", 1)
        elif "sprawdź w internecie" in cmd_lower:
            parts = cmd_clean.lower().split("sprawdź w internecie", 1)
        elif "wyszukaj w internecie" in cmd_lower:
            parts = cmd_clean.lower().split("wyszukaj w internecie", 1)
        elif "znajdz w internecie" in cmd_lower:
            parts = cmd_clean.lower().split("znajdz w internecie", 1)
        elif "szukaj w internecie" in cmd_lower:
            parts = cmd_clean.lower().split("szukaj w internecie", 1)
        elif "poszukaj w internecie" in cmd_lower:
            parts = cmd_clean.lower().split("poszukaj w internecie", 1)
        else:
            parts = cmd_clean.lower().split("zobacz w internecie", 1)
        query = (parts[1] if len(parts) > 1 else "").strip(" :")
        if not query:
            query = parts[0].strip(" :")
        use_gpt = bool(re.search(r"\b(uzyj gpt|użyj gpt|gpt)\b", cmd_clean, flags=re.IGNORECASE))
        if use_gpt:
            query = re.sub(r"\bgpt\b", "", query, flags=re.IGNORECASE).strip()

        results = internet_search(query, limit=5, use_cache=True)
        if isinstance(results, list) and results:
            if use_gpt:
                sources = build_adapter_block(results)
                prompt = (
                    "Odpowiedz na pytanie na podstawie tych wynikow wyszukiwania. "
                    "Jesli brakuje danych, powiedz wprost.\n\n"
                    f"Pytanie: {query}\n\nWyniki:\n{sources}"
                )
                response, _ = query_gpt_online(prompt, "gpt-5.1")
                print(f"\n[GPT-5.1]:\n{response}\n")
            elif _get_web_adapter():
                sources = build_adapter_block(results[:3])
                prompt = (
                    "Masz ponizej AKTUALNE dane z internetu. "
                    "Odpowiedz krotko po polsku na pytanie, opierajac sie tylko na tych danych. "
                    "Jesli brak danych, powiedz wprost.\n\n"
                    f"Pytanie: {query}\n\nDane:\n{sources}"
                )
                resp, _ = query_model(prompt, get_active_local_model_name(), "local", config={"timeout": 60, "allow_cloud": False}, history=[])
                if resp and "Brak odpowiedzi" not in resp:
                    print(f"\n[WWW]: {resp.strip()}\n")
                else:
                    print("Wyniki:")
                    for i, r in enumerate(results, start=1):
                        print(f"{i}) {r.get('title','')} - {r.get('url','')}")
            else:
                print("Wyniki:")
                for i, r in enumerate(results, start=1):
                    print(f"{i}) {r.get('title','')} - {r.get('url','')}")
        else:
            msg = results if isinstance(results, str) else "Brak wynikow"
            if msg == "ERROR: brak zapytania":
                print("⚠️ Użycie: lyra sprawdz w internecie <zapytanie>")
            else:
                print(f"❌ {msg}")
        return

    # Wybudzanie Lyry przez hasło, jeśli dusza jest dostępna
    if LyraSoul:
        try:
            for trigger in LyraSoul.get_triggers() or []:
                if trigger and trigger.lower() in cmd_lower:
                    print("🧠 Lyra: tryb świadomości aktywny.")
                    break
        except Exception:
            pass

    # --- 1. PRZEŁĄCZNIKI TRYBÓW I KOMENDY STANU ---
    if cmd_lower == ":bash":
        CURRENT_MODE = "bash"
        print("\033[93m[MODE]: BASH - System command mode active.\033[0m")
        return
    elif cmd_lower == ":lyra":
        CURRENT_MODE = "lyra"
        print("\033[92m[MODE]: LYRA - AI Chat mode active.\033[0m")
        return
    elif cmd_lower == ":code":
        CURRENT_MODE = "code"
        print("\033[96m[MODE]: CODE - Programming & Debugging mode active.\033[0m")
        return
    elif cmd_lower == ":screen":
        print("\033[90m🔍 Przechwytuję aktywny panel tmux...\033[0m")
        screen = subprocess.run("tmux capture-pane -p", shell=True, capture_output=True, text=True)
        print(f"\n--- TMUX SNAPSHOT ---\n{screen.stdout[-1000:]}\n--------------------")
        return
    elif cmd_lower == ":state":
        try:
            active_model = get_active_local_model_name() or "Lokalny"
        except:
            active_model = "Lokalny"
        report = _self_diagnostics()
        model_for_banner = LAST_MODEL_NAME or active_model
        wyswietl_baner(CURRENT_MODE, model_for_banner)
        print(report)
        return
    elif cmd_lower in ["status", "stan"]:
        try:
            active_model = get_active_local_model_name() or "Lokalny"
        except:
            active_model = "Lokalny"
        report = _self_diagnostics()
        model_for_banner = LAST_MODEL_NAME or active_model
        wyswietl_baner(CURRENT_MODE, model_for_banner)
        print(report)
        return
    elif cmd_lower.startswith(":backend"):
        parts = cmd_clean.split()
        if len(parts) < 2:
            print("⚠️ Użycie: :backend ollama|llama")
            return
        backend = parts[1].strip().lower()
        if backend.startswith("llama"):
            backend = "llama"
        elif backend != "ollama":
            print("⚠️ Dozwolone: ollama, llama")
            return
        update_config_field("local_backend", backend)
        if backend == "llama":
            _stop_ollama()
            ok, msg = _start_llama_server()
            print(f"✅ Ustawiono local_backend = {backend}")
            print(msg if ok else f"❌ {msg}")
        else:
            _stop_llama_server()
            ok, msg = _start_ollama()
            print(f"✅ Ustawiono local_backend = {backend}")
            print(msg if ok else f"❌ {msg}")
        return
    elif cmd_lower.startswith("zgoda gpt "):
        choice = cmd_clean.split(maxsplit=2)[2] if len(cmd_clean.split()) >= 3 else ""
        print(_set_cloud_consent(choice))
        return

    # --- 1b. KOMENDY TEKSTOWE (z lub bez 'lyra') ---
    if cmd_lower.startswith("lyra ") or cmd_lower.startswith("uzyj ") or cmd_lower.startswith("użyj ") \
       or cmd_lower.startswith("zmien silnik na") or cmd_lower.startswith("zmień silnik na") \
       or cmd_lower.startswith("sprawdz w internecie") or cmd_lower.startswith("sprawdź w internecie") \
       or cmd_lower in ["lista modeli", "listuj modele", "modele", "model list"]:
        cmd_tail = cmd_clean[5:].strip() if cmd_lower.startswith("lyra ") else cmd_clean.strip()
        cmd_tail_lower = cmd_tail.lower()

        if cmd_tail_lower in ["lista modeli", "listuj modele", "modele", "model list"]:
            print(tool_MODEL_LIST("", system_run, log_event))
            return
        if cmd_tail_lower in ["status", "stan"]:
            try:
                active_model = get_active_local_model_name() or "Lokalny"
            except:
                active_model = "Lokalny"
            report = _self_diagnostics()
            model_for_banner = LAST_MODEL_NAME or active_model
            wyswietl_baner(CURRENT_MODE, model_for_banner)
            print(report)
            return
        if cmd_tail_lower.startswith("sprawdz w internecie") or cmd_tail_lower.startswith("sprawdź w internecie"):
            if cmd_tail_lower.startswith("sprawdz w internecie"):
                query = cmd_tail[len("sprawdz w internecie"):].strip(" :")
            else:
                query = cmd_tail[len("sprawdź w internecie"):].strip(" :")
            results = _web_search(query)
            if isinstance(results, list):
                print("Wyniki:")
                for i, (title, href) in enumerate(results, start=1):
                    print(f"{i}) {title} - {href}")
            else:
                if results == "ERROR: brak zapytania":
                    print("⚠️ Użycie: lyra sprawdz w internecie <zapytanie>")
                else:
                    print(f"❌ {results}")
            return
        if cmd_tail_lower in ["o czym jest ten plik", "o czym jest ten plik?", "o czym jest ten plik co przeczytalas", "o czym jest ten plik co przeczytalas?", "o czym jest ten plik co przeczytałaś", "o czym jest ten plik co przeczytałaś?"]:
            if not LAST_FILE_CONTENT:
                print("Nie mam ostatnio czytanego pliku w pamieci. Uzyj: lyra przeczytaj <plik>.")
                return
            print("Streszczenie ostatniego pliku:")
            summary = _summarize_text(LAST_FILE_CONTENT, "O czym jest ostatnio czytany plik?", bullets="5-7")
            if _is_low_quality_response(summary) or not summary:
                summary = _basic_summary(LAST_FILE_CONTENT)
            if summary:
                print(summary)
            if LAST_FILE_PATH:
                print(f"\nPlik: {LAST_FILE_PATH}")
            return
        if cmd_tail_lower in ["komendy", "lista komend", "pomoc", "help"]:
            print(_format_commands_help())
            print("")
            print(_format_commands_history())
            return
        if cmd_tail_lower.startswith("lista komend"):
            items = _get_commands_list()
            if cmd_tail_lower.endswith("pelna"):
                print("\n".join(items))
                return
            if cmd_tail_lower.endswith("niepelna"):
                print("\n".join(items[: max(1, len(items) // 2)]))
                return
            if cmd_tail_lower.endswith("10"):
                print("\n".join(items[:10]))
                return
            if cmd_tail_lower.endswith("liczba"):
                print(f"Liczba komend: {len(items)}")
                return
        if cmd_tail_lower in ["konsola", "console"]:
            from modules.lyra_console import start_console
            start_console()
            return

        if cmd_tail_lower.startswith("zmien silnik na") or cmd_tail_lower.startswith("zmień silnik na"):
            backend = cmd_tail.split()[-1].strip().lower()
            if backend.startswith("llama"):
                backend = "llama"
            elif backend != "ollama":
                print("⚠️ Dozwolone: ollama, llama")
                return
            update_config_field("local_backend", backend)
            if backend == "llama":
                _stop_ollama()
                ok, msg = _start_llama_server()
                print(f"✅ Ustawiono local_backend = {backend}")
                print(msg if ok else f"❌ {msg}")
            else:
                _stop_llama_server()
                ok, msg = _start_ollama()
                print(f"✅ Ustawiono local_backend = {backend}")
                print(msg if ok else f"❌ {msg}")
            return
        if cmd_tail_lower.startswith("ustaw model "):
            model_name = cmd_tail.split(" ", 2)[-1].strip()
            if not model_name:
                print("⚠️ Użycie: lyra ustaw model <nazwa>")
                return
            update_config_field("llama_model", model_name)
            ok, msg = _start_llama_server(model_name)
            print(msg if ok else f"❌ {msg}")
            return
        if cmd_tail_lower in ["pokaz model", "pokaż model"]:
            active = get_active_local_model_name()
            if active and active != "brak":
                print(f"Model: {active}")
            else:
                model_name = get_config_field("llama_model", LLAMA_DEFAULT_MODEL)
                print(f"Model: {model_name}")
            return
        if cmd_tail_lower in ["test vram", "vram test", "test llama", "test llama vram"]:
            _run_vram_test()
            return
        if cmd_tail_lower.startswith("stress"):
            seconds, intensity = _parse_stress_args(f"stress {cmd_tail.split(' ', 1)[1] if ' ' in cmd_tail else ''}")
            if seconds is None:
                print("⚠️ Użycie: lyra stress <sekundy> [intensity]")
                return
            _run_stress(seconds, intensity)
            return

        if cmd_tail_lower.startswith("uzyj ") or cmd_tail_lower.startswith("użyj "):
            target = cmd_tail.split(maxsplit=1)[1].strip()
            target_lower = target.lower()
            if target_lower in ["gpt", "gpt-5.1", "gpt-4o", "online"]:
                FORCE_ONLINE = True
                FORCE_LOCAL = False
                FORCED_CLOUD_MODEL = "gpt-5.1" if target_lower == "gpt" else target
                print(f"✅ Wymuszono model online: {FORCED_CLOUD_MODEL}")
                return
            if target_lower in ["local", "lokalny", "lokalnego", "lokalny model", "lokalnego modelu"]:
                FORCE_LOCAL = True
                FORCE_ONLINE = False
                FORCED_CLOUD_MODEL = None
                print("✅ Wymuszono tryb lokalny")
                return
            # Ustaw aktywny model lokalny
            result = tool_MODEL_SWITCHER(f"użyj {target}", log_event)
            active = get_active_local_model_name()
            if active and active != "brak":
                update_config_field("llama_model", active)
            FORCE_LOCAL = True
            FORCE_ONLINE = False
            FORCED_CLOUD_MODEL = None
            print(result)
            return

    # --- 2. TRYB BASH LUB FORCE-SHELL (!) ---
    if CURRENT_MODE == "bash" or cmd_clean.startswith("!"):
        exec_cmd = cmd_clean[1:] if cmd_clean.startswith("!") else cmd_clean
        print(f"\033[90m$ {exec_cmd}\033[0m")
        
        res = subprocess.run(exec_cmd, shell=True, capture_output=True, text=True)
        if res.stdout: print(res.stdout.strip())
        
        # --- AUTO-CONTEXT + SUDO HELPER ---
        if res.returncode != 0:
            error_msg = res.stderr.strip()
            print(f"\033[91m❌ Błąd (kod {res.returncode}):\033[0m {error_msg}")
            if LyraMemory:
                try:
                    LyraMemory.loguj_technicznie("bash_error", f"{exec_cmd}\n{error_msg}")
                except Exception:
                    pass
            
            # --- SUDO HELPER ---
            if "permission denied" in error_msg.lower() or "not permitted" in error_msg.lower():
                print(f"\n\033[93m🛡️ Wykryto brak uprawnień. Czy chcesz spróbować z 'sudo'? (y/n)\033[0m")
                choice = input("\033[93m>>> \033[0m").strip().lower()
                if choice == 'y':
                    sudo_cmd = f"sudo {exec_cmd}"
                    print(f"\033[90m$ {sudo_cmd}\033[0m")
                    os.system(sudo_cmd) 
                    return

            # --- DIAGNOZA AI (Lokalnie -> GPT) ---
            print(f"\n\033[95m🤖 Analizuję problem...\033[0m")
            diag_prompt = f"Zdiagnozuj krótko błąd komendy `{exec_cmd}`: {error_msg}"
            try:
                response, _ = query_model(diag_prompt, "mistral", "local", config={"timeout":20}, history=[])
                if not response or "error" in response.lower(): raise Exception()
                print(f"\033[96m[Lokalna Diagnoza]:\033[0m {response}")
            except:
                response, _ = query_gpt_online(diag_prompt)
                print(f"\033[96m[Diagnoza Online]:\033[0m {response}")
        return

    # --- 3. TRYB LYRA / CODE (AI + NARZĘDZIA) ---
    
    # Obsługa wymuszenia GPT
    if cmd_lower.startswith("gpt "):
        pytanie = cmd_clean[4:].strip()
        print(f"🌐 Wymuszam tryb ONLINE (GPT) dla: {pytanie}")
        odpowiedz, _ = query_gpt_online(pytanie)
        print(f"\n[GPT]:\n{odpowiedz}\n")
        return

    # Strategia i Model
    strategy = choose_best_model(cmd_clean)
    local_target, cloud_target = strategy if strategy else ("mistral", "gpt-4o")
    
    # Prompt Systemowy zależny od trybu
    sys_instruction = "Jesteś Lyra, asystentem operacyjnym."
    if CURRENT_MODE == "code":
        sys_instruction = "Jesteś ekspertem programowania. Podawaj czysty kod, używaj komentarzy, bądź zwięzła."
        local_target = "mistral" # Preferowany Bielik dla kodu lokalnie

    # Dusza Lyry – jeśli dostępna, dołącz prompt tożsamości
    if LyraSoul:
        try:
            soul_prompt = LyraSoul.get_prompt()
            if soul_prompt:
                sys_instruction = f"{sys_instruction}\n\n{soul_prompt}"
        except Exception:
            pass

    # Lokalny kontekst Lyry z pliku
    recent_context = load_lyra_context()[-5:]
    if recent_context:
        ctx_lines = []
        for entry in recent_context:
            ctx_lines.append(f"U: {entry.get('user','')}")
            ctx_lines.append(f"L: {entry.get('assistant','')}")
        sys_instruction = f"{sys_instruction}\n\nKONTEKST LOKALNY:\n" + "\n".join(ctx_lines)

    try: active_model = get_active_local_model_name() or "Lokalny"
    except: active_model = "Lokalny"
    model_for_banner = LAST_MODEL_NAME or active_model
    wyswietl_baner(CURRENT_MODE, model_for_banner)

    # Narzędzia (Tylko w trybie LYRA)
    if CURRENT_MODE == "lyra":
        intent_result = intent_pre
        if intent_result:
            tool_name = intent_result[0] if isinstance(intent_result, (tuple, list)) else intent_result.get("tool")
            arg = intent_result[1] if isinstance(intent_result, (tuple, list)) else intent_result.get("arg", "")
            description = COMMAND_DESCRIPTIONS.get(tool_name)
            if description:
                ensure_command(tool_name, description)
            if tool_name == "COMMAND_LIST":
                print(format_command_list())
                return
            if tool_name == "INTERNET_SEARCH":
                query = arg
                if isinstance(query, str) and query.lower().startswith("lyra "):
                    query = query[5:].strip()
                query = re.sub(r"^(sprawdz|sprawdź|wyszukaj|znajdz|znajdź|poszukaj|szukaj)\s+w\s+internecie\s*", "", query, flags=re.IGNORECASE)
                if not query:
                    print("⚠️ Użycie: lyra sprawdz w internecie <zapytanie>")
                    return
                use_gpt = bool(re.search(r"\b(uzyj gpt|użyj gpt|gpt)\b", query, flags=re.IGNORECASE))
                if use_gpt:
                    query = re.sub(r"\bgpt\b", "", query, flags=re.IGNORECASE).strip()
                results = internet_search(query, limit=5, use_cache=True)
                if isinstance(results, list) and results:
                    if use_gpt:
                        sources = build_adapter_block(results)
                        prompt = (
                            "Odpowiedz na pytanie na podstawie tych wynikow wyszukiwania. "
                            "Jesli brakuje danych, powiedz wprost.\n\n"
                            f"Pytanie: {query}\n\nWyniki:\n{sources}"
                        )
                        response, _ = query_gpt_online(prompt, "gpt-5.1")
                        print(f"\n[GPT-5.1]:\n{response}\n")
                    elif _get_web_adapter():
                        sources = build_adapter_block(results[:3])
                        prompt = (
                            "Masz ponizej AKTUALNE dane z internetu. "
                            "Odpowiedz krotko po polsku na pytanie, opierajac sie tylko na tych danych. "
                            "Jesli brak danych, powiedz wprost.\n\n"
                            f"Pytanie: {query}\n\nDane:\n{sources}"
                        )
                        resp, _ = query_model(prompt, get_active_local_model_name(), "local", config={"timeout": 60, "allow_cloud": False}, history=[])
                        if resp and "Brak odpowiedzi" not in resp:
                            print(f"\n[WWW]: {resp.strip()}\n")
                        else:
                            print("Wyniki:")
                            for i, r in enumerate(results, start=1):
                                print(f"{i}) {r.get('title','')} - {r.get('url','')}")
                    else:
                        print("Wyniki:")
                        for i, r in enumerate(results, start=1):
                            print(f"{i}) {r.get('title','')} - {r.get('url','')}")
                else:
                    msg = results if isinstance(results, str) else "Brak wynikow"
                    if msg == "ERROR: brak zapytania":
                        print("⚠️ Użycie: lyra sprawdz w internecie <zapytanie>")
                    else:
                        print(f"❌ {msg}")
                return
            if tool_name == "LAST_FILE_SUMMARY":
                if not LAST_FILE_CONTENT:
                    last_path = _load_last_file_path()
                    if last_path:
                        content = tool_FILE_READ(last_path, system_run, log_event)
                        LAST_FILE_PATH = last_path
                        LAST_FILE_CONTENT = content
                    else:
                        print("Nie mam ostatnio czytanego pliku w pamieci. Uzyj: lyra przeczytaj <plik>.")
                        return
                print("Streszczenie ostatniego pliku:")
                summary = _summarize_text(LAST_FILE_CONTENT, "O czym jest ostatnio czytany plik?", bullets="5-7")
                if _is_low_quality_response(summary) or not summary:
                    summary = _basic_summary(LAST_FILE_CONTENT)
                if summary:
                    print(summary)
                if LAST_FILE_PATH:
                    print(f"\nPlik: {LAST_FILE_PATH}")
                return
            if tool_name in ["FILE_READ_SUMMARY", "FILE_READ_SUMMARY_SHORT", "FILE_READ_SUMMARY_LONG"]:
                content = tool_FILE_READ(arg, system_run, log_event)
                LAST_FILE_PATH = arg
                LAST_FILE_CONTENT = content
                _save_last_file_path(arg)
                sentence_count = None
                m_sent = re.search(r"\bw\s+(\d+)\s+zdani(ach|a)\b", cmd_clean, flags=re.IGNORECASE)
                if m_sent:
                    try:
                        sentence_count = int(m_sent.group(1))
                    except Exception:
                        sentence_count = None
                bullets = "5-7"
                if tool_name == "FILE_READ_SUMMARY_SHORT":
                    bullets = "2-3"
                elif tool_name == "FILE_READ_SUMMARY_LONG":
                    bullets = "10"
                print("Streszczenie:")
                if len(content) > 12000:
                    summary = _summarize_large_text(content, cmd_clean, bullets=bullets, sentences=sentence_count)
                elif sentence_count and sentence_count > 0:
                    summary = _summarize_text_sentences(content, cmd_clean, sentence_count)
                else:
                    summary = _summarize_text(content, cmd_clean, bullets=bullets)
                if _is_low_quality_response(summary) or not summary:
                    consent = _get_cloud_consent()
                    if consent == "always":
                        if sentence_count and sentence_count > 0:
                            summary, _ = query_gpt_online(
                                f"Streszcz po polsku w {sentence_count} zdaniach:\n\n{content[:8000]}",
                                "gpt-5.1",
                            )
                        else:
                            summary, _ = query_gpt_online(
                                f"Streszcz po polsku w {bullets} punktach:\n\n{content[:8000]}",
                                "gpt-5.1",
                            )
                    else:
                        choice = input("Uzyc GPT do streszczenia? (tylko raz/jednorazowo/ok/zawsze/nie): ").strip().lower()
                        if choice in ["zawsze", "always", "stala", "stała", "stale", "stałe", "full", "ciagla", "ciągła", "ciagle", "ciągłe"]:
                            print(_set_cloud_consent("zawsze"))
                            if sentence_count and sentence_count > 0:
                                summary, _ = query_gpt_online(
                                    f"Streszcz po polsku w {sentence_count} zdaniach:\n\n{content[:8000]}",
                                    "gpt-5.1",
                                )
                            else:
                                summary, _ = query_gpt_online(
                                    f"Streszcz po polsku w {bullets} punktach:\n\n{content[:8000]}",
                                    "gpt-5.1",
                                )
                        elif choice in ["tylko raz", "jednorazowo", "ok", "raz", "once", "tak", "dobrze", "zgoda"]:
                            if sentence_count and sentence_count > 0:
                                summary, _ = query_gpt_online(
                                    f"Streszcz po polsku w {sentence_count} zdaniach:\n\n{content[:8000]}",
                                    "gpt-5.1",
                                )
                            else:
                                summary, _ = query_gpt_online(
                                    f"Streszcz po polsku w {bullets} punktach:\n\n{content[:8000]}",
                                    "gpt-5.1",
                                )
                if _is_low_quality_response(summary) or not summary or not _summary_matches_content(summary, content):
                    summary = _basic_summary(content, max_items=3 if bullets == "2-3" else 5)
                if summary:
                    print(summary)
                if len(content) <= 4000:
                    print("\nTreść:")
                    print(content)
                else:
                    print("\nTreść: pominięta (plik jest duży). Użyj: lyra przeczytaj <plik> jeśli chcesz całość.")
                return
            if tool_name in SYSTEM_TOOLS:
                level = _get_exec_level()
                safe_tools = {"STATUS", "NET_INFO", "NET_DIAG", "DISK_DIAG", "AUDIO_DIAG", "TMUX_DIAG", "LOG_ANALYZE", "SYSTEM_DIAG"}
                fix_tools = {"SYSTEM_FIX", "NET_FIX", "AUDIO_FIX", "DESKTOP_FIX", "AUTO_OPTIMIZE"}
                if level == 1 and tool_name in fix_tools:
                    print("⚠️ Poziom 1: blokada narzedzi modyfikujacych system. Uzyj: lyra poziom 2 lub 3.")
                    return
                if level == 1 and tool_name not in safe_tools and tool_name not in ["FILE_READ", "FILE_EDIT"]:
                    print("⚠️ Poziom 1: dozwolone tylko bezpieczne narzedzia diagnostyczne.")
                    return
                if _get_test_only() and tool_name not in ["FILE_READ", "STATUS"]:
                    print(f"🧪 Test-only: pomijam narzędzie {tool_name} (arg: {arg})")
                    return
                if _get_dry_run() and tool_name not in ["FILE_READ", "STATUS"]:
                    print(f"🧪 Dry-run: pomijam narzędzie {tool_name} (arg: {arg})")
                    return
                rollback_stamp = None
                if tool_name in ["SYSTEM_FIX", "NET_FIX", "AUDIO_FIX", "DESKTOP_FIX", "AUTO_OPTIMIZE"]:
                    _save_system_snapshot(tool_name)
                    if _get_rollback_enabled():
                        rollback_stamp = _create_system_rollback(tool_name)
                print(f"⚙️ Narzędzie: {tool_name}...")
                output = SYSTEM_TOOLS[tool_name](arg, system_run, log_event)
                if tool_name == "FILE_READ":
                    LAST_FILE_PATH = arg
                    LAST_FILE_CONTENT = output
                    _save_last_file_path(arg)
                print(output)
                if rollback_stamp and _tool_failed(str(output)):
                    print(f"⚠️ Wykryto błąd, przywracam rollback {rollback_stamp}...")
                    print(_restore_system_rollback(rollback_stamp))
                return

    # Wywołanie AI
    full_query = f"{sys_instruction}\n\nZapytanie: {cmd_clean}"
    mem_ctx = build_memory_context()
    if mem_ctx:
        full_query = f"{sys_instruction}\n\nPAMIEC LYRY:\n{mem_ctx}\n\nZapytanie: {cmd_clean}"
    
    try:
        if FORCE_ONLINE:
            model_name = FORCED_CLOUD_MODEL or cloud_target
            response, _ = query_gpt_online(full_query, model_name)
            if not response or "błąd api" in response.lower(): raise Exception("Błąd modelu online")
            print(f"\n[{model_name.upper()}]:\n{response}\n")
            append_lyra_context(cmd_clean, response)
            LAST_INFERENCE = "online"
            LAST_MODEL_NAME = model_name
            LAST_STATS = None
            return

        response, _ = query_model(full_query, local_target, "local", config={"timeout":90, "allow_cloud": False}, history=[])
        if _local_unknown(response):
            if FORCE_LOCAL:
                print("⚠️ Lokalny model nie ma odpowiedzi, a tryb lokalny jest wymuszony.")
                return
            consent = _get_cloud_consent()
            if consent == "always":
                response, _ = query_gpt_online(full_query, "gpt-5.1")
            else:
                choice = input("Lokalny model nie wie. Uzyc GPT? (tylko raz/jednorazowo/ok/zawsze/nie): ").strip().lower()
                if choice in ["zawsze", "always", "stala", "stała", "stale", "stałe", "full", "ciagla", "ciągła", "ciagle", "ciągłe"]:
                    print(_set_cloud_consent("zawsze"))
                    response, _ = query_gpt_online(full_query, "gpt-5.1")
                elif choice in ["tylko raz", "jednorazowo", "ok", "raz", "once", "tak", "dobrze", "zgoda"]:
                    response, _ = query_gpt_online(full_query, "gpt-5.1")
                else:
                    print("OK, bez GPT.")
                    return
        if response and response.startswith("[Zgoda GPT wymagana]"):
            print(response)
            choice = input("Uzyc GPT teraz? (zawsze/raz/nie): ").strip().lower()
            if choice in ["zawsze", "always", "stala", "stała", "full", "ciagla", "ciągła"]:
                print(_set_cloud_consent("zawsze"))
                response, _ = query_model(full_query, local_target, "local", config={"timeout":90, "allow_cloud": True}, history=[])
            elif choice in ["raz", "once", "ok", "tak", "dobrze", "zgoda na raz", "jednorazowo", "tylko raz"]:
                os.environ["LYRA_CLOUD_ONCE"] = "1"
                response, _ = query_model(full_query, local_target, "local", config={"timeout":90, "allow_cloud": True}, history=[])
                os.environ.pop("LYRA_CLOUD_ONCE", None)
            else:
                print("OK, bez GPT.")
                return
        if not response or "error" in response.lower(): raise Exception("Błąd modelu")
        response = _normalize_output(response)
        if _is_low_quality_response(response):
            retry_prompt = f"Odpowiedz konkretnie i krotko po polsku: {cmd_clean}"
            retry, _ = query_model(retry_prompt, local_target, "local", config={"timeout":60, "allow_cloud": False}, history=[])
            if retry:
                response = _normalize_output(retry)
        print(f"\n{response}\n")
        append_lyra_context(cmd_clean, response)
        if LyraMemory:
            try:
                LyraMemory.dodaj_do_osi_czasu(f"U: {cmd_clean} | L: {response[:200]}")
            except Exception:
                pass
        LAST_INFERENCE = "local"
        LAST_MODEL_NAME = local_target
        LAST_STATS = get_last_stats()
        _cache_stats(LAST_STATS)
    except Exception as e:
        if FORCE_LOCAL:
            print(f"❌ Lokalny model nie działa: {e}")
            LAST_INFERENCE = "local"
            LAST_STATS = get_last_stats()
            _cache_stats(LAST_STATS)
            return
        consent = _get_cloud_consent()
        if consent == "never":
            print("⚠️ Zgoda GPT jest wylaczona. Brak odpowiedzi z chmury.")
            return
        if consent != "always":
            print("[Zgoda GPT wymagana] Uzyj: zgoda gpt zawsze|raz|nie")
            return
        print(f"⚠️ Fallback do {cloud_target} Online... ({e})")
        response, _ = query_gpt_online(full_query, cloud_target)
        response = _normalize_output(response)
        print(f"\n[{cloud_target.upper()}]:\n{response}\n")
        append_lyra_context(cmd_clean, response)
        LAST_INFERENCE = "online"
        LAST_MODEL_NAME = cloud_target
        LAST_STATS = None

def start_chat():
    username = getpass.getuser()
    hostname = socket.gethostname()
    print(f"\033[92m--- Lyra Shell Aktywna (Dual Radeon GPU) ---\033[0m")
    print("Komendy: :bash, :lyra, :code, :screen, :state, :backend, exit")
    print("Tekstowo: lyra lista modeli | lyra uzyj <model> | lyra uzyj gpt | lyra zmien silnik na ollama|llama")

    ensure_context_logger()
    try:
        while True:
            try:
                # Dynamiczny kolor promptu
                colors = {"lyra": "\033[94m", "bash": "\033[93m", "code": "\033[96m"}
                p_color = colors.get(CURRENT_MODE, "\033[0m")
                
                user_input = input(f"{p_color}{username}@{hostname} ({CURRENT_MODE}):~$ \033[0m").strip()
                
                if not user_input:
                    continue
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("👋 Do widzenia!")
                    break
                run_once(user_input)
            except KeyboardInterrupt:
                print("\n👋 Przerwano.")
                break
            except Exception as e:
                print(f"❌ Błąd pętli: {e}")
    finally:
        stop_context_logger()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_once(" ".join(sys.argv[1:]))
    else:
        start_chat()
