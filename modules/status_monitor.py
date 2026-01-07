import json, os, subprocess
from datetime import datetime

from modules.model_paths import get_models_path

STATE_PATH = os.path.expanduser("~/lyra_agent/system_state.json")
MODELS_PATH = str(get_models_path())

def internet_ok():
    try:
        subprocess.check_call(["ping", "-c", "1", "8.8.8.8"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def tool_STATUS_MONITOR(arg, system_tool, log):
    """Wyświetla aktualny status Lyry i automatycznie aktualizuje tryb"""
    state = load_json(STATE_PATH, {})
    models = load_json(MODELS_PATH, {"active": "mistral", "available": {"mistral": "mistral:latest"}})

    current_mode = state.get("mode", "auto")
    active_model = models.get("active", "mistral")

    net = internet_ok()
    internet_status = "✅ jest" if net else "❌ brak"

    # automatyczna korekta trybu, jeśli w AUTO
    if current_mode == "auto":
        if not net:
            state["mode"] = "offline"
        else:
            state["mode"] = "auto"
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    # zaktualizowany tryb po auto-detekcji
    current_mode = state.get("mode", "auto")

    report = (
        f"[Lyra • Tryb: {current_mode.upper()} • Model: {active_model} • Internet: {internet_status}]\n"
        f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    log(report, "status_monitor.log")
    return report

