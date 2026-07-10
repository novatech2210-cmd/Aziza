import json
import os
import argparse
import random

def assign_register(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    registers = ["academic", "professional", "colloquial"]
    
    for filename in os.listdir(input_dir):
        if not filename.endswith(".jsonl"): continue
        in_path = os.path.join(input_dir, filename)
        out_path = os.path.join(output_dir, filename)
        
        with open(in_path, "r") as fin, open(out_path, "w") as fout:
            for line in fin:
                data = json.loads(line)
                data["register"] = random.choice(registers)
                fout.write(json.dumps(data) + "\n")
        print(f"Assigned registers for {filename}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    assign_register(args.input, args.output)
