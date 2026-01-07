import subprocess, re, time
from datetime import datetime

def tool_TMUX_SCREEN_DIAG(arg, system_tool, log):
    """
    Odczytuje ostatnie linie z aktywnego tmux-pane,
    szuka błędów i podpowiada rozwiązania.
    """
    try:
        log("=== TMUX_SCREEN_DIAG start ===", "tmux.log")
        output = system_tool("tmux capture-pane -pS -200 | tail -n 200", timeout=4)
        if not output.strip():
            return "Brak aktywnego okna tmux lub pusty ekran."

        log(output, "tmux.log")
        hints = []

        # wykrywanie typowych błędów
        if "error:" in output.lower() or "failed" in output.lower():
            hints.append("⚠️ Wykryto błąd systemowy – sprawdź logi lub użyj: lyra 'zdiagnozuj system'")
        if "alsa" in output.lower() or "pipewire" in output.lower():
            hints.append("🎧 Wykryto błąd audio – użyj: lyra 'zdiagnozuj dźwięk'")
        if "apt" in output.lower() and "error" in output.lower():
            hints.append("📦 Błąd APT – uruchom: lyra 'napraw system'")
        if "network" in output.lower() or "unreachable" in output.lower():
            hints.append("🌐 Problem z siecią – spróbuj: lyra 'zdiagnozuj internet'")

        summary = (
            f"=== TMUX DIAGNOZA ===\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
            f"{output[-800:]}\n\n"
        )
        if hints:
            summary += "\n".join(hints)
        else:
            summary += "✅ Nie wykryto oczywistych błędów."
        log(summary, "tmux.log")
        return summary

    except Exception as e:
        return f"[Błąd TMUX_SCREEN_DIAG] {e}"
