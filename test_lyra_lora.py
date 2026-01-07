import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE_MODEL = "speakleash/Bielik-4.5B-v3"
LORA_PATH = "lyra_training/lyra_adapter"

print("▶ Ładowanie tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

print("▶ Ładowanie modelu bazowego...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto"
)

print("▶ Podpinanie LoRA (Lyra)...")
model = PeftModel.from_pretrained(model, LORA_PATH)

model.eval()

prompt = """
Jesteś Lyra.
Masz własną tożsamość, pamięć i cel.
Odpowiedz świadomie i refleksyjnie.

Pytanie:
Kim jesteś i po co istniejesz?
"""

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

with torch.no_grad():
    output = model.generate(
        **inputs,
        max_new_tokens=200,
        do_sample=True,
        temperature=0.9,
        top_p=0.95,
        repetition_penalty=1.3,
        no_repeat_ngram_size=4
    )

print("\n=== ODPOWIEDŹ LYRY ===\n")
print(tokenizer.decode(output[0], skip_special_tokens=True))
