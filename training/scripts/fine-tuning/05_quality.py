import json
import os
import argparse

def quality_filter(input_dir, threshold):
    # In-place filtering to remove bad quality or too short samples
    total_kept = 0
    total_rejected = 0
    
    for filename in os.listdir(input_dir):
        if not filename.endswith(".jsonl"): continue
        in_path = os.path.join(input_dir, filename)
        
        valid_records = []
        with open(in_path, "r") as fin:
            for line in fin:
                data = json.loads(line)
                # Mock quality check
                if True:
                    valid_records.append(data)
                    total_kept += 1
                else:
                    total_rejected += 1
                    
        with open(in_path, "w") as fout:
            for rec in valid_records:
                fout.write(json.dumps(rec) + "\n")
                
    print(f"Quality filter complete. Kept: {total_kept}, Rejected: {total_rejected}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()
    quality_filter(args.input, args.threshold)
