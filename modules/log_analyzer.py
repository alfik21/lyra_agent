import re
from datetime import datetime

def tool_LOG_ANALYZE(arg, system_tool, log):
    """
    Analizuje treść logów (np. systemowych, Xorg, Cinnamon)
    i tłumaczy je na ludzki język. Pobiera ostatnie 100 linii z pliku logu,
    interpretuje znane wzorce błędów i zwraca raport tekstowy.
    Argument `arg` może zawierać ścieżkę do pliku logu; jeżeli jest pusty,
    używa domyślnego pliku ~/.xsession-errors.
    """
    try:
        # jeśli nie podano ścieżki – bierzemy ~/.xsession-errors
        path = arg.strip() or "~/.xsession-errors"

        # Pobierz ostatnie 100 linii z pliku logu
        output = system_tool(f"tail -n 100 {path}", timeout=5)

        explanations = []

        # proste heurystyki do rozpoznawania częstych błędów
        lower_out = output.lower()
        if "ebusy" in lower_out or "resource busy" in lower_out:
            explanations.append("🧩 System zgłasza 'resource busy' – czyli zasób (np. karta graficzna lub sesja Xorg) jest już zajęty przez inny proces.")

        if "mutter" in lower_out or "muffin" in lower_out:
            explanations.append("🎨 Mutter/Muffin jednocześnie — konflikt środowisk GNOME ↔ Cinnamon.")

        if "respawning too quickly" in lower_out:
            explanations.append("♻️ Powłoka Cinnamon wpada w crash-loop — najczęściej przez uszkodzony motyw lub rozszerzenie.")

        if "gnome-shell" in lower_out:
            explanations.append("🪟 GNOME przejął sesję — Cinnamon nie mógł wystartować.")

        if "failed to start" in lower_out:
            explanations.append("❌ Cinnamon nie wystartował — może być uszkodzony motyw lub pakiet cinnamon-settings-daemon.")

        if not explanations:
            explanations.append("✅ Nie znaleziono krytycznych błędów — sesja wygląda stabilnie.")

        text = (
            f"=== Analiza logu {path} ({datetime.now().strftime('%H:%M:%S')}) ===\n\n"
            f"{output[-800:]}\n\n"
            + "\n".join(explanations)
        )

        log(text, "log_analyzer.log")
        return text

    except Exception as e:
        return f"[Błąd LOG_ANALYZE] {e}"

