import torch
import json
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import argparse

def evaluate():
    model_id = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
    adapter_path = "./aziza-adapter-final-uz/final"

    print(f"Loading tokenizer {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    
    print(f"Loading base model {model_id}...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    
    print(f"Loading adapter {adapter_path}...")
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()

    test_cases = [
        {
            "system": "Sen Aziza ismli raqamli yordamchisan. Har doim samimiy va to'g'ri javob ber.",
            "user": "Matematika: 5 karra 5 nechchi?",
            "expected": ["25", "yigirma", "besh"]
        },
        {
            "system": "Sen Aziza ismli raqamli yordamchisan. Har doim samimiy va to'g'ri javob ber.",
            "user": "Salom",
            "expected": ["assalomu", "alaykum", "yordam"]
        },
        {
            "system": "Sen Aziza ismli raqamli yordamchisan. Har doim samimiy va to'g'ri javob ber.",
            "user": "Sen kimsan?",
            "expected": ["aziza", "yordamchi"]
        },
        {
            "system": "Sen Aziza ismli raqamli yordamchisan. Har doim samimiy va to'g'ri javob ber.",
            "user": "Ertaga havo qanday bo'ladi?",
            "expected": ["havo", "bulutli", "issiq"]
        },
        {
            "system": "Sen Aziza ismli raqamli yordamchisan. Har doim samimiy va to'g'ri javob ber.",
            "user": "Menga she'r aytib ber",
            "expected": ["she'r", "bahor", "quvonch"]
        },
        {
            "system": "Сен Азиза исмли рақамли ёрдамчисан. Ҳар доим самимий ва тўғри жавоб бер.",
            "user": "Математика: 5 карра 5 неччи?",
            "expected": ["25", "йигирма", "беш"]
        },
        {
            "system": "Сен Азиза исмли рақамли ёрдамчисан. Ҳар доим самимий ва тўғри жавоб бер.",
            "user": "Салом",
            "expected": ["ассалому", "алайкум", "ёрдам"]
        },
        {
            "system": "Сен Азиза исмли рақамли ёрдамчисан. Ҳар доим самимий ва тўғри жавоб бер.",
            "user": "Сен кимсан?",
            "expected": ["азиза", "ёрдамчи"]
        },
        {
            "system": "Сен Азиза исмли рақамли ёрдамчисан. Ҳар доим самимий ва тўғри жавоб бер.",
            "user": "Эртага ҳаво қандай бўлади?",
            "expected": ["ҳаво", "булутли", "иссиқ"]
        },
        {
            "system": "Сен Азиза исмли рақамли ёрдамчисан. Ҳар доим самимий ва тўғри жавоб бер.",
            "user": "Менга шеър айтиб бер",
            "expected": ["шеър", "баҳор", "қувонч"]
        }
    ]

    correct = 0
    total = len(test_cases)

    for i, case in enumerate(test_cases):
        messages = [
            {"role": "system", "content": case["system"]},
            {"role": "user", "content": case["user"]}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to("cuda")
        
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=50, pad_token_id=tokenizer.eos_token_id)
        
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        
        print(f"\n--- Test Case {i+1} ---")
        print(f"User: {case['user']}")
        print(f"Response: {response}")
        
        # Check if any expected keyword is in the response (case-insensitive)
        response_lower = response.lower()
        if any(kw.lower() in response_lower for kw in case["expected"]):
            print("Status: PASS")
            correct += 1
        else:
            print(f"Status: FAIL (Expected one of: {case['expected']})")

    accuracy = (correct / total) * 100
    print(f"\nFinal Accuracy: {accuracy:.2f}%")
    
    if accuracy >= 80:
        print("Benchmark passed!")
        exit(0)
    else:
        print("Benchmark failed!")
        exit(1)

if __name__ == "__main__":
    evaluate()
