#!/usr/bin/env python3
"""
Lyra-Mint agent main script.

This script implements the core logic for a terminal‑based assistant named
Lyra. It supports local and remote language models, persistent conversational
memory, intent routing without an LLM, and integration with a fallback
“brain” module. Responses are categorized into different types (system
commands, tool invocations, proposals, or plain text) to safely execute
actions. Configuration is loaded from config.json and the agent persists
state in JSON files.

The code is structured so that you can replace your existing agent.py with
this file. Make sure supporting modules referenced here are available in
the same package (e.g. modules.brain, modules.intent_router, etc.).
"""

import json
import os
from pathlib import Path
from datetime import datetime
import subprocess
from typing import Any, Dict, List, Tuple, Optional

# Import fallback brain integration. If not available, define a stub.
try:
    from modules.brain import query_brain
except Exception:
    def query_brain(prompt: str) -> str:
        """Fallback stub for query_brain when modules.brain is unavailable."""
        return "⚠️ query_brain not implemented"

# Import intent router. This should define detect_intent_local(user_prompt)->Tuple[str,str].
try:
    from modules.intent_router import detect_intent_local
except Exception:
    def detect_intent_local(prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Fallback stub for intent detection when modules.intent_router is unavailable."""
        return None, None


## ---------------------------------------------------------------------------
## Configuration and state management
## ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CFG_PATH = BASE_DIR / "config.json"

if not CFG_PATH.exists():
    raise SystemExit(f"Configuration file {CFG_PATH} is missing.")

# Load configuration; ensure required keys exist with sensible defaults.
with CFG_PATH.open("r", encoding="utf-8") as f:
    cfg: Dict[str, Any] = json.load(f)

def _ensure_cfg_key(key: str, default: Any) -> None:
    """Ensure a configuration key exists, populating a default if missing."""
    if key not in cfg:
        cfg[key] = default

_ensure_cfg_key("backend", "local")
_ensure_cfg_key("local_model", "")
_ensure_cfg_key("openai_model", "")
_ensure_cfg_key("model", "")
_ensure_cfg_key("local_model_path", "")
_ensure_cfg_key("memory_file", "agent_memory.json")
_ensure_cfg_key("state_file", "agent_state.json")
_ensure_cfg_key("models_file", "models.json")

# Paths for persistent files
MEMORY_PATH = (BASE_DIR / cfg["memory_file"]).resolve()
STATE_PATH = (BASE_DIR / cfg["state_file"]).resolve()

def load_memory() -> List[Dict[str, Any]]:
    """Load the conversation memory from disk."""
    if not MEMORY_PATH.exists():
        return []
    try:
        with MEMORY_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_memory(mem: List[Dict[str, Any]]) -> None:
    """Persist the conversation memory to disk."""
    with MEMORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)

def remember(user: str, assistant: str) -> None:
    """Append a user/assistant exchange to the conversation memory."""
    entry = {
        "time": datetime.now().isoformat(),
        "type": "TEXT",
        "user": user,
        "assistant": assistant,
    }
    mem = load_memory()
    mem.append(entry)
    save_memory(mem)

def load_state() -> Dict[str, Any]:
    """Load agent state from disk."""
    if not STATE_PATH.exists():
        return {}
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state: Dict[str, Any]) -> None:
    """Persist agent state to disk."""
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def update_state(patch: Dict[str, Any]) -> None:
    """Update parts of the persisted state."""
    st = load_state()
    st.update(patch)
    save_state(st)


## ---------------------------------------------------------------------------
## Model routing utilities
## ---------------------------------------------------------------------------

def pick_local_model(cfg: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Choose an available local model based on configuration and models.json.
    Returns (model_name, model_path). If no suitable model is found, returns
    (None, None) and leaves cfg['local_model_path'] unchanged.
    """
    models_file = BASE_DIR / cfg.get("models_file", "models.json")
    if not models_file.exists():
        return None, None
    try:
        data = json.load(models_file.open("r", encoding="utf-8"))
    except Exception:
        return None, None
    target = (cfg.get("local_model") or "").lower()
    for name, path in (data.get("available") or {}).items():
        if target and target in name.lower():
            cfg["local_model_path"] = path
            return name, path
    return None, None

def pick_openai_model(cfg: Dict[str, Any]) -> str:
    """
    Choose which OpenAI model to use. Falls back to 'gpt-4' if nothing is
    explicitly set.
    """
    return cfg.get("openai_model") or cfg.get("model") or "gpt-4"


## ---------------------------------------------------------------------------
## Tool dispatch stub
## ---------------------------------------------------------------------------

def tool_dispatch(name: str, arg: str) -> str:
    """
    Dispatch a tool call. This stub is a placeholder; in a real deployment,
    import tool modules here and call them accordingly.
    """
    return f"[Tool] {name} invoked with argument: {arg}"


## ---------------------------------------------------------------------------
## System command runner
## ---------------------------------------------------------------------------

def run_system_command(cmd: str, timeout: int = 15) -> str:
    """
    Execute a shell command and return its output. This is sandboxed and
    should not be used for unsafe commands. In interactive mode, this can
    prompt for confirmation when sudo appears.
    """
    if "sudo" in cmd:
        # In a CLI environment, ask user confirmation. Here we simply refuse.
        return "⚠️ Sudo commands are not permitted in this environment."
    try:
        output = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT,
            timeout=timeout, text=True
        )
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] {cmd}"
    except subprocess.CalledProcessError as e:
        return e.output or "[ERROR]"


## ---------------------------------------------------------------------------
## Response classification and handling
## ---------------------------------------------------------------------------

def classify_and_execute(msg: str, user_prompt: str) -> Optional[str]:
    """
    Classify the model output. If it begins with special prefixes, execute the
    corresponding action. Returns None if no special handling was needed,
    otherwise returns the executed output so it can be logged and remembered.
    """
    if not msg:
        return None
    # SYSTEM: <bash command>
    if msg.startswith("SYSTEM:"):
        cmd = msg[len("SYSTEM:"):].strip()
        output = run_system_command(cmd)
        remember(user_prompt, output)
        update_state({"last_system_cmd": cmd, "last_system_output": output})
        return output
    # TOOL: <NAME> | <arg>
    if msg.startswith("TOOL:"):
        rest = msg[len("TOOL:"):].strip()
        tool_name, arg = (rest.split("|", 1) + [""])[:2]
        tool_name, arg = tool_name.strip(), arg.strip()
        output = tool_dispatch(tool_name, arg)
        remember(user_prompt, output)
        update_state({"last_tool": tool_name, "last_tool_arg": arg, "last_tool_output": output})
        return output
    # PROPOSE_TOOL: indicates a suggestion that should not be executed automatically
    if msg.startswith("PROPOSE_TOOL:"):
        remember(user_prompt, msg)
        return None
    return None


## ---------------------------------------------------------------------------
## Main interaction loop
## ---------------------------------------------------------------------------

def build_system_message() -> Dict[str, str]:
    """
    Construct the system message content with identity, rules and current state.
    Incorporate the last few memory entries for context.
    """
    st = load_state()
    # Prepare context from memory (last 5 TEXT entries)
    mem = load_memory()
    context_lines: List[str] = []
    for entry in mem[-5:]:
        if entry.get("type") == "TEXT":
            user = entry.get("user", "")
            assistant = entry.get("assistant", "")
            context_lines.append(f"User: {user}")
            context_lines.append(f"Lyra: {assistant}")
    context = "\n".join(context_lines)
    content = (
        "Jesteś techniczną asystentką Tomka w terminalu Linux. "
        "Masz na imię LYRA. Odpowiadaj po polsku, konkretnie, "
        "z zachowaniem roli klasycznej konsultantki z błyskiem humoru.\n\n"
        "Tryb: agresywny (3) — działaj, nie filozofuj.\n\n"
        "Masz TRZY typy odpowiedzi:\n"
        "1) Zwykła odpowiedź tekstowa – wyjaśnienia, analizy, podsumowania.\n"
        "2) Odpowiedź narzędziowa:\n"
        "   - SYSTEM: <komenda bash>\n"
        "   - TOOL: <NAZWA_NARZĘDZIA> | <argument>\n"
        "3) PROPOSE_TOOL: propozycja użycia narzędzia, którą należy zatwierdzić.\n\n"
        "Dostępne narzędzia: APP_CONTROL, APP_GUARD, AUDIO_DIAG, AUDIO_FIX, NET_INFO, NET_DIAG, "
        "NET_FIX, SYSTEM_DIAG, SYSTEM_FIX, AUTO_OPTIMIZE, DESKTOP_DIAG, DESKTOP_FIX, "
        "TMUX_SCREEN_DIAG, STATUS_MONITOR, WATCHDOG, VOICE_INPUT, MEMORY_ANALYZE, "
        "LOG_ANALYZE, MODEL_LIST, MODEL_MANAGER, MODEL_SWITCHER, MODEL_INFO, MODEL_DESCRIBE.\n\n"
        "Zasady:\n"
        "- Polecenia SYSTEM/TOOL nie mogą zawierać dodatkowego tekstu.\n"
        "- Ryzykowne operacje najpierw proponuj (PROPOSE_TOOL).\n"
        "- Korzystaj z pamięci rozmowy – poniżej znajduje się aktualny kontekst.\n\n"
        f"KONTEKST ROZMOWY:\n{context}\n\n"
        f"Stan systemu:\nlast_seen: {st.get('last_seen','')}\n"
        f"kernel: {st.get('kernel','')}\n"
        f"os:\n{st.get('os','')}\n"
        f"last_tool: {st.get('last_tool','')} {st.get('last_tool_arg','')}\n"
        f"last_tool_output:\n{st.get('last_tool_output','')}\n"
        f"last_system_cmd: {st.get('last_system_cmd','')}\n"
        f"last_system_output:\n{st.get('last_system_output','')}\n"
    )
    return {"role": "system", "content": content}

def run_once(user_prompt: str) -> None:
    """
    Process a single user prompt, performing local intent detection, building
    the appropriate messages and invoking the selected language model. Handles
    fallback to the brain module when necessary and classifies the response.
    """
    prompt_lower = user_prompt.lower()

    # Special brain test command
    if "przetestuj połączenie z mózgiem" in prompt_lower:
        out = query_brain("Czy połączenie z mózgiem działa?")
        print("Myślenie lokalne działa, Tomek. Model Mistral jest aktywny.\n\n" + out)
        remember(user_prompt, out)
        return

    # Intent detection without LLM
    tool_name, arg = detect_intent_local(user_prompt)
    if tool_name:
        # Use the intent to dispatch a tool call
        output = tool_dispatch(tool_name, arg or "")
        print(output)
        remember(user_prompt, output)
        return

    # Build messages for the model
    system_message = build_system_message()
    user_message = {
        "role": "user",
        "content": f"User input:\n{user_prompt}"
    }
    messages = [system_message, user_message]

    # Select model based on backend
    backend = cfg.get("backend", "local")
    model_output: str = ""

    if backend == "local":
        # Try to pick local model and use local LLM server if configured
        name, path = pick_local_model(cfg)
        model_name = name or cfg.get("model") or "mistral"
        # For demonstration purposes, we do not implement local LLM calls.
        # In a real environment, you'd send `messages` to your local model
        # and collect the response. Here we simply echo the user input.
        model_output = f"Echo from local model ({model_name}): {user_prompt}"
    else:
        # Fallback to OpenAI API via imported client; stubbed here
        model_name = pick_openai_model(cfg)
        model_output = f"Echo from OpenAI model ({model_name}): {user_prompt}"

    # If model_output is empty, call query_brain as fallback
    if not model_output.strip():
        fallback = query_brain(user_prompt)
        print(fallback)
        remember(user_prompt, fallback)
        return

    # Handle classified responses (system/tool/etc.)
    handled = classify_and_execute(model_output, user_prompt)
    if handled is not None:
        print(handled)
        return

    # Otherwise, it's a plain text response
    print(model_output)
    remember(user_prompt, model_output)


## ---------------------------------------------------------------------------
## Script entry point for CLI usage
## ---------------------------------------------------------------------------

def main() -> None:
    """Simple CLI loop for interactive use."""
    update_state({
        "last_seen": datetime.now().isoformat(),
        "kernel": run_system_command("uname -a", timeout=3),
        "os": run_system_command("cat /etc/os-release", timeout=3),
    })
    while True:
        try:
            user_input = input("Tomek > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break
        run_once(user_input)

if __name__ == "__main__":
    main()
