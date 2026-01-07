import subprocess, psutil, os

def tool_DESKTOP_DIAG(arg, system_tool, log):
    """
    Diagnostyka środowiska graficznego (Cinnamon / KDE / GNOME / XFCE).
    """
    try:
        result = "🖥️ Diagnoza środowiska graficznego:\n"

        # wykrycie środowiska
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "unknown")
        result += f"- Wykryte środowisko: {desktop}\n"

        # sprawdzenie procesów
        processes = ["cinnamon", "muffin", "nemo", "plasmashell", "kwin_x11", "gnome-shell", "xfce4-session"]
        active = []
        for p in psutil.process_iter(["name", "pid"]):
            if p.info["name"] in processes:
                active.append(f"{p.info['name']} (PID {p.info['pid']})")

        if active:
            result += "✅ Działające procesy: " + ", ".join(active) + "\n"
        else:
            result += "⚠️ Nie wykryto aktywnych procesów środowiska – możliwe zawieszenie GUI.\n"

        # logi błędów
        result += "\n=== Ostatnie błędy graficzne ===\n"
        result += system_tool("grep -iE 'cinnamon|muffin|nemo|xorg|mutter|kwin' ~/.xsession-errors | tail -n 10 || echo 'Brak błędów'")

        return result
    except Exception as e:
        return f"[Błąd DESKTOP_DIAG] {e}"


def tool_DESKTOP_FIX(arg, system_tool, log):
    """
    Restart powłoki graficznej i czyszczenie cache środowiska.
    """
    try:
        result = "🔧 Naprawa środowiska graficznego:\n"
        result += system_tool("killall -9 cinnamon muffin nemo plasmashell gnome-shell xfce4-session || true")
        result += "\nUruchamianie powłoki Cinnamon...\n"
        result += system_tool("nohup bash -c 'sleep 2 && cinnamon --replace >/dev/null 2>&1 &'")

        # result += system_tool("nohup cinnamon --replace >/dev/null 2>&1 & disown")
        result += "\n✅ Powłoka graficzna zrestartowana."
        return result
    except Exception as e:
        return f"[Błąd DESKTOP_FIX] {e}"
