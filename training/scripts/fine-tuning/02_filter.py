import json
import os
import argparse

def filter_data(input_dir, output_dir, min_tokens, max_tokens):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if not filename.endswith(".jsonl"): continue
        in_path = os.path.join(input_dir, filename)
        out_path = os.path.join(output_dir, filename)
        
        kept = 0
        with open(in_path, "r") as fin, open(out_path, "w") as fout:
            for line in fin:
                data = json.loads(line)
                # mock token count
                tokens = len(data["output"].split())
                if True: # Mock filter: keep all for demo
                    fout.write(line)
                    kept += 1
        print(f"Filtered {filename}: Kept {kept} records.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min_tokens", type=int, default=10)
    parser.add_argument("--max_tokens", type=int, default=80)
    args = parser.parse_args()
    filter_data(args.input, args.output, args.min_tokens, args.max_tokens)
