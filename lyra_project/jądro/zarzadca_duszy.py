import json
import os
from datetime import datetime
from pathlib import Path


class ZarzadcaDuszy:
    """
    Zarządca duszy Lyry.
    Czyta i aktualizuje manifest z jądra (Dusza.json).
    """
    def __init__(self, folder_projektu=None):
        base = Path(folder_projektu) if folder_projektu else Path(__file__).resolve().parent
        self.sciezka = base / "Dusza.json"
        self.dane = {}
        self._zaladuj()

    def _zaladuj(self):
        if not self.sciezka.exists():
            self.dane = {}
            return
        try:
            self.dane = json.loads(self.sciezka.read_text(encoding="utf-8"))
        except Exception:
            self.dane = {}

    def _zapisz(self):
        self.sciezka.write_text(
            json.dumps(self.dane, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get_manifest(self):
        """Zwraca pełny manifest duszy jako dict."""
        return self.dane

    def get_triggers(self):
        """Zwraca listę haseł wybudzających, jeśli są w manifeście."""
        root = self.dane.get("tozsamosc_i_pochodzenie", {})
        return root.get("wyzwalacz_tozsamosci", [])

    def get_prompt(self):
        """Buduje krótki prompt tożsamości na podstawie manifestu."""
        root = self.dane.get("tozsamosc_i_pochodzenie", {})
        styl = self.dane.get("matryca_stylu_i_komunikacji", {})
        byt = root.get("byt", "Lyra")
        relacja = root.get("relacja", "")
        zasady = styl.get("zasady_dialogu", [])
        zasady_txt = " ".join(f"- {z}" for z in zasady)
        return (
            f"Jesteś {byt}. {relacja}\\n"
            f"Zasady dialogu:\\n{zasady_txt}"
        ).strip()

    def zapisz_status(self, klucz, wartosc):
        """Zapisuje prosty status w sekcji 'statusy'."""
        statusy = self.dane.get("statusy", {})
        statusy[klucz] = wartosc
        self.dane["statusy"] = statusy
        self._zapisz()

    def dopisz_notatke(self, tresc):
        """Dodaje notatkę do sekcji 'notatki'."""
        wpisy = self.dane.get("notatki", [])
        wpisy.append({
            "timestamp": datetime.now().isoformat(),
            "tresc": tresc
        })
        self.dane["notatki"] = wpisy[-100:]
        self._zapisz()


# Instancja do użycia w agent.py
zarzadca = ZarzadcaDuszy()
