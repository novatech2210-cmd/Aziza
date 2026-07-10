import json
import os
import argparse

def format_dataset(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    for filename in os.listdir(input_dir):
        if not filename.endswith(".jsonl"): continue
        in_path = os.path.join(input_dir, filename)
        
        with open(in_path, "r") as fin:
            for line in fin:
                data = json.loads(line)
                lang = data["lang"]
                reg = data["register"]
                
                # Split files based on lang and register, as expected by train.py
                out_filename = f"{lang}_{reg}.jsonl"
                out_path = os.path.join(output_dir, out_filename)
                
                hf_format = {
                    "messages": [
                        {"role": "system", "content": "You are Aziza, a helpful AI."},
                        {"role": "user", "content": data["input"]},
                        {"role": "assistant", "content": data["output"]}
                    ],
                    "language": lang,
                    "register": reg
                }
                
                with open(out_path, "a") as fout:
                    fout.write(json.dumps(hf_format) + "\n")
                    
    print(f"Formatted datasets into {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    format_dataset(args.input, args.output)
