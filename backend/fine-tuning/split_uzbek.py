import json
import random
import os

with open('aziza-uzbek.jsonl', 'r') as f:
    lines = f.readlines()

random.shuffle(lines)
split_idx = int(len(lines) * 0.9)
train = lines[:split_idx]
val = lines[split_idx:]

os.makedirs('data_uzbek/uz-latn', exist_ok=True)
with open('data_uzbek/uz-latn/train.jsonl', 'w') as f:
    f.writelines(train)
with open('data_uzbek/uz-latn/val.jsonl', 'w') as f:
    f.writelines(val)
