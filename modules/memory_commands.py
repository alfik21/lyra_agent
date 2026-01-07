import os
import re
import sys
from datetime import datetime
from pathlib import Path
import shutil

BASE_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = BASE_DIR / "lyra_project"
if CORE_DIR.exists():
    sys.path.insert(0, str(CORE_DIR))

try:
    from jądro.zarzadca_pamieci import pamiec as LyraMemory
except Exception:
    LyraMemory = None


def parse_memory_command(raw_cmd: str):
    cmd = raw_cmd.strip()
    if not cmd:
        return None
    if cmd.lower().startswith("lyra "):
        cmd = cmd[5:].strip()
    m = re.search(r"^(zapamiętaj|zapamietaj|niezapomnij|zapisz|zaloguj)\b[:\\s,-]*", cmd, flags=re.IGNORECASE)
    if not m:
        return None
    trigger = m.group(1).lower()
    payload = cmd[m.end():].strip()
    if trigger in ["zapamiętaj", "zapamietaj"]:
        return ("dluga", payload)
    if trigger == "niezapomnij":
        return ("biezaca", payload)
    if trigger in ["zapisz", "zaloguj"]:
        return ("logowa", payload)
    return None


def handle_memory_command(raw_cmd: str):
    parsed = parse_memory_command(raw_cmd)
    if not parsed:
        return None
    if not LyraMemory:
        return "⚠️ Pamięć Lyry niedostępna (brak modułu jądra)."
    kind, payload = parsed
    if not payload:
        return "⚠️ Podaj treść do zapisu po komendzie."
    try:
        backup_dir = BASE_DIR / "logs" / "memory_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for name in ["Pamiec.json", "PamiecBiezaca.json", "PamiecLogowa.json"]:
            path = BASE_DIR / name
            if path.exists():
                shutil.copy2(path, backup_dir / f"{name}.{stamp}.bak")
    except Exception:
        pass
    if kind == "dluga":
        key = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        LyraMemory.zapisz_fakt(key, payload)
        return "✅ Zapisano w Pamiec.json"
    if kind == "biezaca":
        LyraMemory.dodaj_do_osi_czasu(payload)
        return "✅ Zapisano w PamiecBiezaca.json"
    if kind == "logowa":
        LyraMemory.loguj_technicznie("USER_ZAPISZ", payload)
        return "✅ Zapisano w PamiecLogowa.json"
    return None


def record_context_line(text: str):
    if not LyraMemory:
        return
    try:
        LyraMemory.zapisz_kontekst(text)
    except Exception:
        pass


def build_memory_context(max_chars: int = 8000):
    if not LyraMemory:
        return ""
    try:
        dluga = LyraMemory.odczytaj("dluga") or {}
        biezaca = LyraMemory.odczytaj("biezaca") or []
    except Exception:
        return ""
    parts = []
    if isinstance(dluga, dict) and dluga:
        items = list(dluga.items())[:20]
        chunk = "\n".join([f"- {k}: {v}" for k, v in items])
        parts.append("Pamiec_dluga:\n" + chunk)
    if isinstance(biezaca, list) and biezaca:
        recent = biezaca[-5:]
        chunk = "\n".join([f"- {x.get('data','')}: {x.get('zdarzenie','')}" for x in recent])
        parts.append("Pamiec_biezaca:\n" + chunk)
    text = "\n\n".join(parts).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[OBIĘTE]..."
    return text
