import json, os
from pathlib import Path

from modules.model_paths import get_models_path

# Definicje ścieżek (zgodnie z Twoim życzeniem)
BAZOWY_KATALOG = Path(__file__).resolve().parent.parent
PLIK_MODELE = get_models_path()

def wczytaj_konfiguracje_modeli():
    """Wczytuje listę dostępnych modeli i aktualnie aktywny model."""
    if not PLIK_MODELE.exists():
        # Domyślna konfiguracja, jeśli plik nie istnieje
        domyslna = {
            "active": "mistral",
            "available": {
                "mistral": "mistral:latest",
                "aya": "aya:latest",
                "bielik": "bielik:latest"
            }
        }
        with open(PLIK_MODELE, 'w', encoding='utf-8') as f:
            json.dump(domyslna, f, indent=4)
        return domyslna
    
    with open(PLIK_MODELE, 'r', encoding='utf-8') as f:
        return json.load(f)

def przelacz_model(nowa_nazwa):
    """Przełącza aktywny model na wskazany przez użytkownika."""
    config = wczytaj_konfiguracje_modeli()
    
    if nowa_nazwa in config["available"]:
        config["active"] = nowa_nazwa
        with open(PLIK_MODELE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True, nowa_nazwa
    else:
        return False, list(config["available"].keys())

# --- PRZYKŁAD UŻYCIA W AGENCIE ---
# nazwa = "aya"
# sukces, wynik = przelacz_model(nazwa)
# if sukces:
#     print(f"Model zmieniony na: {wynik}")
# else:
#     print(f"Błąd! Nie znam modelu {nazwa}. Dostępne: {wynik}")



