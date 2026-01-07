import shutil
from textwrap import indent

def _run(cmd, system_tool, timeout_tag="", log=None):
    out = system_tool(cmd)
    if log:
        log(f"[AUDIO_DIAG {_short(cmd)}] {out[:4000]}", "audio.log")
    return out

def _short(cmd: str, limit: int = 40) -> str:
    return (cmd[:limit] + "...") if len(cmd) > limit else cmd

def _has(bin_name: str) -> bool:
    return shutil.which(bin_name) is not None

def tool_AUDIO_DIAG(description: str, system_tool, log):
    report = []
    report.append("=== AUDIO_DIAG – diagnostyka dźwięku PipeWire/PulseAudio/ALSA ===")
    if description:
        report.append(f"Opis / kontekst: {description}")
    report.append("")

    # 1. binarki
    report.append("## 1. Dostępne binarki:")
    for bin_name in [
        "pipewire", "pipewire-pulse", "wireplumber", "pw-cli", "pactl",
        "pulseaudio", "alsactl", "aplay", "arecord"
    ]:
        path = shutil.which(bin_name)
        report.append(f"- {bin_name}: {'OK -> ' + path if path else 'BRAK'}")
    report.append("")

    # 2. status usług
    def _systemctl_user(unit):
        return _run(f"systemctl --user is-active {unit}", system_tool, log=log)

    report.append("## 2. Status usług (systemctl --user):")
    units = [
        "pipewire.service",
        "pipewire-pulse.service",
        "wireplumber.service",
        "pulseaudio.service",
    ]
    statuses = {}
    for u in units:
        s = _systemctl_user(u)
        statuses[u] = s
        report.append(f"- {u}: {s}")
    report.append("")

    pa_status = statuses.get("pulseaudio.service", "")
    pw_pulse_status = statuses.get("pipewire-pulse.service", "")
    if "active" in pa_status and "active" in pw_pulse_status:
        report.append("!!! UWAGA: Jednocześnie aktywne pulseaudio.service i pipewire-pulse.service (konflikt).")
    else:
        report.append("Brak oczywistego konfliktu PulseAudio vs PipeWire-Pulse.")
    report.append("")

    # 3. PipeWire / pw-cli
    report.append("## 3. PipeWire")
    if _has("pw-cli"):
        report.append("### 3.1 Urządzenia (pw-cli ls Device):")
        out_devices = _run("pw-cli ls Device", system_tool, log=log)
        report.append(indent(out_devices[:4000], "    ") or "    (brak)")
        report.append("")
        report.append("### 3.2 Węzły (pw-cli ls Node):")
        out_nodes = _run("pw-cli ls Node", system_tool, log=log)
        report.append(indent(out_nodes[:4000], "    ") or "    (brak)")
    else:
        report.append("pw-cli: BRAK – ograniczona diagnoza PipeWire.")
    report.append("")

    # 4. PulseAudio / pipewire-pulse – przez pactl
    report.append("## 4. PulseAudio / pipewire-pulse (pactl)")
    if _has("pactl"):
        info = _run("pactl info", system_tool, log=log)
        report.append("### 4.1 pactl info:")
        report.append(indent(info, "    "))
        report.append("")

        sinks = _run("pactl list short sinks", system_tool, log=log)
        report.append("### 4.2 sinks (wyjścia):")
        report.append(indent(sinks or "(brak)", "    "))
        report.append("")

        sources = _run("pactl list short sources", system_tool, log=log)
        report.append("### 4.3 sources (wejścia):")
        report.append(indent(sources or "(brak)", "    "))
        report.append("")

        sinputs = _run("pactl list short sink-inputs", system_tool, log=log)
        report.append("### 4.4 aktywne strumienie (sink-inputs):")
        report.append(indent(sinputs or "(brak aktywnych strumieni)", "    "))
        report.append("")

        default_sink = _run("pactl get-default-sink", system_tool, log=log)
        default_source = _run("pactl get-default-source", system_tool, log=log)
        report.append("### 4.5 domyślne urządzenia:")
        report.append(f"    Default sink  : {default_sink}")
        report.append(f"    Default source: {default_source}")
        report.append("")
    else:
        report.append("pactl: BRAK – brak szczegółów o sesji audio.")
        info = ""

    # 5. ALSA
    report.append("## 5. ALSA (aplay/arecord)")
    if _has("aplay"):
        aplay_out = _run("aplay -l", system_tool, log=log)
        report.append("### 5.1 aplay -l:")
        report.append(indent(aplay_out or "(brak urządzeń)", "    "))
    else:
        report.append("aplay: BRAK")
        aplay_out = ""

    if _has("arecord"):
        arec_out = _run("arecord -l", system_tool, log=log)
        report.append("### 5.2 arecord -l:")
        report.append(indent(arec_out or "(brak urządzeń)", "    "))
    else:
        report.append("arecord: BRAK")
        arec_out = ""

    report.append("")
    report.append("## 6. Podsumowanie Lyry (wstępne):")

    # proste heurystyki
    if aplay_out and "no soundcards found" in aplay_out.lower():
        report.append("- ALSA nie widzi kart dźwiękowych – problem sprzętowy/sterownik/moduły kernela.")
    if "Server Name:" in info:
        if "PipeWire" in info:
            report.append("- Serwer audio działa na PipeWire (OK).")
        elif "PulseAudio" in info:
            report.append("- Serwer audio: PulseAudio – OK, o ile nie dubluje się z PipeWire.")
    if "active" in pa_status and "active" in pw_pulse_status:
        report.append("- KONFLIKT: PulseAudio i PipeWire-Pulse jednocześnie aktywne – warto wyłączyć PulseAudio.")

    report.append("")
    report.append("=== KONIEC RAPORTU AUDIO_DIAG ===")
    report.append("")
    report.append("Jeśli chcesz, mogę spróbować naprawić audio automatycznie (tryb 3):")
    report.append('- wywołaj:  ./agent.sh "Lyra napraw dźwięk"  (użyje AUDIO_FIX)')

    return "\n".join(report)


def tool_AUDIO_FIX(description: str, system_tool, log):
    """
    Tryb 3 – wykonuje dość agresywne, ale odwracalne naprawy audio.
    NIE usuwa pakietów, NIE grzebie w kernelu.
    """
    steps = []
    steps.append("=== AUDIO_FIX – automatyczne naprawy audio (tryb 3) ===")
    if description:
        steps.append(f"Opis / kontekst: {description}")
    steps.append("")

    # 1. Restart usług PipeWire/pipewire-pulse/wireplumber
    cmds = [
        "systemctl --user restart pipewire.service",
        "systemctl --user restart pipewire-pulse.service",
        "systemctl --user restart wireplumber.service",
    ]
    for c in cmds:
        out = system_tool(c)
        steps.append(f"$ {c}\n{indent(out, '    ')}\n")
        if log:
            log(f"[AUDIO_FIX] {c} -> {out[:1000]}", "audio_fix.log")

    # 2. Wyciszenia – spróbuj odblokować
    for c in [
        "pactl set-sink-mute @DEFAULT_SINK@ 0",
        "pactl set-sink-volume @DEFAULT_SINK@ 80%",
    ]:
        out = system_tool(c)
        steps.append(f"$ {c}\n{indent(out, '    ')}\n")

    steps.append("=== KONIEC AUDIO_FIX ===")
    steps.append("Jeśli nadal nie ma dźwięku – zrób jeszcze raz AUDIO_DIAG i pokaż raport Lyrze w czacie.")
    return "\n".join(steps)
