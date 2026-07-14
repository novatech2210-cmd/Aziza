import time
import torch
import json
from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList
from peft import PeftModel

class TTFTTimer(StoppingCriteria):
    def __init__(self):
        self.start_time = 0.0
        self.ttft = 0.0
        self.first_token_seen = False

    def reset(self):
        self.start_time = time.perf_counter()
        self.ttft = 0.0
        self.first_token_seen = False

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        if not self.first_token_seen:
            self.ttft = time.perf_counter() - self.start_time
            self.first_token_seen = True
        return False

def run_benchmark(model, tokenizer, prompts, n_runs=30):
    timer = TTFTTimer()
    stopping_criteria = StoppingCriteriaList([timer])
    
    latencies = []
    
    # Warmup
    prompt = prompts[0]
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        model.generate(**inputs, max_new_tokens=5, pad_token_id=tokenizer.eos_token_id)
        
    for i in range(n_runs):
        prompt = prompts[i % len(prompts)]
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to("cuda")
                
        timer.reset()
        with torch.no_grad():
            model.generate(**inputs, max_new_tokens=5, stopping_criteria=stopping_criteria, pad_token_id=tokenizer.eos_token_id)
            
        latencies.append(timer.ttft * 1000)
    
    latencies.sort()
    
    p50 = latencies[len(latencies)//2]
    p95 = latencies[int(len(latencies)*0.95)]
    p99 = latencies[int(len(latencies)*0.99)]
    
    print(f"p50: {p50:.2f} ms")
    print(f"p95: {p95:.2f} ms")
    print(f"p99: {p99:.2f} ms")
    return {"p50": p50, "p95": p95, "p99": p99}

def main():
    model_id = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
    adapters = {
        
        "uz": "./aziza-adapter-final-uz/final",
    }
    
    prompts = {
        "ru": ["Привет", "Как дела?", "Расскажи мне о своих возможностях.", "Что такое искусственный интеллект?"],
        "uz-latin": ["Salom", "Sen kimsan?", "Ertaga havo qanday bo'ladi?", "Menga she'r aytib ber"],
        "uz-cyrillic": ["Салом", "Сен кимсан?", "Эртага ҳаво қандай бўлади?", "Менга шеър айтиб бер"]
    }
    
    print(f"Loading tokenizer {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    print(f"Loading base model {model_id}...")
    base_model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.float16, device_map="auto"
    )

    results = {}
    
    for lang, path in adapters.items():
        print(f"\nLoading adapter {path} for {lang}...")
        model = PeftModel.from_pretrained(base_model, path)
        model.eval()
        
        if lang == "ru":
            print("\n--- TTFT Benchmark for Russian ---")
            results["ru"] = run_benchmark(model, tokenizer, prompts["ru"], n_runs=20)
        elif lang == "uz":
            print("\n--- TTFT Benchmark for Uzbek Latin ---")
            results["uz-latin"] = run_benchmark(model, tokenizer, prompts["uz-latin"], n_runs=20)
            print("\n--- TTFT Benchmark for Uzbek Cyrillic ---")
            results["uz-cyrillic"] = run_benchmark(model, tokenizer, prompts["uz-cyrillic"], n_runs=20)
            
        model.unload()

    with open("bench_ttft_report.txt", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nBenchmark complete. Results saved to bench_ttft_report.txt")

if __name__ == "__main__":
    main()
