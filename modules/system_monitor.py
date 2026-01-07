import psutil, subprocess

def get_status():
    status = {}
    # CPU / RAM
    status["cpu_load"] = psutil.cpu_percent(interval=1)
    status["ram_used"] = round(psutil.virtual_memory().percent, 1)
    # Sieć
    try:
        result = subprocess.run(["ping", "-c", "1", "1.1.1.1"],
                                capture_output=True, text=True, timeout=2)
        status["net_ok"] = result.returncode == 0
    except Exception:
        status["net_ok"] = False
    # Audio
    try:
        vol = subprocess.getoutput("pactl get-sink-volume @DEFAULT_SINK@ | awk '{print $5}'")
        mute = subprocess.getoutput("pactl get-sink-mute @DEFAULT_SINK@")
        status["audio_volume"] = vol
        status["audio_muted"] = "yes" in mute
    except Exception:
        status["audio_volume"] = "?"
        status["audio_muted"] = None
    return status


def analyze_status(status: dict) -> str:
    alerts = []
    if status["cpu_load"] > 85:
        alerts.append(f"CPU obciążony ({status['cpu_load']} %)")
    if status["ram_used"] > 90:
        alerts.append(f"Pamięć RAM prawie pełna ({status['ram_used']} %)")
    if not status["net_ok"]:
        alerts.append("Brak połączenia z internetem")
    if status["audio_muted"]:
        alerts.append("Dźwięk jest wyciszony")
    if not alerts:
        return "System stabilny. Wszystko wygląda dobrze."
    return "⚠️  " + "; ".join(alerts)

