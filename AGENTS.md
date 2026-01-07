# Repository Guidelines

## Struktura projektu i organizacja plików
Ten repozytorium to agent „Lyra” w Pythonie. Najważniejsze miejsca:
- `agent.py` to główny plik uruchomieniowy.
- `agent.sh` to prosty skrót do `agent.py`.
- `modules/` zawiera narzędzia (sieć, audio, system, pamięć itd.).
- `lyra_project/` to rdzeń projektu używany przez `agent.py`.
- `logs/` trzyma logi uruchomień i błędów.
- `memory*.json`, `state.json`, `agent_state.json` to pliki stanu (nie edytuj ich bez potrzeby).
- `llama.cpp/` to osobny projekt serwera modeli.
- `venv/`, `.venv/`, `myenv/`, `processor/`, `be/`, `seems/` wyglądają na środowiska Pythona — zwykle ich nie ruszamy.

## Pierwsze uruchomienie (krok po kroku)
1) Wejdź do katalogu projektu:
   `cd /home/tomek/lyra_agent`
2) Zainstaluj zależności:
   `pip install -r requirements.txt`
3) Uruchom agenta:
   `python3 agent.py`
4) Jeśli pojawi się błąd `ImportError: openai`, doinstaluj:
   `pip install openai`
5) Gdy coś nie działa, sprawdź logi w `logs/`.

## Uruchomienie przez skrypty
- Szybki start: `./agent.sh`
- Start w tmux (LLM + GPU + Lyra): `./start_lyra_tmux.sh`

## Dodawanie nowego narzędzia (krok po kroku)
1) Dodaj plik w `modules/` (np. `modules/my_tool.py`).
2) W `agent.py` zaimportuj funkcję narzędzia.
3) Dodaj narzędzie do słownika `SYSTEM_TOOLS`.
4) Uruchom `python3 agent.py` i sprawdź działanie.

## Styl kodu i konwencje
- Wcięcia: 4 spacje.
- Importy: standardowa biblioteka → zewnętrzne pakiety → lokalne moduły.
- Nazwy funkcji i modułów opisowe i spójne.

## Testy i weryfikacja zmian
W repo brak gotowych testów dla Lyry. Po zmianach:
- Uruchom `python3 agent.py`.
- Sprawdź działanie narzędzi, które modyfikowałeś.
- Zajrzyj do `logs/` jeśli pojawią się błędy.

## Commity i pull requesty
Nie ma ustalonej konwencji. Stosuj krótkie, zrozumiałe opisy, np.:
- `Dodaj narzędzie diagnostyki sieci`
- `Napraw błąd w routerze intencji`
W opisie PR napisz: co zmieniono i jak to sprawdzić.

## Konfiguracja i bezpieczeństwo
- `config.json` i pliki `*.json` ze stanem sterują działaniem. Zrób kopię przed większymi zmianami.
- Nie edytuj logów i środowisk (`venv/`, `.venv/`) bez wyraźnej potrzeby.
