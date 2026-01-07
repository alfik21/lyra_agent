import shutil
import urllib.parse
from textwrap import indent

def _has(bin_name: str) -> bool:
    return shutil.which(bin_name) is not None

def _pick_browser() -> str | None:
    for b in ["brave-browser", "google-chrome", "chromium", "firefox"]:
        if _has(b):
            return b
    return None  # użyjemy xdg-open

def _log_cmd(log, cmd, out=""):
    if log:
        log(f"[APP_CONTROL] {cmd} -> {out[:500]}", "app.log")

def tool_APP_CONTROL(description: str, system_tool, log):
    """
    Inteligentne otwieranie aplikacji/stron na podstawie opisu Tomka.
    Przykłady:
      - 'włącz youtube'
      - 'odpal youtube najnowsze filmy o linux pipewire'
      - 'uruchom lutris'
      - 'włącz steam i discord'
    """
    desc_raw = description.strip()
    desc = desc_raw.lower()

    notes: list[str] = []
    cmds: list[str] = []

    # --- 1. YOUTUBE / przeglądarka ---
    if "youtube" in desc or "yt " in desc or desc.startswith("yt"):
        base = "https://www.youtube.com"
        query = desc

        # spróbuj wyciągnąć słowa kluczowe po 'youtube'
        for cut in ["youtube", "yt", "włącz", "wlacz", "odpal", "otwórz", "otworz", "puść", "pusc", "najowsze", "najnowsze", "filmy", "film"]:
            query = query.replace(cut, "")
        query = " ".join(query.split()).strip()

        if query:
            q_encoded = urllib.parse.quote_plus(query)
            # prosty search; YT i tak to ogarnie
            url = f"{base}/results?search_query={q_encoded}"
            if "najnowsze" in desc or "najowsze" in desc:
                # lekkie wymuszenie sortowania po dacie (nie idealne, ale wystarczy)
                url += "&sp=CAISAhAB"
            notes.append(f"Otwieram YouTube z wyszukiwaniem: {query}")
        else:
            url = base
            notes.append("Otwieram stronę główną YouTube.")

        browser = _pick_browser()
        if browser:
            cmd = f'{browser} "{url}" &'
        else:
            cmd = f'xdg-open "{url}" &'
        out = system_tool(cmd)
        _log_cmd(log, cmd, out)
        cmds.append(cmd)

    # --- 2. MAPA APLIKACJI GRAFICZNYCH ---
    apps = {
        "lutris": ["lutris"],
        "steam": ["steam"],
        "discord": ["discord"],
        "spotify": ["spotify"],
        "telegram": ["telegram-desktop", "telegram"],
        "obs": ["obs"],          # OBS Studio
        "vlc": ["vlc"],
        "gg": ["gg", "gadu-gadu"],
    }

    # sprawdzamy po słowach-kluczach
    for key, candidates in apps.items():
        if key in desc:
            found_bin = None
            for c in candidates:
                if _has(c):
                    found_bin = c
                    break
            if found_bin:
                cmd = f"{found_bin} &"
                out = system_tool(cmd)
                _log_cmd(log, cmd, out)
                cmds.append(cmd)
                notes.append(f"Uruchamiam aplikację: {found_bin}")
            else:
                notes.append(f"Nie znalazłam programu '{key}' w PATH (sprawdź, czy jest zainstalowany).")

    # --- 3. Jeśli nic nie rozpoznałam ---
    if not cmds:
        notes.append("Nie rozumiem, jaką aplikację lub stronę mam otworzyć na podstawie tego opisu:")
        notes.append(f"  \"{desc_raw}\"")
        notes.append("Spróbuj np.: 'Lyra włącz YouTube', 'Lyra uruchom Lutris', 'Lyra odpal Steam'.")
        return "\n".join(notes)

    notes.append("")
    notes.append("Wykonane polecenia:")
    for c in cmds:
        notes.append(f"  $ {c}")

    return "\n".join(notes)
