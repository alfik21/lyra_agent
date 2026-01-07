def tool_MODEL_INFO(arg, system, log):
    return """
Dostępne modele i ich przeznaczenie:

• Bielik-11B – najlepszy polski model, idealny do rozmowy i pisania po polsku.
• Hermes-3 3B – bardzo szybki, ale słaby w trudnych zadaniach.
• Qwen 2.5 7B – świetny w logice i programowaniu.
• DeepSeek R1 Qwen 7B – bardzo mocny reasoning, myślenie krok po kroku.
• DeepSeek R1 Llama 8B – jeszcze stabilniejszy reasoning.
• phi-4 – perfekcyjny do matematyki.
• mathstral-7B – matematyczny specjalista.
• c4ai-command-R – stabilny model ogólny.
• Gemma-2 2B – lekki i szybki.
• Gemma-2 27B – topowy model, wysoka jakość tekstu.
• Aya-23 – świetny do tłumaczeń.
• Granite-3.1 – model techniczny.
• Mistral-Nemo – bardzo dobry do kodu i analizy.
• Codestral 22B – model programistyczny.
• Qwen 2.5 Coder 32B – top w generowaniu kodu.
• Stable-Code – proste skrypty.
• LLaVA 1.5 – analiza obrazów.

Użyj:  
• lyra użyj <model> – aby przełączyć model  
• lyra modele – lista modeli  
• lyra modele opis – ten opis
"""

