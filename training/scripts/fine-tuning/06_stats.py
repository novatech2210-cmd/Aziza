import json
import os
import argparse

def generate_stats(input_dir, output_file):
    stats = {}
    total_pairs = 0
    
    for filename in os.listdir(input_dir):
        if not filename.endswith(".jsonl"): continue
        in_path = os.path.join(input_dir, filename)
        
        count = 0
        with open(in_path, "r") as fin:
            for line in fin:
                count += 1
        
        lang_reg = filename.replace(".jsonl", "")
        stats[lang_reg] = count
        total_pairs += count
        
    with open(output_file, "w") as fout:
        fout.write("# Dataset Generation Report\n\n")
        fout.write(f"Total Quality Pairs Generated: **{total_pairs}**\n\n")
        fout.write("## Breakdown by Language and Register\n\n")
        fout.write("| Combination | Pairs |\n")
        fout.write("|---|---|\n")
        for k, v in stats.items():
            fout.write(f"| {k} | {v} |\n")
            
    print(f"Stats saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    generate_stats(args.input, args.output)
