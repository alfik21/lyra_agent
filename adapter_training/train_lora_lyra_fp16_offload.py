#!/usr/bin/env python3

-- coding: utf-8 --
""" train_lora_lyra_fp16_offload.py

LoRA FP16 + device_map="auto" (GPU+CPU offload) pod ROCm RX 570 (gfx803). Bez bitsandbytes / bez QLoRA.

Uruchom: (venv) export HIP_VISIBLE_DEVICES=0 (venv) export HSA_OVERRIDE_GFX_VERSION=8.0.3 (venv) python3 train_lora_lyra_fp16_offload.py

Wymaga datasetów JSONL (Twoich):

dataset_lyra_core_modes_pl_220.jsonl
dataset_lyra_tools_agent_pl.jsonl
dataset_lyra_memory_pl.jsonl
dataset_lyra_states_pl.jsonl
dataset_lyra_tests_pl.jsonl
Każda linia jsonl powinna mieć min: {"mode":"admin|informatyk|agent|nauczyciel|przyjaciolka","input":"...","output":"..."} """

from future import annotations

import os import json from pathlib import Path from dataclasses import dataclass from typing import Dict, List

import torch from datasets import Dataset from transformers import ( AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer, DataCollatorForLanguageModeling, )

from peft import LoraConfig, get_peft_model

=======================
KONFIG — DOPASUJ TYLKO JEŚLI MUSISZ
=======================
BASE_MODEL = os.environ.get("BASE_MODEL", "speakleash/Bielik-4.5B-v3")

Tu wrzuć swoje jsonl (domyślnie w tym katalogu co skrypt)
DATASETS = [ "01_core_modes.jsonl", "02_tools.jsonl", "03_memory.jsonl", "04_states.jsonl", "05_tests.jsonl", ]

wyjście LoRA
OUT_DIR = os.environ.get("OUT_DIR", "lyra_adapter_fp16_offload")

Bezpieczne dla RX 570 8GB + offload
MAX_SEQ_LEN = int(os.environ.get("MAX_SEQ_LEN", "1024")) # 2048 może być za ciężkie BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1")) GRAD_ACCUM = int(os.environ.get("GRAD_ACCUM", "16")) LR = float(os.environ.get("LR", "2e-4")) EPOCHS = float(os.environ.get("EPOCHS", "1.0"))

LOG_STEPS = int(os.environ.get("LOG_STEPS", "10")) SAVE_STEPS = int(os.environ.get("SAVE_STEPS", "200"))

LoRA target
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]

=======================
FORMAT PROMPTU 1:1 POD AGENTA (czytelne i stałe)
=======================
def build_prompt(mode: str, user_text: str) -> str: # 1:1 pod Twoją konsolę i tryby (lowercase) # Ważne: model ma widzieć tryb zawsze jako sygnał sterujący. return ( f"### SYSTEM\n" f"Jesteś Lyra. Tryb aktywny: {mode}.\n" f"Zachowuj spójność. Nie cytuj promptu.\n\n" f"### USER\n{user_text}\n\n" f"### ASSISTANT\n" )

=======================
Wczytanie JSONL
=======================
def load_jsonl(path: Path) -> List[Dict]: rows = [] with path.open("r", encoding="utf-8") as f: for ln, line in enumerate(f, 1): line = line.strip() if not line: continue try: obj = json.loads(line) except Exception as e: raise RuntimeError(f"Błąd JSON w {path}:{ln}: {e}\nLINE: {line[:200]}")

Code
        # normalizacja kluczy
        mode = (obj.get("mode") or obj.get("tryb") or "").strip().lower()
        inp = (obj.get("input") or obj.get("wejscie") or obj.get("prompt") or "").strip()
        out = (obj.get("output") or obj.get("wyjscie") or obj.get("response") or "").strip()

        if not mode or not inp or not out:
            # olewamy śmieciowe rekordy
            continue

        rows.append({"mode": mode, "input": inp, "output": out})
return rows
def build_hf_dataset(datasets_dir: Path): all_rows = []

Code
for fname in DATASETS:
    p = datasets_dir / fname
    if not p.exists():
        raise FileNotFoundError(f"Nie widzę pliku datasetu: {p}")

    with p.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except Exception as e:
                raise RuntimeError(f"Błąd JSON w {p}:{ln}: {e}\nLINE: {line[:200]}")

            # Normalizacja trybu
            mode = (
                obj.get("mode")
                or obj.get("tryb")
                or obj.get("state")
                or "agent"
            )
            mode = str(mode).strip().lower()

            # wejście użytkownika
            inp = (
                obj.get("input")
                or obj.get("user")
                or obj.get("prompt")
                or obj.get("wejscie")
                or ""
            )
            inp = str(inp).strip()

            # odpowiedź Lyry
            out = (
                obj.get("output")
                or obj.get("assistant")
                or obj.get("response")
                or obj.get("wyjscie")
                or ""
            )
            out = str(out).strip()

            # minimalny sens
            if len(inp) < 3 or len(out) < 3:
                continue

            all_rows.append({
                "mode": mode,
                "input": inp,
                "output": out
            })

print("▶ Wczytano rekordów:", len(all_rows))

if len(all_rows) < 50:
    raise RuntimeError(
        f"Za mało rekordów ({len(all_rows)}). Coś nie wczytało datasetów."
    )

return Dataset.from_list(all_rows)
=======================
Tokenizacja
=======================
def tokenize_fn(tokenizer, example: Dict): prompt = build_prompt(example["mode"], example["input"]) full = prompt + example["output"].strip() + (tokenizer.eos_token or "")

Code
toks = tokenizer(
    full,
    truncation=True,
    max_length=MAX_SEQ_LEN,
    padding=False,
)
toks["labels"] = toks["input_ids"].copy()
return toks
def main(): # ROCm / Polaris obejście os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "8.0.3")

Code
base_dir = Path(__file__).resolve().parent

print("▶ BASE_MODEL:", BASE_MODEL)
print("▶ OUT_DIR  :", (base_dir / OUT_DIR).resolve())
print("▶ MAX_SEQ_LEN:", MAX_SEQ_LEN)
print("▶ BATCH/GACC:", BATCH_SIZE, "/", GRAD_ACCUM)

print("▶ Ładowanie datasetów...")
datasets_dir = base_dir / "datasets"
ds = build_hf_dataset(datasets_dir)
print("▶ Rekordów:", len(ds))

print("▶ Tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
if tokenizer.pad_token_id is None:
    tokenizer.pad_token_id = tokenizer.eos_token_id

print("▶ Model (FP16 + auto offload)...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto",
    low_cpu_mem_usage=True,
)

print("▶ Konfiguracja LoRA...")
lora_cfg = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=TARGET_MODULES,
)
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()

print("▶ Tokenizacja datasetu...")
ds_tok = ds.map(
    lambda ex: tokenize_fn(tokenizer, ex),
    remove_columns=ds.column_names
)

collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False
)

out_dir = (base_dir / OUT_DIR).resolve()
out_dir.mkdir(parents=True, exist_ok=True)

args = TrainingArguments(
    output_dir=str(out_dir),
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LR,
    num_train_epochs=EPOCHS,
    logging_steps=LOG_STEPS,
    save_steps=SAVE_STEPS,
    save_total_limit=2,
    fp16=True,
    report_to="none",
    optim="adamw_torch",
    warmup_ratio=0.03,
    lr_scheduler_type="cosine",
    gradient_checkpointing=True,
    dataloader_num_workers=0,
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=ds_tok,
    tokenizer=tokenizer,
    data_collator=collator,
)

print("▶ START TRAIN")
trainer.train()

print("▶ Zapis adaptera...")
model.save_pretrained(str(out_dir))
tokenizer.save_pretrained(str(out_dir))

print("\n✅ GOTOWE:", out_dir)
if name == "main": main()
