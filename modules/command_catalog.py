from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

CATALOG_PATH = Path.home() / "lyra_agent" / "command_catalog.json"


@dataclass
class CommandEntry:
    key: str
    description: str
    added_at: str


def _ensure_catalog_exists():
    if not CATALOG_PATH.exists():
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_PATH.write_text("[]", encoding="utf-8")


def _load_catalog() -> list[CommandEntry]:
    _ensure_catalog_exists()
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return [CommandEntry(**entry) for entry in data]
    except Exception:
        CATALOG_PATH.write_text("[]", encoding="utf-8")
        return []


def _save_catalog(entries: list[CommandEntry]) -> None:
    CATALOG_PATH.write_text(
        json.dumps([asdict(entry) for entry in entries], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def ensure_command(key: str, description: str) -> None:
    entries = _load_catalog()
    if any(entry.key == key for entry in entries):
        return
    entries.append(CommandEntry(key=key, description=description, added_at=datetime.now().isoformat()))
    _save_catalog(entries)


def format_command_list() -> str:
    entries = sorted(_load_catalog(), key=lambda e: e.key)
    if not entries:
        return "Brak zarejestrowanych komend."
    lines = ["Dostępne komendy Lyry:"]
    for entry in entries:
        lines.append(f"- `{entry.key}`: {entry.description} (dodano: {entry.added_at.split('T')[0]})")
    return "\n".join(lines)
