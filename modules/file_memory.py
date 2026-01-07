import json
import os
from datetime import datetime
from pathlib import Path

MEMORY_PATH = Path.home() / "lyra_agent" / "file_memory.json"


def _load_memory():
    if not MEMORY_PATH.exists():
        return []
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def record_file_event(action: str, path: str, detail: str = ""):
    try:
        items = _load_memory()
        items.append(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "action": action,
                "path": path,
                "detail": detail,
            }
        )
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=True), encoding="utf-8")
    except Exception:
        pass
