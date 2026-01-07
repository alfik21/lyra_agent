import re

def detect_intent(user_prompt: str) -> tuple[str, str]:
    raw = user_prompt.strip()
    if raw.lower().startswith("lyra "):
        raw = raw[5:].strip()
    p = raw.lower().strip()

    # 📄 0. ODCZYT PLIKU
    m = re.search(
        r"(?:czytaj|odczytaj|wczytaj|przeczytaj|pokaz|pokaż|wyswietl|wyświetl)\s+"
        r"(?:zawartosc|zawartość)?\s*(?:pliku|plik)\s+(.+)",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        path = m.group(1).strip().lstrip(":").strip()
        return ("FILE_READ", path)

    m = re.search(r"^(?:podsumuj|stresc|streszcz)\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        path = m.group(1).strip()
        return ("FILE_READ_SUMMARY", path)

    if re.search(r"^o czym jest ten plik(\s+co\s+przeczyta(ł|l)as|ąś)?\??$", raw, flags=re.IGNORECASE):
        return ("LAST_FILE_SUMMARY", "")
    if re.search(r"^co było ciekawego w tym pliku\??$", raw, flags=re.IGNORECASE):
        return ("LAST_FILE_SUMMARY", "")

    if re.search(r"^(sprawdz|sprawdź)\s+sterowniki\b", raw, flags=re.IGNORECASE):
        return ("SYSTEM_DIAG", "sterowniki")

    if any(key in p for key in [
        "sprawdz w internecie",
        "sprawdź w internecie",
        "wyszukaj w internecie",
        "znajdz w internecie",
        "znajdź w internecie",
        "poszukaj w internecie",
        "szukaj w internecie",
        "aktualne informacje",
        "co nowego",
        "najświeższe",
        "najnowsze informacje",
    ]):
        return ("INTERNET_SEARCH", raw)

    if re.search(r"^(ktora|która|ktorej|ktorej|która|która|która|która)\s+godzina\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktora\s+jest\s+godzina\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktora\s+godzina\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktora\s+jest\s+teraz\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktora\s+jest\s+teraz\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktora\s+godzina\s+teraz\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktorej\s+godzina\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktorej\s+jest\s+godzina\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktora\s+godzina\s+jest\??$", raw, flags=re.IGNORECASE) or re.search(r"^ktora\s+godzina\s+teraz\??$", raw, flags=re.IGNORECASE) or re.search(r"^która\s+godzina\??$", raw, flags=re.IGNORECASE) or re.search(r"^która\s+jest\s+godzina\??$", raw, flags=re.IGNORECASE):
        return ("SYSTEM_DIAG", "time")

    if re.search(r"^(?:pokaz|pokaż|wyswietl|wyświetl|lista)\s+komend\b", raw, flags=re.IGNORECASE):
        return ("COMMAND_LIST", "")
    m = re.search(
        r"^(?:przeczytaj|odczytaj|wczytaj|czytaj)\s+(.+?)\s+"
        r"(?:i\s+(?:podsumuj|stres[cś]c|streszcz))(?:\s+\w+)?\s+"
        r"w\s+\d+\s+zdani(?:ach|a)\s*$",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        path = m.group(1).strip()
        return ("FILE_READ_SUMMARY", path)

    m = re.search(
        r"^(?:przeczytaj|odczytaj|wczytaj|czytaj)\s+"
        r"(?:i\s+(?:podsumuj|stres[cś]c|streszcz))\s+(.+?)\s+"
        r"w\s+\d+\s+zdani(?:ach|a)\s*$",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        path = m.group(1).strip()
        return ("FILE_READ_SUMMARY", path)

    m = re.search(r"^(?:przeczytaj|odczytaj|wczytaj|czytaj)\s+(?:i\s+(?:podsumuj|stres[cś]c|streszcz))\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        path = m.group(1).strip()
        return ("FILE_READ_SUMMARY", path)
    m = re.search(r"^(?:przeczytaj|odczytaj|wczytaj|czytaj)\s+(.+?)\s+(?:i\s+(?:podsumuj|stres[cś]c|streszcz))$", raw, flags=re.IGNORECASE)
    if m:
        path = m.group(1).strip()
        return ("FILE_READ_SUMMARY", path)

    m = re.search(r"^(?:przeczytaj|odczytaj|wczytaj|czytaj)\s+(.+?)\s+(?:i\s+(?:podsumuj|stres[cś]c|streszcz))\s+(?:krótko|krotko|krócej|krocej)$", raw, flags=re.IGNORECASE)
    if m:
        path = m.group(1).strip()
        return ("FILE_READ_SUMMARY_SHORT", path)
    m = re.search(r"^(?:przeczytaj|odczytaj|wczytaj|czytaj)\s+(.+?)\s+(?:i\s+(?:podsumuj|stres[cś]c|streszcz))\s+(?:dlugo|długo|szczegółowo|szczegolowo)$", raw, flags=re.IGNORECASE)
    if m:
        path = m.group(1).strip()
        return ("FILE_READ_SUMMARY_LONG", path)

    # skróty typu: "pokaz plik.txt" / "przeczytaj /sciezka/plik"
    m = re.search(r"^(?:pokaz|pokaż|wyswietl|wyświetl|przeczytaj)\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        path = m.group(1).strip()
        if "/" in path or "." in path:
            return ("FILE_READ", path)

    if re.search(r"^dodaj (na koncu|na poczatku|w srodku)\s+", raw, flags=re.IGNORECASE):
        return ("FILE_EDIT", raw)
    if re.search(r"^dodaj w linii numer\s+\d+\s+", raw, flags=re.IGNORECASE):
        return ("FILE_EDIT", raw)
    if re.search(r"^zahaszuj linie (nr|od)\s+", raw, flags=re.IGNORECASE):
        return ("FILE_EDIT", raw)
    if re.search(r"^zacznij plik\s+", raw, flags=re.IGNORECASE):
        return ("FILE_EDIT", raw)

    # 💽 1. DYSKI (Poprawione: teraz zawsze zwraca DISK_DIAG)
    if any(k in p for k in [
        "sprawdź dyski", "sprawdz dyski", "pokaż dyski", "pokaz dyski", "dyski", "dysk",
        "partycje", "wolne miejsce", "ile mam miejsca", "miejsce na dysku", "przestrzen na dysku"
    ]):
        return ("DISK_DIAG", "")

    # 🌐 2. SIEĆ
    if any(word in p for word in ["internet", "sieć", "sieci", "wifi", "wi-fi", "ping", "lan", "ethernet", "polaczenie", "łącze"]):
        if any(x in p for x in ["napraw", "restart"]): return ("NET_FIX", p)
        if any(x in p for x in ["diagnoz", "sprawdź", "sprawdz", "testuj"]): return ("NET_DIAG", p)
        return ("NET_INFO", p)

    # 🔊 3. AUDIO
    if any(word in p for word in ["dźwięk", "audio", "glosnosc", "głośność", "mikrofon", "mikro", "sound", "glosniki", "głośniki"]):
        if any(x in p for x in ["napraw", "restart"]): return ("AUDIO_FIX", p)
        return ("AUDIO_DIAG", p)

    # 🖥️ 4. SYSTEM (Poprawione mapowanie pod agent.py)
    if any(word in p for word in ["procesor", "cpu", "ram", "pamięć", "pamiec", "system", "kernel", "update", "procesy", "obciazenie", "obciążenie"]):
        if "opt" in p: return ("AUTO_OPTIMIZE", p)
        if "napraw" in p: return ("SYSTEM_FIX", p)
        return ("SYSTEM_DIAG", p)

    # 📦 5. APLIKACJE / GUARD
    if any(word in p for word in ["monitoruj", "pilnuj", "guard"]): return ("APP_GUARD", p)
    if any(word in p for word in ["uruchom", "otwórz", "włącz"]): return ("APP_CONTROL", p)

    # 🖥️ 6. LOGI / DESKTOP
    if re.search(r"\blog(?:i|ow|ów)?\b", p) or any(x in p for x in ["dziennik", "journal"]):
        return ("LOG_ANALYZE", p)
    if any(x in p for x in ["cinnamon", "ekran", "pulpit", "panel", "tray"]): return ("DESKTOP_DIAG", p)

    return ("LLM", user_prompt)
