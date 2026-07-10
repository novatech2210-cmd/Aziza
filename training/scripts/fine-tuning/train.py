import os
import argparse
import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from trl import SFTTrainer, SFTConfig

def main(lang, register, output_dir, data_file):
    print(f"Training adapter for {lang} - {register}...")
    
    # Load dataset
    dataset = load_dataset("json", data_files={"train": data_file})
    # Since it's a mock training for validation, we'll split a small val set
    dataset = dataset["train"].train_test_split(test_size=0.05)
    
    # QLoRA configs (LOCKED from spec)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, 
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, 
        bnb_4bit_compute_dtype=torch.float16
    )
    
    model_id = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24" # Using local env model instead of NVIDIA one for test
    model = AutoModelForCausalLM.from_pretrained(
        model_id, 
        quantization_config=bnb_config, 
        device_map="auto"
    )
    
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        
    lora_cfg = LoraConfig(
        r=16, 
        lora_alpha=32, 
        target_modules=["q_proj","v_proj","k_proj","o_proj"],
        lora_dropout=0.05, 
        bias="none", 
        task_type=TaskType.CAUSAL_LM
    )
    
    model = get_peft_model(model, lora_cfg)
    
    training_args = SFTConfig(
        output_dir=output_dir,
        max_seq_length=512,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        max_steps=10, # Reduced to 1 for quick validation
        lr_scheduler_type="cosine",
        warmup_steps=100,
        logging_steps=10,
        save_strategy="epoch",
        dataset_text_field="messages"
    )
    
    def format_func(example):
        return [tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)]
    
    trainer = SFTTrainer(
        model=model, 
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"], 
        args=training_args,
        formatting_func=format_func
    )
    
    print("Starting training...")
    trainer.train()
    
    print(f"Saving to {output_dir}...")
    trainer.model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", required=True)
    parser.add_argument("--register", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--data_file", required=True)
    args = parser.parse_args()
    main(args.lang, args.register, args.output, args.data_file)
