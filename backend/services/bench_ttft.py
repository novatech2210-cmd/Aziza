#!/usr/bin/env python3
import time
import torch
import numpy as np
import argparse
import os
from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList, BitsAndBytesConfig

class TTFTTimer(StoppingCriteria):
    def __init__(self):
        self.start_time = None
        self.ttft = None

    def reset(self):
        self.start_time = time.perf_counter()
        self.ttft = None

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        if self.ttft is None and self.start_time is not None:
            self.ttft = (time.perf_counter() - self.start_time) * 1000
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter_path", type=str, default="")
    args = parser.parse_args()

    model_id = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
    hf_token = os.environ.get("HF_TOKEN")
    
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)
    bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)
    
    print("Loading model...")
    base_model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=bnb_config, device_map="auto", token=hf_token)
    
    if args.adapter_path:
        from peft import PeftModel
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(base_model, args.adapter_path)
    else:
        model = base_model
        
    model.eval()
    
    prompts = [
        ("ru", "Привет, как дела?"),
        ("uz_latin", "Salom, qalaysiz?"),
        ("uz_cyrillic", "Салом, қалайсиз?"),
    ] * 17  # 51 prompts total

    results = {"ru": [], "uz_latin": [], "uz_cyrillic": [], "all": []}
    
    timer = TTFTTimer()
    stopping_criteria = StoppingCriteriaList([timer])
    
    print("Starting benchmark...")
    for i, (lang, text) in enumerate(prompts):
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        timer.reset()
        
        with torch.no_grad():
            model.generate(**inputs, max_new_tokens=10, stopping_criteria=stopping_criteria, pad_token_id=tokenizer.eos_token_id)
            
        ttft = timer.ttft
        if ttft is None:
            # Fallback if stopping criteria didn't trigger
            ttft = (time.perf_counter() - timer.start_time) * 1000
            
        results[lang].append(ttft)
        results["all"].append(ttft)
        print(f"[{i+1}/51] {lang}: TTFT = {ttft:.2f} ms")
        
    print("\n--- TTFT Benchmark Results ---")
    for lang in ["ru", "uz_latin", "uz_cyrillic", "all"]:
        arr = np.array(results[lang])
        if len(arr) > 0:
            p50 = np.percentile(arr, 50)
            p95 = np.percentile(arr, 95)
            p99 = np.percentile(arr, 99)
            print(f"{lang.upper()}: p50={p50:.2f}ms | p95={p95:.2f}ms | p99={p99:.2f}ms")

if __name__ == "__main__":
    main()
