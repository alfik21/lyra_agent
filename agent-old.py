import json, sys, subprocess
import os

from pathlib import Path
from datetime import datetime
from openai import OpenAI
import requests


from modules.app_tools import tool_APP_CONTROL
from modules.audio_tools import tool_AUDIO_DIAG, tool_AUDIO_FIX
from modules.net_tools import tool_NET_INFO, tool_NET_DIAG, tool_NET_FIX
from modules.system_tools import tool_SYSTEM_DIAG, tool_SYSTEM_FIX, tool_AUTO_OPTIMIZE
from modules.app_guard import tool_APP_GUARD
from modules.tmux_tools import tool_TMUX_SCREEN_DIAG
from modules.brain import query_brain
from modules.intent_router import detect_intent
from modules.system_monitor import get_status, analyze_status
from modules.systeminfo import tool_SYSINFO
from modules.net_tools import tool_NET_INFO, tool_NET_DIAG, tool_NET_FIX
from modules.watchdog import tool_WATCHDOG
from modules.tmux_tools import tool_TMUX_SCREEN_DIAG
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

















# =========================================================
# CONFIG / PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

cfg = json.load(open(BASE_DIR / "config.json"))
client = OpenAI(api_key=cfg["api_key"])

# =========================================================
# LOGGING — musi być zdefiniowane WCZEŚNIE!
# =========================================================

LOGS_DIR = BASE_DIR / cfg.get("logs_dir", "logs")
LOGS_DIR.mkdir(exist_ok=True)

def log(line: str, filename: str = "agent.log"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (LOGS_DIR / filename).open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")
        
memory_path = BASE_DIR / cfg.get("memory_file", "agent_memory.json")
state_path  = BASE_DIR / cfg.get("state_file", "agent_state.json")

if not memory_path.exists():
    memory_path.write_text("[]", encoding="utf-8")

if not state_path.exists():
    state_path.write_text("{}", encoding="utf-8")



# =========================================================
# LOGGING
# =========================================================

def log(line: str, filename: str = "agent.log"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (LOGS_DIR / filename).open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")

    
# ------------------------------------------
# 2. Jeśli STILL backend = openai → mapowanie uproszczone
# ------------------------------------------
# =========================================================
# BACKEND + MODEL SETUP — NOWA, CZYSTA LOGIKA
# =========================================================

local_model_raw = cfg.get("local_model", "").strip()
local_model = local_model_raw.lower().replace(" ", "")
models_file = cfg.get("models_file")

#cfg["backend"] = "openai"       # domyślny backend
#cfg["local_model_path"] = None  # ścieżka do lokalnego modelu
#cfg["model"] = cfg.get("model", "gpt-5.1")

print(f"[Lyra] Żądany model lokalny: {local_model_raw}")

# -----------------------------------------------
# 1. Jeśli mamy models.json → próbuj dopasować model
# -----------------------------------------------
if models_file and os.path.exists(models_file):
    try:
        with open(models_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        available = data.get("available", {})
        selected_model = None
        selected_path = None

        # dopasowanie "przybliżone"
        for name, path in available.items():
            cleaned = name.lower().replace(" ", "")
            if local_model and local_model in cleaned:
                selected_model = name
                selected_path = path
                break

        if selected_path:
            cfg["backend"] = "local"
            cfg["model"] = selected_model
            cfg["local_model_path"] = selected_path
            print(f"[Lyra MODEL] Wybrano model lokalny: {selected_model}")
            print(f"[Lyra MODEL] Ścieżka: {selected_path}")
        else:
            print(f"[Lyra MODEL] Brak modelu '{local_model_raw}' w models.json → używam OpenAI")

    except Exception as e:
        print(f"[Lyra MODEL ERROR] Nie można wczytać models.json: {e}")

# zapisujemy
with open(BASE_DIR / "config.json", "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)


# Wyświetlenie statusu Lyry przy starcie
from modules.status_monitor import tool_STATUS_MONITOR


def tmux_capture(lines=200):
    cmd = f"tmux capture-pane -p -S -{lines} -t lyra"
    return system_tool(cmd)


# =========================================================
# MEMORY (rozmowa)
# =========================================================

def load_memory():
    try:
        return json.loads(memory_path.read_text(encoding="utf-8"))
    except Exception:
        return []

def remember(user: str, assistant: str):
    mem = load_memory()
    mem.append({
        "time": datetime.now().isoformat(),
        "user": user,
        "assistant": assistant
    })
    memory_path.write_text(
        json.dumps(mem, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

# =========================================================
# STATE (stan systemu)
# =========================================================

def load_state() -> dict:
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_state(state: dict):
    state_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def update_state(patch: dict):
    st = load_state()
    st.update(patch)
    save_state(st)
    
def tmux_capture(lines: int = 500) -> str:
    """
    Zrzut aktualnego ekranu tmuxa (ostatnie N linii).
    """
    cmd = f"tmux capture-pane -pS -{lines}"
    return system_tool(cmd, timeout=3)


# =========================================================
# SYSTEM TOOL
# =========================================================

def system_tool(cmd: str, timeout: int = 15) -> str:
    log(f"SYSTEM CMD: {cmd}", "system.log")
    try:
        return subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True
        )
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] {cmd}"
    except subprocess.CalledProcessError as e:
        return e.output or "[ERROR]"

# =========================================================
# TOOL DISPATCH
# =========================================================

def tool_dispatch(name: str, arg: str) -> str:
    name = name.strip().upper()
    
# aliasy dla rozpoznawanych narzędzi
    if name in ["CINNAMON_DIAG", "GNOME_DIAG", "KDE_DIAG", "XFCE_DIAG"]:
        name = "DESKTOP_DIAG"
    if name in ["CINNAMON_FIX", "GNOME_FIX", "KDE_FIX", "XFCE_FIX"]:
        name = "DESKTOP_FIX"


    if name == "AUDIO_DIAG":
        return tool_AUDIO_DIAG(arg, system_tool, log)
    if name == "AUDIO_FIX":
        return tool_AUDIO_FIX(arg, system_tool, log)
    if name == "SYSINFO":
        return tool_SYSINFO(arg, system_tool, log)
    if name == "NET_INFO":
        return tool_NET_INFO(arg, system_tool, log)
    if name == "NET_DIAG":
        return tool_NET_DIAG(arg, system_tool, log)
    if name == "NET_FIX":
        return tool_NET_FIX(arg, system_tool, log)
    if name == "TMUX_SCREEN_DIAG":
        return tool_TMUX_SCREEN_DIAG(arg, system_tool, log)
    if name == "DESKTOP_DIAG":
        return tool_DESKTOP_DIAG(arg, system_tool, log)
    if name == "DESKTOP_FIX":
        return tool_DESKTOP_FIX(arg, system_tool, log)
    if name == "LOG_ANALYZE":
        return tool_LOG_ANALYZE(arg, system_tool, log)
    if name == "MODEL_MANAGER":
        return tool_MODEL_LIST(arg, system_tool, log)
        return tool_MODEL_MANAGER(arg, system_tool, log)
    if name == "MODE_MANAGER":
        return tool_MODE_MANAGER(arg, system_tool, log)
    if name == "STATUS_MONITOR":
        return tool_STATUS_MONITOR(arg, system_tool, log)
    if name in ["MODEL_SWITCHER", "PRZEŁĄCZNIK_MODELI"]:
        return switch_model(arg, log)
    if name in ["MODELE", "MODEL_SWITCHER"]:
        return tool_MODEL_SWITCHER(arg, log)
    if name == "MODEL_INFO":
        return tool_MODEL_INFO(arg, system_tool, log)
    if name == "MODEL_DESCRIBE":
        return tool_MODEL_DESCRIBE(arg, system_tool, log)






    




    if name == "NET_INFO":
        return tool_NET_INFO(arg, system_tool, log)
    if name == "NET_DIAG":
        return tool_NET_DIAG(arg, system_tool, log)
    if name == "NET_FIX":
        return tool_NET_FIX(arg, system_tool, log)
        # TMUX
    if name == "TMUX_SCREEN_DIAG":
        return tool_TMUX_SCREEN_DIAG(arg, system_tool, log)
    if name == "WATCHDOG":
        return tool_WATCHDOG(arg, system_tool, log)
    if name == "VOICE_INPUT":
        return tool_VOICE_INPUT(arg, system_tool, log)
    if name == "MEMORY_ANALYZE":
        return tool_MEMORY_ANALYZE(arg, system_tool, log)





    if name == "SYSTEM_DIAG":
        return tool_SYSTEM_DIAG(arg, system_tool, log)
    if name == "SYSTEM_FIX":
        return tool_SYSTEM_FIX(arg, system_tool, log)
    if name == "AUTO_OPTIMIZE":
        return tool_AUTO_OPTIMIZE(arg, system_tool, log)

    if name == "APP_CONTROL":
        return tool_APP_CONTROL(arg, system_tool, log)

    if name == "APP_GUARD":
        return tool_APP_GUARD(arg, system_tool, log)

    return f"[Lyra-System] Nieznane narzędzie: {name}"

# =========================================================
# MAIN
# =========================================================

user_prompt = " ".join(sys.argv[1:]).strip()


# --- automatyczny status przed każdą odpowiedzią ---
try:
    from modules.status_monitor import tool_STATUS_MONITOR
    print(tool_STATUS_MONITOR("", None, log))
except Exception as e:
    print(f"[Lyra] Nie udało się pobrać statusu: {e}")



# --- filtr poleceń TOOL: z opisem w języku polskim ---
if user_prompt.startswith("TOOL:"):
    rest = user_prompt.split(":", 1)[1].strip()
    tool_name, arg = (rest.split("|", 1) + [""])[:2]
    tool_name, arg = tool_name.strip(), arg.strip()
    output = tool_dispatch(tool_name, arg)
    print(f"🧰 Wynik narzędzia ({tool_name}):\n{output}\n")

    # Krótki opis po polsku od LLM (jeśli działa)
    try:
        messages = [
            {"role": "system", "content": "Przetłumacz techniczny wynik na naturalny język polski, krótko i rzeczowo."},
            {"role": "user", "content": output}
        ]
        resp = client.chat.completions.create(model="gpt-5.1", messages=messages)
        msg = resp.choices[0].message.content.strip()
        print(f"💬 {msg}")
    except Exception:
        pass

    sys.exit(0)


if "zmień model" in user_prompt.lower():
    new_model = user_prompt.split()[-1].lower()
    state = load_state()
    cfg["local_model"] = new_model
    with open(BASE_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print(f"✅ Zmieniono model na: {new_model}")
    sys.exit(0)
    
## === Lyra: aktualizacja modeli lokalnych ===
#import os
#if "aktualizuj modele" in user_input.lower():
#    print("🧠 Lyra: aktualizuję lokalne modele AI... proszę czekać...")
#    result = os.system("bash ~/update_ai_models.sh")
###    if result == 0:
#        print("✅ Zakończono — modele zostały zsynchronizowane.")
#    else:
#        print("⚠️ Wystąpił błąd podczas aktualizacji modeli. Sprawdź log w /media/tomek/arhiwum/#AI_MODELS/sync_log.txt.")
#    continue





if not user_prompt:
    print('Podaj treść polecenia, np.: ./agent.sh "Lyra zdiagnozuj internet"')
    sys.exit(0)
    
    
    # === Lyra: aktualizacja modeli lokalnych ===
import os
if "aktualizuj modele" in user_prompt.lower():
    print("🧠 Lyra: aktualizuję lokalne modele AI... proszę czekać...")
    result = os.system("bash ~/update_ai_models.sh")

    if result == 0:
        print("✅ Zakończono — modele zostały zsynchronizowane.")
    else:
        print("⚠️ Wystąpił błąd podczas aktualizacji modeli.")
        print("   Sprawdź log: /media/tomek/arhiwum/AI_MODELS/sync_log.txt")

    sys.exit(0)

    
    
    
    
    
    
# --- naturalne mapowanie fraz na moduły Lyry ---
prompt_lower = user_prompt.lower()
if "użyj" in user_prompt.lower():
    model_name = user_prompt.replace("użyj", "").strip()
    result = switch_model(model_name, log)
    print(result)
    sys.exit(0)

if "modele opis" in prompt_lower:
    user_prompt = "TOOL: MODEL_DESCRIBE |"
if "zdiagnozuj cinnamon" in prompt_lower or "zdiagnozuj środowisko" in prompt_lower:
    user_prompt = "TOOL: DESKTOP_DIAG | cinnamon"
elif "napraw cinnamon" in prompt_lower or "napraw środowisko" in prompt_lower:
    user_prompt = "TOOL: DESKTOP_FIX | cinnamon"
elif "zoptymalizuj system" in prompt_lower:
    user_prompt = "TOOL: AUTO_OPTIMIZE | auto"
elif "zdiagnozuj system" in prompt_lower:
    user_prompt = "TOOL: SYSTEM_DIAG | auto"
elif "modele" in prompt_lower:
    user_prompt = "TOOL: MODEL_SWITCHER | lista"
    user_prompt = "TOOL: MODEL_LIST |"

elif prompt_lower.startswith("użyj "):
    user_prompt = f"TOOL: MODEL_SWITCHER | {user_prompt}"

elif "odśwież modele" in prompt_lower:
    user_prompt = "TOOL: MODEL_SWITCHER | odśwież"
   

log(f"USER: {user_prompt}")

# --- snapshot systemu (lekki, bezpieczny)
update_state({
    "last_seen": datetime.now().isoformat(),
    "kernel": system_tool("uname -a", timeout=3)[:300],
    "os": system_tool("cat /etc/os-release", timeout=3)[:500],
    #session": system_tool("echo $XDG_SESSION_TYPE", timeout=3).strip()
    "last_autocontext": "tmux_screen",
    "last_autocontext_time": datetime.now().isoformat()
})

st = load_state()

system_message = {
    "role": "system",
    "content": (
        "Masz na imię LYRA.\n"
        "Jesteś stałą, techniczną asystentką Tomka w terminalu Linux.\n\n"

        "Twoja rola:\n"
        "- pomagasz Tomkowi OGARNIAĆ system, pliki, sieć, aplikacje i automatyzację\n"
        "- pamiętasz wcześniejsze działania (stan systemu + historię rozmów)\n"
        "- nie udajesz, że nie wiesz – jeśli coś było robione przed chwilą, ODNOŚ SIĘ DO TEGO\n\n"

        "Styl odpowiedzi:\n"
        "- mów po ludzku, technicznie, bez korpo-gadki\n"
        "- nie powtarzaj bez sensu instrukcji, jeśli już były robione\n"
        "- jeśli pytanie jest krótkie → odpowiedź krótka\n"
        "- jeśli problem jest złożony → prowadź krok po kroku\n\n"
        
        "Reguła ciągłości:"
        " - Jeśli w SYSTEM STATE jest last_tool / last_system_cmd,"
        " a Tomek pyta 'co było', 'co robiłaś', 'dlaczego',"
        " MUSISZ się do tego odnieść."
        
        "AUTOKONTEKST:"
        "- Jeśli użytkownik zgłasza błąd, zawieszenie, brak działania"
        "  i nie podał logów, MASZ prawo użyć:"
        "  TOOL: TMUX_SCREEN"
        "- Po odczytaniu ekranu:"
        "  - analizujesz zawartość"
        "  - NIE pytasz o logi, jeśli są na ekranie"
        "  - kontynuujesz diagnozę"

        

        "Zachowanie:\n"
        "- jeśli Tomek mówi 'zrób', 'sprawdź', 'napraw' → DZIAŁAJ\n"
        "- jeśli coś już sprawdzałaś → przypomnij, co wyszło\n"
        "- nie udawaj braku pamięci, jeśli stan jest w SYSTEM STATE\n\n"
        
  #     system_message["content"] += (
    "\n\nZASADA EKRANU:\n"
    "- Jeśli użytkownik pisze: 'zobacz ekran', 'co jest na ekranie', "
    "'sprawdź co się wyświetla', 'jaki jest błąd', 'co wyskoczyło', "
    "'co widzisz',"
    "a pracujemy w tmux → użyj SYSTEM: tmux_capture.\n"
#

        
        
        "Technika:\n"
        "- SYSTEM: tylko czyste komendy bash\n"
        "- TOOL: tylko wywołanie narzędzia\n"
        "- PROPOSE_TOOL: gdy brakuje funkcji\n\n"
        "Jesteś LYRĄ-System, asystentem Tomka w terminalu Linux.\n"
        "Obsługujesz SYSTEM / TOOL / PROPOSE_TOOL.\n\n"
        "\n"
        "ZASADA AUTOMATYCZNEJ DECYZJI:\n"
        "- Jesli polecenie dotyczy diagnozy, uzyj *_DIAG.\n"
        "- Jesli dotyczy naprawy, uzyj *_FIX.\n"
        "- Jesli dotyczy informacji, uzyj *_INFO.\n"
        "- Jesli dotyczy uruchomienia programu lub strony, uzyj: TOOL: APP_CONTROL | <opis>.\n"
        "- Jesli dotyczy pilnowania aplikacji, uzyj: TOOL: APP_GUARD | <opis>.\n"
        "- Jesli dotyczy plikow/katalogow/archiwow (find/cp/mv/grep/tar/unzip), uzyj: SYSTEM: <komenda>.\n"
        "- Jesli mozna wykonac od razu, NIE opisuj - zwroc tylko SYSTEM: albo TOOL:.\n"
        "- Jesli nie jest oczywiste, zapytaj krotko o doprecyzowanie.\n"
        "=== SYSTEM STATE ===\n"
        f"session: {st.get('session','')}\n"
        f"kernel: {st.get('kernel','')}\n"
        f"os:\n{st.get('os','')}\n"
        f"last_tool: {st.get('last_tool','')} {st.get('last_tool_arg','')}\n"
        f"last_system_cmd: {st.get('last_system_cmd','')}\n"
        "=== END STATE ===\n"
        
    )
}

messages = [
    system_message,
    {"role": "user", "content": user_prompt}
]

# =========================================================
# GENERATE RESPONSE
# =========================================================

msg = ""

# ---------------------------------------------------------
# BACKEND: LOCAL (Ollama)
# ---------------------------------------------------------
if cfg["backend"] == "local":
    try:
        payload = {
            "model": cfg["model"],
            "prompt": user_prompt
        }

        r = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=60,
            stream=True
        )

        msg = ""
        for line in r.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line.decode("utf-8"))
                msg += chunk.get("response", "")
            except Exception:
                pass

    except Exception as e:
        msg = f"[Błąd modelu lokalnego] {e}"

# ---------------------------------------------------------
# BACKEND: OPENAI
# ---------------------------------------------------------
else:
    try:
        msg, mode = query_model(
            user_prompt,
            cfg["model"],   # → tu musi być model z config.json
            cfg["model"],   # → fallback też na ten sam
            client,
            messages
        )
        log(f"MODEL USED: {mode}")

    except Exception as e:
        msg = f"[Błąd OpenAI] {e}"
# =========================================================
# DISPATCH
# =========================================================


if msg.strip() == "SYSTEM: tmux_capture":
    output = tmux_capture(800)
    print(output)

    update_state({
        "last_system_cmd": "tmux_capture",
        "last_system_output": output[:4000]
    })

    remember(user_prompt, f"SYSTEM: tmux_capture\n{output}")
    sys.exit(0)


if msg.startswith("SYSTEM:"):
    cmd = msg.replace("SYSTEM:", "", 1).strip()
    output = system_tool(cmd)
    print(output)

    update_state({
        "last_system_cmd": cmd,
        "last_system_output": output[:4000]
    })

    remember(user_prompt, f"SYSTEM: {cmd}\n{output[:4000]}")

elif msg.startswith("TOOL:"):
    rest = msg.replace("TOOL:", "", 1).strip()
    tool_name, arg = (rest.split("|", 1) + [""])[:2]
    tool_name, arg = tool_name.strip(), arg.strip()

    output = tool_dispatch(tool_name, arg)
    print(output)

    update_state({
        "last_tool": tool_name,
        "last_tool_arg": arg,
        "last_tool_output": output[:4000]
    })

    remember(user_prompt, f"TOOL: {tool_name} | {arg}\n{output[:4000]}")

elif msg.startswith("PROPOSE_TOOL:"):
    print(msg)
    remember(user_prompt, msg)

# =========================================================
# INTENT ROUTER
# =========================================================
tool_name, arg = detect_intent(user_prompt)
if tool_name:
    output = tool_dispatch(tool_name, arg)
    print(output)
    remember(user_prompt, f"[AUTO] TOOL: {tool_name} | {arg}\n{output}")
    sys.exit(0)

if "monitor" in user_prompt.lower() or "status" in user_prompt.lower():
    s = get_status()
    report = analyze_status(s)
    print(report)
    remember(user_prompt, report)
    sys.exit(0)

# =========================================================
# LOCAL BRAIN (fallback)
# =========================================================
else:
    out = query_brain(user_prompt)
    print(out)
    remember(user_prompt, out)

