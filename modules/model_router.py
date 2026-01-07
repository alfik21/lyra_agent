import os
# Importujemy funkcję przeszukiwania pamięci z Twojego modułu pamięci
from modules.memory_ai import search_memory 
import socket
import requests
import json
from pathlib import Path
try:
    import openai
except Exception:
    openai = None

CONFIG_PATH = Path.home() / "lyra_agent" / "config.json"
LAST_STATS = None

def _load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _get_local_backend():
    cfg = _load_config()
    value = (cfg.get("local_backend") or os.environ.get("LYRA_BACKEND") or "ollama").lower()
    if value.startswith("llama"):
        return "llama"
    return value

def _get_cloud_model():
    cfg = _load_config()
    return cfg.get("default_cloud_model") or "gpt-5.1"

def _cloud_consent_state():
    cfg = _load_config()
    return (cfg.get("cloud_consent") or "ask").lower()

def get_last_stats():
    return LAST_STATS

def _ollama_detected(timeout=2):
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=timeout)
        if r.status_code != 200:
            return False
        data = r.json()
        return isinstance(data, dict) and "models" in data
    except Exception:
        return False

def query_ollama(prompt, model="mistral", timeout=90):
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        # Zwiększamy timeout do 30 sekund, bo Mistral może potrzebować chwili na start
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            try:
                prompt_n = data.get("prompt_eval_count") or 0
                prompt_ns = data.get("prompt_eval_duration") or 0
                gen_n = data.get("eval_count") or 0
                gen_ns = data.get("eval_duration") or 0
                prompt_tps = (prompt_n / (prompt_ns / 1e9)) if prompt_ns else None
                gen_tps = (gen_n / (gen_ns / 1e9)) if gen_ns else None
                global LAST_STATS
                LAST_STATS = {
                    "prompt_tps": prompt_tps,
                    "gen_tps": gen_tps,
                    "backend": "ollama"
                }
            except Exception:
                pass
            return data.get("response", "Błąd: Brak pola response")
        return f"Błąd Ollama: Status {response.status_code}"
    except Exception as e:
        return f"Błąd połączenia z Ollama: {str(e)}"

def query_llama_server(prompt, model=None, timeout=90):
    try:
        # Try llama.cpp /completion
        url = "http://127.0.0.1:11434/completion"
        payload = {"prompt": prompt, "n_predict": 256, "temperature": 0.7, "timings": True}
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            try:
                timings = data.get("timings") or {}
                prompt_tps = timings.get("prompt_per_second")
                gen_tps = timings.get("predicted_per_second")
                if prompt_tps is None or gen_tps is None:
                    prompt_n = timings.get("prompt_n") or 0
                    prompt_ms = timings.get("prompt_ms") or 0
                    gen_n = timings.get("predicted_n") or 0
                    gen_ms = timings.get("predicted_ms") or 0
                    prompt_tps = (prompt_n / (prompt_ms / 1000.0)) if prompt_ms else None
                    gen_tps = (gen_n / (gen_ms / 1000.0)) if gen_ms else None
                global LAST_STATS
                LAST_STATS = {"prompt_tps": prompt_tps, "gen_tps": gen_tps, "backend": "llama"}
            except Exception:
                pass
            text = data.get("content") or data.get("response") or ""
            if text:
                return text

        # Try OpenAI-compatible /v1/chat/completions
        url = "http://127.0.0.1:11434/v1/chat/completions"
        payload = {"model": "", "messages": [{"role": "user", "content": prompt}]}
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices") or []
            if choices and isinstance(choices, list):
                msg = choices[0].get("message") or {}
                text = msg.get("content") or ""
                if text:
                    return text

        # Try OpenAI-compatible /v1/completions
        url = "http://127.0.0.1:11434/v1/completions"
        payload = {"model": "", "prompt": prompt}
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices") or []
            if choices and isinstance(choices, list):
                text = choices[0].get("text") or ""
                if text:
                    return text

        if _ollama_detected():
            return "Błąd llama-server: ollama detected"
        return "Błąd llama-server: Status 404"
    except Exception as e:
        return f"Błąd połączenia z llama-server: {str(e)}"

def internet_ok():
    """Szybki test, czy jest połączenie z internetem (ping do Google DNS)."""
    try:
        # Próbuje połączyć się z portem 53 (DNS) u Google
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

def _query_openai(prompt, model_name=None, timeout=20):
    if not openai:
        return "Błąd API: brak biblioteki openai"
    if os.environ.get("LYRA_CLOUD_ONCE") == "1":
        pass
    else:
        consent = _cloud_consent_state()
        if consent == "never":
            return "Błąd API: zgoda wylaczona"
        if consent != "always":
            return "CONSENT_REQUIRED"
    cfg = _load_config()
    api_key = cfg.get("openai_api_key")
    if not api_key or "TWÓJ_KLUCZ" in api_key:
        return "Błąd API: brak klucza"
    model_name = model_name or _get_cloud_model()
    try:
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Jesteś Lyra, zaawansowany asystent AI."},
                {"role": "user", "content": prompt},
            ],
            timeout=timeout,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"Błąd API: {e}"

# Dalej idzie Twoja funkcja query_model...
# Reszta Twojego kodu query_model...
def query_model(prompt, local_model, remote_model, config, history):
    # Lyra próbuje najpierw sprawdzić, czy już o tym rozmawialiście
    try:
        mem_answer = search_memory(prompt)
        if mem_answer:
            # Jeśli znajdzie konkretną odpowiedź w pamięci, może jej użyć
            pass 
    except Exception as e:
        print(f"[DEBUG] Problem z pamięcią: {e}")
    
    # Dalsza część logiki wyboru modelu (Ollama / API)...

    # =====================
    # Tryb pracy
    # =====================
    STATE_PATH = os.path.expanduser("~/lyra_agent/system_state.json")
    mode = "auto"

    if os.path.exists(STATE_PATH):
        try:
            mode = json.load(open(STATE_PATH, "r", encoding="utf-8")).get("mode", "auto")
        except:
            mode = "auto"

    # =====================
    # 1. Pamięć
    # =====================
    mem_answer = search_memory(prompt)
    if mem_answer:
        return f"[Z pamięci] {mem_answer}", "memory"

    # =====================
    # 2. Offline wymuszony
    # =====================
    # POPRAWNA LOGIKA:
    if mode == "offline":
        backend = _get_local_backend()
        if backend == "llama":
            odpowiedz = query_llama_server(prompt, model=local_model, timeout=30)
            return odpowiedz, "llama"
        odpowiedz = query_ollama(prompt, local_model, timeout=30)
        return odpowiedz, "ollama"

    # =====================
    # 3. Lokalny model (Ollama)
    # =====================
    try:
        backend = _get_local_backend()
        if backend == "llama":
            local_resp = query_llama_server(prompt, model=local_model, timeout=30)
        else:
            local_resp = query_ollama(prompt, local_model, timeout=30)

        if local_resp and isinstance(local_resp, str) and local_resp.strip():
            # Jeśli backend zwrócił błąd, przejdź dalej do fallbacku
            if "błąd" not in local_resp.lower() and "error" not in local_resp.lower():
                return local_resp, "local"
    except:
        pass

    # =====================
    # 4. Tryb online → GPT
    # =====================
    allow_cloud = bool((config or {}).get("allow_cloud"))
    if allow_cloud and internet_ok():
        cloud_model = remote_model or _get_cloud_model()
        resp = _query_openai(prompt, cloud_model, timeout=20)
        if resp == "CONSENT_REQUIRED":
            return "[Zgoda GPT wymagana] Uzyj: zgoda gpt zawsze|raz|nie", "consent"
        if resp and "błąd api" not in resp.lower():
            return resp, "cloud"

    # =====================
    # 5. Brak internetu i brak lokalnego
    # =====================
    return "[Brak odpowiedzi] Offline + lokalny model nie działa.", "offline"
