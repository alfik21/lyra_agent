import os
import re
from pathlib import Path

from modules.file_memory import record_file_event

MAX_BYTES = 1_000_000


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def tool_FILE_READ(arg: str, system_run=None, log_fn=None):
    raw = (arg or "").strip()
    if not raw:
        return "Podaj sciezke pliku."
    raw = _strip_quotes(raw).lstrip(":").strip()
    # usuń typowe dopiski poleceń
    for token in [" i podsumuj", " i stresc", " i streszcz", " i streść", " i streszcz ", " i stresc ", " podsumuj", " stresc", " streść", " streszcz"]:
        if token in raw:
            raw = raw.replace(token, "").strip()
    raw = re.sub(r"\s+(krotko|krótko|dlugo|długo)(\s+w\s+\d+\s+zdani(ach|a))?\s*$", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s+w\s+\d+\s+zdani(ach|a)\s*$", "", raw, flags=re.IGNORECASE)
    path = Path(os.path.expanduser(raw)).resolve()
    if not path.exists():
        return f"Nie znaleziono pliku: {path}"
    if path.is_dir():
        return f"To jest katalog, nie plik: {path}"
    try:
        size = path.stat().st_size
    except Exception:
        size = None
    try:
        if size is not None and size > MAX_BYTES:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_BYTES)
            record_file_event("read", str(path), f"cut:{MAX_BYTES}")
            return f"[UCIETO do {MAX_BYTES} bajtow]\n{content}"
        content = path.read_text(encoding="utf-8", errors="replace")
        record_file_event("read", str(path), f"bytes:{len(content)}")
        return content
    except Exception as e:
        return f"Blad odczytu pliku: {e}"
