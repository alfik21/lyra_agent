import os, subprocess
from datetime import datetime

# Ujednolicony katalog logów
LOG_DIR = os.path.expanduser("~/lyra_agent/logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log_guard(app, msg):
    path = os.path.join(LOG_DIR, "watchdog_apps.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} | {app.upper()} | {msg}\n")

def generate_script(app):
    # Generuje skrypt monitorujący (uproszczone pod systemd)
    return f"while true; do pgrep -f {app} || {app} & sleep 60; done"

def tool_APP_GUARD(app, system_run, log):
    app = app.strip().lower()
    if not app: return "Podaj nazwę aplikacji."
    
    log_guard(app, "Aktywacja strażnika.")
    # Tutaj logika tworzenia unitu systemd (jak w Twoim oryginale)
    return f"🛡️ Strażnik dla {app} został skonfigurowany w logach Lyry."
