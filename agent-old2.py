#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

import requests
from openai import OpenAI

# ======= MODULE IMPORTS =======
from modules.app_tools import tool_APP_CONTROL
from modules.audio_tools import tool_AUDIO_DIAG, tool_AUDIO_FIX
from modules.net_tools import tool_NET_INFO, tool_NET_DIAG, tool_NET_FIX
from modules.system_tools import tool_SYSTEM_DIAG, tool_SYSTEM_FIX, tool_AUTO_OPTIMIZE
from modules.app_guard import tool_APP_GUARD
from modules.tmux_tools import tool_TMUX_SCREEN_DIAG
from modules.brain import query_brain
from modules.system_monitor import get_status, analyze_status
from modules.systeminfo import tool_SYSINFO
from modules.watchdog import tool_WATCHDOG
from modules.voice_input import tool_VOICE_INPUT
from modules.memory_ai import tool_MEMORY_ANALYZE
from modules.desktop_tools import tool_DESKTOP_DIAG, tool_DESKTOP_FIX
from modules.log_analyzer import tool_LOG_ANALYZE
from modules.model_manager import tool_MODEL_MANAGER
from modules.model_router import query_model
from modules.mode_manager import tool_MODE_MANAGER
from modules.status_monitor import tool_STATUS_MONITOR
from modules.switch_model import switch_model
from modules.model_switcher import tool_MODEL_SWITCHER
from modules.opisy_modelow import tool_MODEL_INFO
from modules.model_list import tool_MODEL_LIST
from modules.model_describe import tool_MODEL_DESCRIBE

# ======= PATHS AND CONFIG =======
BASE_DIR = Path(__file__).resolve().parent
CFG_PATH = BASE_DIR / "config.json"

if not CFG_PATH.exists():
    raise SystemExit(f"[Lyra] Brak {CFG_PATH}. Utwórz config.json.")

cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
if "user_name" not in cfg:
    cfg["user_name"] = "Tomek"
    CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# Logs directory
LOGS_DIR = BASE_DIR / cfg.get("logs_dir", "logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Memory and state paths
MEMORY_PATH = (BASE_DIR / cfg.get("memory_file", "agent_memory.json")).resolve()
STATE_PATH = (BASE_DIR / cfg.get("state_file", "agent_state.json")).resolve()
if not MEMORY_PATH.exists():
    MEMORY_PATH.write_text("[]", encoding="utf-8")
if not STATE_PATH.exists():
    STATE_PATH.write_text("{}", encoding="utf-8")

# Initialize OpenAI client if API key is provided
client = OpenAI(api_key=cfg.get("api_key", "")) if cfg.get("api_key") else None

# ======= LOGGING =======
def log(line: str, filename: str = "agent.log"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (LOGS_DIR / filename).open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")

# ======= MEMORY MANAGEMENT =======
def load_memory():
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_memory(entry: dict):
    mem = load_memory()
    mem.append(entry)
    MEMORY_PATH.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")

def remember(user: str, assistant: str):
    save_memory({
        "time": datetime.now().isoformat(),
        "type": "TEXT",
        "user": user,
        "assistant": assistant
    })

def remember_entry(entry_type: str, **fields):
    entry = {"time": datetime.now().isoformat(), "type": entry_type}
    entry.update(fields)
    save_memory(entry)

# ======= STATE MANAGEMENT =======
def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def update_state(patch: dict):
    st = load_state()
    st.update(patch)
    save_state(st)

# ======= SYSTEM TOOLS =======
def system_tool(cmd: str, timeout: int = 15) -> str:
    log(f"SYSTEM CMD: {cmd}", "system.log")
    # Optional sudo guard
    if "sudo" in cmd:
        print("⚠️ Polecenie wymaga sudo. Potwierdź: TAK")
        if input("> ").strip().lower() != "tak":
            return "❌ Anulowano przez użytkownika."

    try:
        return subprocess.check_output(
            cmd, shell=True,
            stderr=subprocess.STDOUT,
            timeout=timeout, text=True
        )
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] {cmd}"
    except subprocess.CalledProcessError as e:
        return e.output or "[ERROR]"

def tmux_capture(lines: int = 500) -> str:
    cmd = f"tmux capture-pane -pS -{lines}"
    return system_tool(cmd, timeout=3)

# ======= MODEL SELECTION =======
MODELS_FILE = cfg.get("models_file")

def pick_local_model(cfg):
    """Select a local model if configured and available."""
    wanted = (cfg.get("local_model") or "").lower()
    if not MODELS_FILE or not os.path.exists(MODELS_FILE):
        return None, None
    data = json.load(open(MODELS_FILE, "r", encoding="utf-8"))
    for name, path in data.get("available", {}).items():
        if wanted and wanted in name.lower():
            return name, path
    return None, None

local_name, local_path = pick_local_model(cfg)
if cfg.get("backend") == "local" and local_path:
    cfg["model"] = local_name
    cfg["local_model_path"] = local_path
else:
    cfg["backend"] = "openai"

def pick_openai_model(cfg: dict) -> str:
    """Return the name of the OpenAI model."""
    return cfg.get("openai_model") or cfg.get("model") or "gpt-5.1"

# ======= INTENT DETECTION =======
def detect_intent_local(user_prompt: str):
    prompt = user_prompt.lower().strip()
    # Brain test
    if "przetestuj połączenie z mózgiem" in prompt:
        return "BRAIN_TEST", ""
    # Network diagnostics
    if any(k in prompt for k in [
        "zdiagnozuj internet", "sprawdź internet",
        "internet nie działa", "problem z internetem",
        "diagnostyka sieci"
    ]):
        return "NET_DIAG", "auto"
    # Memory summary
    if any(k in prompt for k in [
        "co było", "co bylo", "co sie popsuło", "co się popsuło",
        "ostatnio", "dlaczego nie działało",
        "co naprawialiśmy", "jaki był problem", "jaki byl problem"
    ]):
        return "MEMORY_SUMMARY", ""
    return None, None

# ======= TOOL DISPATCH =======
def tool_dispatch(name: str, arg: str) -> str:
    name = (name or "").strip().upper()
    # Brain test
    if name == "BRAIN_TEST":
        out = query_brain("Czy połączenie z mózgiem działa?")
        return f"Myślenie lokalne działa, Tomek. Model Mistral jest aktywny.\n\n{out}"

    # Memory summary
    if name == "MEMORY_SUMMARY":
        mem = load_memory()
        if not mem:
            return "Brak zapisanej historii – pamięć jest pusta."
        last = mem[-20:]
        out = ["Ostatnio (z pamięci pliku):"]
        for m in last:
            t = m.get("type", "?")
            if t in ("TEXT", "LLM"):
                continue
            u = (m.get("user") or "").strip()
            a = (m.get("assistant") or m.get("output") or m.get("proposal") or "").strip()
            if not a:
                continue
            if "MEMORY_SUMMARY" in u or "MEMORY_SUMMARY" in a:
                continue
            out.append(f"- [{t}] {u} → {a[:160]}")
        return "\n".join(out) if len(out) > 1 else "Brak istotnych zdarzeń w pamięci (poza tekstówkami)."

    # Network diagnostics
    if name == "NET_DIAG":
        result = []
        result.append("=== IP ===")
        result.append(system_tool("ip a"))
        result.append("\n=== ROUTES ===")
        result.append(system_tool("ip r"))
        result.append("\n=== DNS ===")
        result.append(system_tool("cat /etc/resolv.conf"))
        result.append("\n=== PING GATEWAY ===")
        result.append(system_tool("ping -c 4 192.168.1.1"))
        result.append("\n=== PING INTERNET (1.1.1.1) ===")
        result.append(system_tool("ping -c 4 1.1.1.1"))
        result.append("\n=== PING DNS (8.8.8.8) ===")
        result.append(system_tool("ping -c 4 8.8.8.8"))
        result.append("\n=== DNS LOOKUP ===")
        result.append(system_tool("dig google.com +short || nslookup google.com || host google.com"))
        result.append("\n=== TRACE ===")
        result.append(system_tool("traceroute 8.8.8.8 || tracepath 8.8.8.8"))
        return "\n".join(result)

    # Desktop tool aliases
    if name in ["CINNAMON_DIAG", "GNOME_DIAG", "KDE_DIAG", "XFCE_DIAG"]:
        name = "DESKTOP_DIAG"
    if name in ["CINNAMON_FIX", "GNOME_FIX", "KDE_FIX", "XFCE_FIX"]:
        name = "DESKTOP_FIX"

    # Dispatch to modules
    if name == "AUDIO_DIAG": return tool_AUDIO_DIAG(arg, system_tool, log)
    if name == "AUDIO_FIX": return tool_AUDIO_FIX(arg, system_tool, log)
    if name == "SYSINFO": return tool_SYSINFO(arg, system_tool, log)
    if name == "NET_INFO": return tool_NET_INFO(arg, system_tool, log)
    if name == "NET_FIX": return tool_NET_FIX(arg, system_tool, log)
    if name == "SYSTEM_DIAG": return tool_SYSTEM_DIAG(arg, system_tool, log)
    if name == "SYSTEM_FIX": return tool_SYSTEM_FIX(arg, system_tool, log)
    if name == "AUTO_OPTIMIZE": return tool_AUTO_OPTIMIZE(arg, system_tool, log)
    if name == "DESKTOP_DIAG": return tool_DESKTOP_DIAG(arg, system_tool, log)
    if name == "DESKTOP_FIX": return tool_DESKTOP_FIX(arg, system_tool, log)
    if name == "TMUX_SCREEN_DIAG": return tool_TMUX_SCREEN_DIAG(arg, system_tool, log)
    if name == "STATUS_MONITOR": return tool_STATUS_MONITOR(arg, system_tool, log)
    if name == "WATCHDOG": return tool_WATCHDOG(arg, system_tool, log)
    if name == "VOICE_INPUT": return tool_VOICE_INPUT(arg, system_tool, log)
    if name == "MEMORY_ANALYZE": return tool_MEMORY_ANALYZE(arg, system_tool, log)
    if name == "LOG_ANALYZE": return tool_LOG_ANALYZE(arg, system_tool, log)
    if name == "MODEL_LIST": return tool_MODEL_LIST(arg, system_tool, log)
    if name == "MODEL_MANAGER": return tool_MODEL_MANAGER(arg, system_tool, log)
    if name in ["MODEL_SWITCHER", "PRZEŁĄCZNIK_MODELI"]: return switch_model(arg, log)
    if name == "MODEL_INFO": return tool_MODEL_INFO(arg, system_tool, log)
    if name == "MODEL_DESCRIBE": return tool_MODEL_DESCRIBE(arg, system_tool, log)
    if name == "APP_CONTROL": return tool_APP_CONTROL(arg, system_tool, log)
    if name == "APP_GUARD": return tool_APP_GUARD(arg, system_tool, log)

    return f"[Lyra-System] Nieznane narzędzie: {name}"

# ======= BANNER =======
def print_lyra_banner(cfg):
    mode = "LOCAL" if cfg.get("backend") == "local" else "ONLINE"
    model = cfg.get("model") if mode == "LOCAL" else pick_openai_model(cfg)
    net = "✅ jest" if cfg.get("internet", True) else "❌ brak"
    print(f"[Lyra] Żądany model lokalny: {cfg.get('local_model', '')}")
    if mode == "LOCAL":
        print(f"[Lyra MODEL] Wybrano model lokalny: {cfg.get('model')}")
        print(f"[Lyra MODEL] Ścieżka: {cfg.get('local_model_path')}")
    else:
        print(f"[Lyra MODEL] Backend zdalny (OpenAI)")
    print(f"[Lyra • Tryb: {mode} • Model: {model} • Internet: {net}]")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ======= MAIN RUN LOOP =======
def run_once(user_prompt: str):
    prompt_lower = user_prompt.lower()

    # Test brain connection
    if "przetestuj połączenie z mózgiem" in prompt_lower:
        out = query_brain("Czy połączenie z mózgiem działa?")
        print(f"Myślenie lokalne działa, Tomek. Model Mistral jest aktywny.\n\n{out}")
        remember(user_prompt, out)
        return

    # Change model command
    if prompt_lower.startswith("lyra zmień model na"):
        name = user_prompt.split("na", 1)[1].strip()
        cfg["local_model"] = name
        cfg["model"] = name
        cfg["backend"] = "local"
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f"✅ Zmieniono model lokalny na: {name}")
        print_lyra_banner(cfg)
        return

    # Handle direct system commands
    if user_prompt.lower().startswith("system:"):
        cmd = user_prompt.split(":", 1)[1].strip()
        out = system_tool(cmd)
        print(out)
        update_state({
            "last_system_cmd": cmd,
            "last_system_output": out[:4000]
        })
        remember_entry("SYSTEM", user=user_prompt, command=cmd, output=out[:4000])
        return

    # Handle direct tool commands
    if user_prompt.startswith("TOOL:"):
        rest = user_prompt.split(":", 1)[1].strip()
        tool_name, arg = (rest.split("|", 1) + [""])[:2]
        tool_name, arg = tool_name.strip(), arg.strip()
        out = tool_dispatch(tool_name, arg)
        print(out)
        remember_entry("TOOL", user=user_prompt, tool=tool_name, args=arg, output=out[:4000])
        update_state({
            "last_tool": tool_name,
            "last_tool_arg": arg,
            "last_tool_output": out[:4000]
        })
        return

    # Quick kernel queries
    if prompt_lower in ["sprawdź kernel", "jaki kernel", "kernel", "wersja kernela"]:
        out = system_tool("uname -r")
        print(out)
        remember_entry("SYSTEM", user=user_prompt, command="uname -r", output=out[:4000])
        return

    # Local intents (network diag, memory summary, brain test)
    tool, arg = detect_intent_local(user_prompt)
    if tool:
        out = tool_dispatch(tool, arg)
        print(out)
        remember_entry("TOOL", user=user_prompt, tool=tool, args=arg, output=out[:4000])
        if tool != "BRAIN_TEST":
            update_state({
                "last_tool": tool,
                "last_tool_arg": arg,
                "last_tool_output": out[:4000]
            })
        return

    # Status or monitor commands
    if "monitor" in prompt_lower or "status" in prompt_lower:
        s = get_status()
        report = analyze_status(s)
        print(report)
        remember(user_prompt, report)
        return

    # Snapshot system state
    update_state({
        "last_seen": datetime.now().isoformat(),
        "kernel": system_tool("uname -a", timeout=3)[:300],
        "session": system_tool("echo $XDG_SESSION_TYPE", timeout=3).strip(),
        "os": system_tool("cat /etc/os-release", timeout=3)[:500],
    })
    st = load_state()

    # Show banner
    print_lyra_banner(cfg)

    # Build system message and context
    system_state_block = (
        f"last_seen: {st.get('last_seen','')}\n"
        f"kernel: {st.get('kernel','')}\n"
        f"os:\n{st.get('os','')}\n"
        f"last_tool: {st.get('last_tool','')} | {st.get('last_tool_arg','')}\n"
        f"last_tool_output:\n{st.get('last_tool_output','')}\n"
        f"last_system_cmd: {st.get('last_system_cmd','')}\n"
        f"last_system_output:\n{st.get('last_system_output','')}\n"
    )

    system_message = {
        "role": "system",
        "content": (
            "Jesteś techniczną asystentką Tomka w terminalu Linux. Masz na imię LYRA. "
            "Użytkownik ma na imię Tomek. Odpowiadaj po polsku, konkretnie.\n"
            "Tryb: agresywny (3) — działaj, nie filozofuj.\n\n"
            "Masz TRZY typy odpowiedzi:\n\n"
            "1) Zwykła odpowiedź tekstowa po polsku – wyjaśnienia, analizy, podsumowania.\n\n"
            "2) Odpowiedź narzędziowa:\n"
            "   - SYSTEM: <komenda bash>\n"
            "   - TOOL: <NAZWA_NARZĘDZIA> | <argument>\n\n"
            "Dostępne narzędzia:\n"
            "APP_CONTROL -> uruchamianie aplikacji i stron\n"
            "APP_GUARD   -> strażnik aplikacji\n"
            "AUDIO_DIAG  -> diagnostyka audio\n"
            "AUDIO_FIX   -> naprawa audio\n"
            "NET_INFO    -> ip a && ip r\n"
            "NET_DIAG    -> diagnostyka sieci\n"
            "NET_FIX     -> naprawa sieci\n"
            "SYSTEM_DIAG -> diagnostyka systemu\n"
            "SYSTEM_FIX  -> naprawy systemowe\n"
            "AUTO_OPTIMIZE -> lekkie, odwracalne optymalizacje\n\n"
            "3) PROPOSE_TOOL:\n"
            "   NAME:\n"
            "   DESCRIPTION:\n"
            "   CODE:\n\n"
            "ZASADY:\n"
            "- SYSTEM / TOOL → ZERO dodatkowego tekstu\n"
            "- ryzykowne akcje tylko jako PROPOSE_TOOL\n"
            "- *_FIX i AUTO_OPTIMIZE tylko jeśli są odwracalne\n\n"
            "- Nie zgaduj imion\n"
            "- Korzystaj z pamięci rozmowy\n"
            "- Nie zmieniaj swojej tożsamości\n\n"
            "ZASADA AUTOMATYCZNEJ DECYZJI:\n"
            "- Jeśli polecenie dotyczy diagnozy, użyj *_DIAG.\n"
            "- Jeśli dotyczy naprawy, użyj *_FIX.\n"
            "- Jeśli dotyczy informacji, użyj *_INFO.\n"
            "- Jeśli dotyczy uruchomienia programu lub strony, użyj: TOOL: APP_CONTROL | <opis>.\n"
            "- Jeśli dotyczy pilnowania aplikacji, użyj: TOOL: APP_GUARD | <opis>.\n"
            "- Jeśli dotyczy plików/katalogów/archiwów (find/cp/mv/grep/tar/unzip), użyj: SYSTEM: <komenda>.\n"
            "- Jeśli można wykonać od razu, nie opisuj – zwróć tylko SYSTEM: albo TOOL:.\n"
            "- Jeśli nie jest oczywiste, zapytaj krótko o doprecyzowanie.\n"
            "\n=== SYSTEM STATE (DO ZAPAMIĘTANIA) ===\n"
            f"session: {st.get('session','')}\n"
            f"kernel: {st.get('kernel','')}\n"
            f"os:\n{st.get('os','')}\n"
            f"last_tool: {st.get('last_tool','')} {st.get('last_tool_arg','')}\n"
            f"last_tool_output:\n{st.get('last_tool_output','')}\n"
            f"last_system_cmd: {st.get('last_system_cmd','')}\n"
            f"last_system_output:\n{st.get('last_system_output','')}\n"
            f"=== END STATE ===\n"
            f"{system_state_block}"
        )
    }

    # Build context from last 5 memory entries
    mem = load_memory()[-5:]
    context_lines = []
    for m in mem:
        if m.get("type") == "TEXT":
            context_lines.append(f"User: {m.get('user','')}")
            context_lines.append(f"Lyra: {m.get('assistant','')}")
    context = "\n".join(context_lines)

    # Final prompt with context
    prompt = (
        f"Jesteś LYRA.\nRozmawiasz z Tomkiem.\nZnasz jego imię: Tomek.\n\n"
        f"KONTEKST ROZMOWY:\n{context}\n\n"
        f"AKTUALNE PYTANIE:\n{user_prompt}"
    )

    messages = [system_message, {"role": "user", "content": prompt}]

    # Choose backend and get response
    backend = cfg.get("backend", "local")
    msg = ""
    mode = ""

    if backend == "local":
        try:
            ollama_model = cfg.get("ollama_model") or cfg.get("model") or "mistral"
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": ollama_model, "prompt": prompt},
                timeout=60,
                stream=True
            )
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    msg += chunk.get("response", "")
            mode = f"local:{ollama_model}"
        except Exception as e:
            msg = f"[Błąd lokalnego modelu] {e}"
            mode = "local:error"
    else:
        # OpenAI backend
        if not client:
            msg = "[Błąd] Brak api_key w config.json."
            mode = "openai:error"
        else:
            try:
                openai_model = pick_openai_model(cfg)
                msg, mode = query_model(
                    user_prompt,
                    openai_model,
                    openai_model,
                    client,
                    messages
                )
            except Exception as e:
                msg = f"[Błąd OpenAI] {e}"
                mode = "openai:error"

    msg = msg.strip()

    # Handle empty or fallback
    if not msg:
        log("LLM EMPTY → fallback to brain", "agent.log")
        out = query_brain(prompt)
        print(out)
        remember(user_prompt, out)
        return

    # System or tool calls from model
    if msg.startswith("SYSTEM:"):
        cmd = msg[len("SYSTEM:"):].strip()
        out = system_tool(cmd)
        print(out)
        remember_entry("SYSTEM", user=user_prompt, command=cmd, output=out[:4000])
        update_state({"last_system_cmd": cmd, "last_system_output": out[:4000]})
        return

    if msg.startswith("TOOL:"):
        rest = msg[len("TOOL:"):].strip()
        tool_name, arg = (rest.split("|", 1) + [""])[:2]
        tool_name, arg = tool_name.strip(), arg.strip()
        out = tool_dispatch(tool_name, arg)
        print(out)
        remember_entry("TOOL", user=user_prompt, tool=tool_name, args=arg, output=out[:4000])
        update_state({
            "last_tool": tool_name,
            "last_tool_arg": arg,
            "last_tool_output": out[:4000]
        })
        return

    if msg.startswith("PROPOSE_TOOL:"):
        print(msg)
        remember_entry("PROPOSE_TOOL", user=user_prompt, proposal=msg[:4000])
        return

    # Normal text response
    print(msg)
    remember(user_prompt, msg)
    log(f"MODEL USED: {mode}", "agent.log")

# ======= ENTRY POINT =======
if __name__ == "__main__":
    # Command-line argument mode
    if len(sys.argv) > 1:
        run_once(" ".join(sys.argv[1:]))
    else:
        print("Lyra online. 'exit' aby wyjść.")
        while True:
            try:
                user_input = input("Ty > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break
            run_once(user_input)

