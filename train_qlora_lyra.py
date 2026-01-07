import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer
)
from peft import (
    LoraConfig,
    get_peft_model,
    #prepare_model_for_kbit_training
)

# ====== KONFIG ======
BASE_MODEL = "speakleash/Bielik-4.5B-v3"
DATASET_PATH = "dataset_lyra.jsonl"
OUTPUT_DIR = "lyra_adapter"

MAX_LEN = 1024

# ====== TOKENIZER ======
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token

# ====== MODEL ======
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    #load_in_8bit=True,
    device_map="auto"
)

#model = prepare_model_for_kbit_training(model)

# ====== LoRA CONFIG ======
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "v_proj"]
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# ====== DATASET ======
dataset = load_dataset("json", data_files=DATASET_PATH, split="train")

def preprocess(example):
    prompt = (
        f"### Instrukcja:\n{example['instruction']}\n"
        f"### Input:\n{example['input']}\n"
        f"### Odpowiedź:\n{example['output']}"
    )
    tokens = tokenizer(
        prompt,
        truncation=True,
        max_length=MAX_LEN,
        padding="max_length"
    )
    tokens["labels"] = tokens["input_ids"].copy()
    return tokens

dataset = dataset.map(preprocess, remove_columns=dataset.column_names)
dataset.set_format("torch")

# ====== TRAINING ======
args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    num_train_epochs=3,
    learning_rate=2e-4,
    #fp16=True,
    logging_steps=10,
    save_strategy="epoch",
    report_to="none"
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=dataset,
    tokenizer=tokenizer
)

trainer.train()

# ====== SAVE ADAPTER ======
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("✅ Adapter Lyra zapisany w:", OUTPUT_DIR)

