from pathlib import Path
import json
from datetime import datetime

# =========================================================
# MEMORY STORE – trwała pamięć Lyry
# =========================================================

MEMORY_PATH = Path.home() / "lyra_agent" / "memory.json"

class MemoryStore:
    def __init__(self, path: Path):
        self.path = path
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            # Jeśli plik uszkodzony – reset z zachowaniem bezpieczeństwa
            backup = self.path.with_suffix(".corrupted.json")
            self.path.rename(backup)
            self.path.write_text("[]", encoding="utf-8")
            return []

    def append(self, entry: dict):
        mem = self.load()
        mem.append(entry)
        self.path.write_text(
            json.dumps(mem, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def remember_text(self, user, assistant):
        self.append({
            "time": datetime.now().isoformat(),
            "type": "TEXT",
            "user": user,
            "assistant": assistant
        })


# =========================================================
# GLOBALNY OBIEKT I API DLA agent.py
# =========================================================

store = MemoryStore(MEMORY_PATH)


def remember(user_text: str, assistant_text: str):
    """
    Funkcja eksportowana, wymagana przez agent.py.
    Nic nie usuwamy — to tylko cienka nakładka na MemoryStore.
    """
    store.remember_text(user_text, assistant_text)


def load_memory():
    """
    Opcjonalne API: agent.py może tego użyć do streszczania pamięci.
    """
    return store.load()

