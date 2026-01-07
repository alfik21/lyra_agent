import json
import os

from modules.model_paths import get_models_path

MODELS_JSON = str(get_models_path())
CONFIG_JSON = "/home/tomek/lyra_agent/config.json"

def switch_model(name, log):
    name = name.lower().replace(" ", "")
    
    if not os.path.exists(MODELS_JSON):
        return "❌ Nie znaleziono models.json – uruchom: lyra aktualizuj modele"

    with open(MODELS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    models = data.get("available", {})

    # wyszukiwanie przybliżone
    match = None
    for model in models:
        if all(x in model.lower() for x in name.split()):
            match = model
            break

    if not match:
        return f"❌ Nie znaleziono modelu pasującego do: {name}"

    path = models[match]

    # zapisz do config.json
    with open(CONFIG_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["local_model"] = match

    with open(CONFIG_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    log(f"[MODEL SWITCH] Ustawiono model: {match}")

    return f"""🔁 Przełączono model lokalny
📌 Model: {match}
📂 Plik: {path}
⚙️ Użyj teraz: lyra test "napisz kod"
"""

