"""
Dataset preparation for Moshi fine-tuning.
"""
import json
import argparse
import random
from pathlib import Path
from typing import List, Dict

def process_dataset(input_path: str, output_dir: str, lang: str):
    print(f"Processing {input_path} for language: {lang}")
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: {input_path} not found.")
        return

    out_dir = Path(output_dir) / lang
    out_dir.mkdir(parents=True, exist_ok=True)

    records: List[Dict] = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                # Ensure it has instruction, input, output
                if "instruction" in data and "output" in data:
                    records.append(data)
            except json.JSONDecodeError:
                continue

    if not records:
        print("No valid records found.")
        return

    # Shuffle and split 90/5/5
    random.shuffle(records)
    total = len(records)
    train_end = int(total * 0.9)
    val_end = int(total * 0.95)

    train_records = records[:train_end]
    val_records = records[train_end:val_end]
    test_records = records[val_end:]

    def save_split(split_records, filename):
        with open(out_dir / filename, 'w', encoding='utf-8') as f:
            for r in split_records:
                # Moshi fine-tuning format
                moshi_record = {
                    "text": f"User: {r.get('instruction', '')} {r.get('input', '')}\nAziza: {r.get('output', '')}"
                }
                f.write(json.dumps(moshi_record, ensure_ascii=False) + '\n')

    save_split(train_records, 'train.jsonl')
    save_split(val_records, 'val.jsonl')
    save_split(test_records, 'test.jsonl')

    avg_len = sum(len(r.get("output", "")) for r in records) / total

    print(f"--- Dataset Statistics ({lang}) ---")
    print(f"Total pairs: {total}")
    print(f"Train: {len(train_records)} | Val: {len(val_records)} | Test: {len(test_records)}")
    print(f"Avg response length: {avg_len:.1f} chars")
    
    # Minimum checks
    mins = {
        "ru": 5000,
        "uz-latn": 3000,
        "uz-cyrl": 3000,
        "en": 2000
    }
    required = mins.get(lang, 0)
    if total < required:
        print(f"WARNING: Dataset size ({total}) is below the required minimum of {required} for {lang}!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to raw JSONL file")
    parser.add_argument("--output_dir", default="./data", help="Output directory")
    parser.add_argument("--lang", required=True, choices=["ru", "uz-latn", "uz-cyrl", "en"], help="Language code")
    args = parser.parse_args()
    
    process_dataset(args.input, args.output_dir, args.lang)
