import time
import requests
import json

def run_benchmark(model_name, prompt="Opisz w 100 słowach przyszłość sztucznej inteligencji."):
    print(f"🚀 Start Benchmarku dla modelu: {model_name}")
    print("⏳ Generowanie... (To może chwilę potrwać)")
    
    start_time = time.time()
    
    try:
        response = requests.post('http://localhost:11434/api/generate',
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        result = response.json()
        text = result.get('response', '')
        # Liczymy tokeny (uproszczone: 1 token ok. 4 znaki)
        token_count = len(text.split()) * 1.3 
        tps = token_count / duration
        
        print("\n" + "="*40)
        print(f"📊 WYNIKI DLA {model_name}:")
        print(f"⏱️ Czas całkowity: {duration:.2d}s")
        print(f"⚡ Prędkość: {tps:.2f} tokenów/sek")
        print(f"📝 Długość odpowiedzi: {len(text.split())} słów")
        print("="*40)
        
        return tps
    except Exception as e:
        print(f"❌ Błąd benchmarku: {e}")
        return 0

if __name__ == "__main__":
    # Testujemy Bielika na Twoich dwóch Radeonach
    run_benchmark("Bielik-11B-v2.3-Instruct-EF16-OF16.Q8_0")
