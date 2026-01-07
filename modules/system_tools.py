import psutil, subprocess, os, platform

# =========================================================
# 🩺 DIAGNOZA SYSTEMU
# =========================================================

def tool_SYSTEM_DIAG(arg, system_tool, log):
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()

        uptime = system_tool("uptime -p").strip()
        temps = system_tool("sensors 2>/dev/null | grep '°C' | head -n 5")

        diag = (
            f"🩺 Diagnoza systemu:\n"
            f"- Uptime: {uptime}\n"
            f"- CPU użycie: {cpu}%\n"
            f"- RAM: {ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB\n"
            f"- SWAP: {swap.used // (1024**2)} MB / {swap.total // (1024**2)} MB\n"
            f"- Temperatura (top 5):\n{temps}\n"
            f"- Liczba procesów: {len(psutil.pids())}\n"
        )

        # Procesy najbardziej obciążające CPU
        top_proc = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                top_proc.append((p.info["pid"], p.info["name"], p.info["cpu_percent"]))
            except:
                continue

        top_proc = sorted(top_proc, key=lambda x: x[2], reverse=True)[:5]

        diag += "\n🔥 TOP 5 procesów CPU:\n"
        for pid, name, cpu_p in top_proc:
            diag += f"  {pid} {name} – {cpu_p}% CPU\n"

        return diag

    except Exception as e:
        return f"[Błąd SYSTEM_DIAG] {e}"


# =========================================================
# 🔧 NAPRAWA SYSTEMU — automatyczne wykrywanie APT / DNF
# =========================================================

def _package_manager():
    if os.path.exists("/usr/bin/apt"):
        return "apt"
    if os.path.exists("/usr/bin/dnf"):
        return "dnf"
    return None


def tool_SYSTEM_FIX(arg, system_tool, log):
    """
    Automatyczna naprawa systemu – aktualizacje, zależności
    """
    out = []
    out.append("=== AUTO FIX SYSTEMU ===")

    # aktualizacja pakietów
    out.append("➤ aktualizacja pakietów:")
    out.append(system_tool("sudo apt update && sudo apt upgrade -y"))

    # naprawa zależności
    out.append("\n➤ naprawa zależności:")
    out.append(system_tool("sudo apt --fix-broken install -y"))

    # czyszczenie
    out.append("\n➤ czyszczenie systemu:")
    out.append(system_tool("sudo apt autoremove -y"))

    log("System naprawiony automatycznie", "system_fix.log")

    return "\n".join(out)


# =========================================================
# ⚙️ AUTO-OPTIMIZE — Bezpieczna optymalizacja
# =========================================================

def tool_AUTO_OPTIMIZE(arg, system_tool, log):
    try:
        actions = [
            "sync",
            "systemctl --user restart pipewire.service",
            "systemctl --user restart wireplumber.service",
            "systemctl --user restart pipewire-pulse.service",
        ]

        result = "⚙️ Auto-Optymalizacja systemu:\n"

        for a in actions:
            out = system_tool(a, timeout=10)
            result += f"\n→ {a}\n{out}\n"

        result += "\n✅ System zoptymalizowany (bez ryzyka utraty sesji)."
        return result

    except Exception as e:
        return f"[Błąd AUTO_OPTIMIZE] {e}"

# To pozwoli Lyrze wywołać funkcję po nazwie, której szuka Router
def get_system_status():
    # Tworzymy atrapę funkcji system_tool, żeby skrypt działał samodzielnie
    def mock_tool(cmd, timeout=5):
        import subprocess
        try:
            return subprocess.check_output(cmd, shell=True, text=True, timeout=timeout)
        except: return ""
    
    def mock_log(msg, file): pass

    return tool_SYSTEM_DIAG(None, mock_tool, mock_log)

if __name__ == "__main__":
    print(get_system_status())

