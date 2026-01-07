import json
import os

STATE_PATH = os.path.expanduser("~/lyra_agent/system_state.json")


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def set_mode(arg):
    """
    Zarządza trybem pracy Lyry: offline / online / auto.
    Zapisuje wybór w system_state.json
    """
    state = load_state()
    arg = (arg or "").strip().lower()

    if arg in ["auto", "online", "offline"]:
        state["mode"] = arg
        save_state(state)
        return f"🔁 Ustawiono tryb: {arg.upper()}"

    current = state.get("mode", "auto")
    return f"📡 Aktualny tryb pracy: {current.upper()}\nDostępne tryby: auto, online, offline"


def tool_MODE_MANAGER(arg, system_tool=None, log=None):
    return set_mode(arg)
