import json
from modules.model_paths import get_models_path, get_models_dir

MAP_FILE = get_models_path()
MODELS_DIR = get_models_dir()

# Opisy modeli – z czasem będziemy rozszerzać
MODEL_DESCRIPTIONS = {
    "bielik": "Polski model 11B, dobry do zadań ogólnych, tłumaczeń, rozmów i kodu.",
    "bielik-11b": "Mocna polska LLM, solidna w zadaniach ogólnych i technicznych.",

    "mistral": "Lekki, szybki model 7B. Idealny do pracy offline i szybkich odpowiedzi.",
    "mistral-nemo": "Mistral ulepszony przez NVIDIA – lepsze rozumienie techniczne.",
    "mixtral": "Model 8x7B – bardzo silny w zadaniach wymagających logiki i CoT.",

    "gemma": "Model Google – świetny w rozumowaniu i języku naturalnym (2B/9B/27B).",
    "granite": "IBM Granite – dobry w zadaniach technicznych i analizie danych.",

    "qwen": "Rodzina Qwen – bardzo mocne modele do kodu, logiki, python, reasoning.",
    "qwen2": "Nowa generacja Qwen – jeszcze lepsze rozumowanie.",
    "qwen2.5": "Topowy model w logice, analizie kodu i matematyce.",

    "aya": "Model wielojęzyczny – dobry w tłumaczeniach i dialogu.",
    "deepseek": "Model zoptymalizowany pod thinking i CoT.",

    "llama": "Meta Llama – świetne modele ogólne i do kodu.",
    "llama3": "Llama 3 – bardzo wysoka jakość odpowiedzi i rozumowania.",

    "phi": "Microsoft Phi – idealny do edukacji, matematyki i zadań logicznych.",

    "stable-code": "Model wyspecjalizowany do pisania i naprawy kodu.",
    "llava": "Model multimodalny – potrafi opisywać obrazy.",
}

def normalize(name):
    return (
        name.lower()
        .replace("_", "-")
        .replace(".", "-")
        .strip()
    )

def describe_model(name):
    key = normalize(name)
    for k, v in MODEL_DESCRIPTIONS.items():
        if k in key:
            return v
    return "Brak opisu – nowy lub niestandardowy model."

def tool_MODEL_DESCRIBE(arg, system, log):
    if not MAP_FILE.exists():
        return "❌ Brak pliku models.json – wykonaj: lyra aktualizuj modele"

    try:
        data = json.loads(MAP_FILE.read_text())
    except Exception as e:
        return f"❌ models.json uszkodzony: {e}"

    available = data.get("available", {})
    msg = "📘 Opisy dostępnych modeli:\n\n"

    if not available:
        msg += "(Brak wpisów w sekcji 'available')\n"
        return msg

    for name, path in available.items():
        desc = describe_model(name)
        msg += f"🔹 **{name}**\n"
        msg += f"    ↳ {path}\n"
        msg += f"    📝 {desc}\n\n"

    msg += "Użyj: lyra użyj <model>\n"
    return msg

