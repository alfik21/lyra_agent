import psutil, time, subprocess, os
from datetime import datetime

MAX_LOG_SIZE = 500_000  # 500 KB rotacja logu

def rotate_log(log_path):
    if os.path.exists(log_path) and os.path.getsize(log_path) > MAX_LOG_SIZE:
        os.rename(log_path, log_path + ".old")

def tool_WATCHDOG(arg, system_tool, log):
    """
    Zaawansowany, stabilny WATCHDOG systemowy dla Lyry.
    Monitoruje CPU, RAM, sieć, internet, procesy i reaguje bezpiecznie.
    """
    LOG_FILE = "watchdog.log"
    rotate_log(os.path.expanduser(f"~/lyra_agent/logs/{LOG_FILE}"))

    log("=== START WATCHDOG ===", LOG_FILE)

    # ----- PODSTAWOWE POMIARY -----
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        net = psutil.net_io_counters()
    except Exception as e:
        return f"[WATCHDOG BŁĄD] psutil: {e}"

    total_sent = net.bytes_sent // (1024**2)
    total_recv = net.bytes_recv // (1024**2)

    # ----- SPRAWDZANIE INTERNETU -----
    try:
        internet_ok = subprocess.call(
            ["ping", "-c", "1", "1.1.1.1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ) == 0
    except Exception:
        internet_ok = False

    # ----- ANALIZA -----
    actions = []

    if cpu > 90:
        actions.append(f"⚠️ Wysokie użycie CPU: {cpu}%")

    if ram > 85:
        actions.append(f"⚠️ RAM prawie pełna: {ram}% – czyszczę cache...")
        try:
            system_tool("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches", timeout=3)
        except Exception as e:
            actions.append(f"❌ Cache czyszczenie nie powiodło się: {e}")

    if not internet_ok:
        actions.append("🌐 Brak internetu!")

    # ----- WYKRYWANIE PROCESÓW ZJADAJĄCYCH CPU -----
    heavy = []
    for p in psutil.process_iter(["name", "cpu_percent"]):
        try:
            if p.info["cpu_percent"] > 70:
                heavy.append(f"{p.info['name']} – {p.info['cpu_percent']}%")
        except:
            pass

    # ----- ZŁOŻENIE RAPORTU -----
    result = (
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🧠 CPU: {cpu}% | 💾 RAM: {ram}%\n"
        f"📡 Internet: {'OK' if internet_ok else 'BRAK'}\n"
        f"🌐 TX/RX: {total_sent}/{total_recv} MB\n"
    )

    if heavy:
        result += "\n🔥 Procesy obciążające CPU:\n"
        for h in heavy:
            result += f" → {h}\n"

    if actions:
        result += "\n⚠️ Działania:\n" + "\n".join(f" → {a}" for a in actions)
    else:
        result += "\n✅ System stabilny"

    log(result, LOG_FILE)
    return result

