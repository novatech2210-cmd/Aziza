import json
import os
import argparse
import random

def generate_mock_data(langs, output_dir, total_pairs=30000):
    os.makedirs(output_dir, exist_ok=True)
    pairs_per_lang = total_pairs // len(langs)
    
    samples = {
        "ru": "Привет, меня зовут Азиза. Как я могу вам помочь сегодня?",
        "uz_latin": "Salom, mening ismim Aziza. Qanday yordam bera olaman?",
        "uz_cyrillic": "Салом, менинг исмим Азиза. Қандай ёрдам бера оламан?"
    }
    
    for lang in langs:
        file_path = os.path.join(output_dir, f"{lang}_raw.jsonl")
        print(f"Generating {pairs_per_lang} pairs for {lang}...")
        with open(file_path, "w") as f:
            for i in range(pairs_per_lang):
                # Add some random length variance
                text = samples[lang] * random.randint(1, 3)
                record = {
                    "instruction": f"Generate response in {lang}",
                    "input": f"User query {i}",
                    "output": text,
                    "lang": lang
                }
                f.write(json.dumps(record) + "\n")
        print(f"Saved {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", nargs="+", required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()
    
    generate_mock_data(args.langs, args.output)
