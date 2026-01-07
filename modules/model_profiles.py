# modules/model_profiles.py

#from modules.model_profiles import choose_best_model
from modules.online_bridge import call_online_api

def process_with_failover(user_prompt):
    # 1. Pobierz parę modeli z Twojego profilu
    local_model, cloud_model = choose_best_model(user_prompt)
    
    # 2. PRÓBA LOKALNA (Z390 / Ollama)
    try:
        # Ustawiamy timeout, żeby Lyra nie wisiała 90 sekund
        response = call_ollama(local_model, user_prompt, timeout=30)
        
        if "timeout" in response.lower() or "error" in response.lower():
            raise Exception("Lokalny model zbyt wolny lub błąd")
            
        return response, "LOCAL"

    except Exception:
        # 3. PRÓBA ONLINE (Twój gpt-5.1)
        print(f"⚠️ {local_model} nie odpowiada. Ratuję się przez {cloud_model}...")
        response = call_online_api(cloud_model, user_prompt)
        return response, "CLOUD"

def choose_best_model(prompt: str):
    """
    Zwraca tuple:
       (local_model_name, cloud_model_name)

    agent.py zakłada, że ta funkcja MA DOKŁADNIE 1 argument!
    """

    p = prompt.lower()

    # ===========================
    # Modele specjalistyczne
    # ===========================

    # analiza zdjęć
    if "zdjęcie" in p or "obraz" in p or "foto" in p:
        return "llava-v1.5-7b-Q4_0", "gpt-4o"

    # kod / programowanie
    if "kod" in p or "python" in p or "program" in p or "skrypt" in p:
        return "qwen2.5-coder-3b-instruct-q4_0", "gpt-5.1"

    # reasoning / trudna logika
    if "wyjaśnij" in p or "logicznie" in p or "rozumowanie" in p or "analiza" in p:
        return "deepseek-r1-distill-qwen-7b-q4_k_m", "gpt-5.1"

    # ogólny polski model (szybki)
    if any(pol in p for pol in ["napisz", "polski", "tłumacz", "wyjaśnij mi"]):
        return "hermes-3-llama-3.2-3b.q4_k_m", "gpt-5.1"

    # domyślny fallback
    return "gemma-2-2b-it-q4_k_m", "gpt-5.1"
