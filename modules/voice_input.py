import speech_recognition as sr
import subprocess, time

def tool_VOICE_INPUT(arg, system_tool, log):
    """
    Nasłuch mikrofonu + rozpoznawanie komendy.
    Bezpieczne, zgodne z system_tool(timeout),
    nie tworzy kolejnych instancji Lyry.
    """

    recognizer = sr.Recognizer()

    try:
        mic = sr.Microphone()
    except Exception as e:
        return f"❌ Mikrofon niedostępny: {e}"

    print("🎤 Powiedz coś do Lyry...")

    with mic as source:
        try:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, phrase_time_limit=6)
        except Exception as e:
            return f"❌ Błąd nasłuchu mikrofonu: {e}"

    text = None

    # 🧠 Rozpoznawanie Google (jeśli jest internet)
    try:
        text = recognizer.recognize_google(audio, language="pl-PL")
    except sr.UnknownValueError:
        return "❌ Nie zrozumiałam – powiedz jeszcze raz."
    except Exception:
        text = None  # brak internetu → spróbujemy lokalnie

    if not text:
        try:
            text = recognizer.recognize_sphinx(audio, language="pl-PL")
        except Exception:
            return "❌ Nie udało się rozpoznać mowy (offline oraz online)."

    # Zapisz do loga
    log(f"[VOICE] Rozpoznano: {text}", "voice.log")

    print(f"🗣️ Rozpoznano: {text}")

    # ------------------------------------------------------
    # 🔥 Najważniejsze: NIE wywołujemy subprocess.run(["lyra"])
    # To tworzy nowe instancje Lyry → chaos.
    # ------------------------------------------------------

    # Zwracamy tekst do agent.py → agent sam go przetworzy.
    return f"[VOICE_COMMAND] {text}"

