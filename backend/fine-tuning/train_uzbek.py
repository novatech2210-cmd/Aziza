import os
import json
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    BitsAndBytesConfig,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import (
    LoraConfig,
    TaskType,
    get_peft_model,
    prepare_model_for_kbit_training,
)

# ---------------------------------------------------------------------------
# LOCKED CONFIG (Do Not Change)
# ---------------------------------------------------------------------------
LOCKED_CONFIG = {
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
    "max_seq_length": 512,
    "batch_size": 4,
    "grad_accum_steps": 4,
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "lr_scheduler_type": "cosine",
    "quantization": "nf4",
    "double_quant": True,
    "compute_dtype": "float16",
}

def main():
    model_id = os.getenv("MODEL_ID", "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24")
    output_dir = "./aziza-adapter-final-uz"
    data_file = "aziza-uzbek.jsonl"
    
    print(f"Loading tokenizer {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    compute_dtype = torch.float16 if LOCKED_CONFIG["compute_dtype"] == "float16" else torch.bfloat16
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=LOCKED_CONFIG["double_quant"],
        bnb_4bit_quant_type=LOCKED_CONFIG["quantization"],
        bnb_4bit_compute_dtype=compute_dtype,
    )
    
    print(f"Loading model {model_id}...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=compute_dtype,
    )
    model = prepare_model_for_kbit_training(model)
    
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LOCKED_CONFIG["lora_r"],
        lora_alpha=LOCKED_CONFIG["lora_alpha"],
        lora_dropout=LOCKED_CONFIG["lora_dropout"],
        target_modules=LOCKED_CONFIG["target_modules"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    print(f"Loading dataset {data_file}...")
    dataset = load_dataset("json", data_files=data_file, split="train")
    
    # Shuffle and split
    dataset = dataset.shuffle(seed=42)
    split_ds = dataset.train_test_split(test_size=0.1)
    train_ds = split_ds["train"]
    eval_ds = split_ds["test"]
    
    def tokenize_fn(examples):
        texts = []
        for msgs in examples["messages"]:
            # Use model's chat template
            text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
            texts.append(text)
        return tokenizer(
            texts,
            truncation=True,
            max_length=LOCKED_CONFIG["max_seq_length"],
            padding=False,
        )
    
    print("Tokenizing dataset...")
    train_ds = train_ds.map(tokenize_fn, batched=True, remove_columns=train_ds.column_names)
    eval_ds = eval_ds.map(tokenize_fn, batched=True, remove_columns=eval_ds.column_names)
    
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=LOCKED_CONFIG["num_epochs"],
        per_device_train_batch_size=LOCKED_CONFIG["batch_size"],
        per_device_eval_batch_size=LOCKED_CONFIG["batch_size"],
        gradient_accumulation_steps=LOCKED_CONFIG["grad_accum_steps"],
        learning_rate=LOCKED_CONFIG["learning_rate"],
        lr_scheduler_type=LOCKED_CONFIG["lr_scheduler_type"],
        bf16=(LOCKED_CONFIG["compute_dtype"] == "bfloat16"),
        fp16=(LOCKED_CONFIG["compute_dtype"] == "float16"),
        warmup_ratio=0.03,
        save_steps=100,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=100,
        load_best_model_at_end=True,
        report_to="none",
        optim="paged_adamw_32bit",
        max_grad_norm=0.3,
        dataloader_num_workers=4,
    )
    
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
    )
    
    print("Starting training...")
    trainer.train()
    
    final_output_dir = os.path.join(output_dir, "final")
    os.makedirs(final_output_dir, exist_ok=True)
    trainer.model.save_pretrained(final_output_dir)
    tokenizer.save_pretrained(final_output_dir)
    print(f"Training complete. Adapter saved to {final_output_dir}")

if __name__ == "__main__":
    main()
