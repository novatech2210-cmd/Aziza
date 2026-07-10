import json
import os
import glob
import uuid

input_dir = "/workspace/aziza-web/fine-tuning/dataset"
output_file = "/workspace/aziza-web/personaplex-finetune/data/aziza-bilingual/aziza-bilingual.jsonl"
os.makedirs(os.path.dirname(output_file), exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as out_f:
    for filepath in glob.glob(os.path.join(input_dir, "*.jsonl")):
        with open(filepath, 'r', encoding='utf-8') as in_f:
            for line in in_f:
                data = json.loads(line)
                
                # Extract user and assistant messages
                dialogue_lines = []
                system_prompt = "You are Aziza, a helpful bilingual AI assistant."
                for msg in data.get("messages", []):
                    if msg["role"] == "system":
                        system_prompt = msg["content"]
                    elif msg["role"] == "user":
                        dialogue_lines.append(f"CLIENT (User): {msg['content']}")
                    elif msg["role"] == "assistant":
                        dialogue_lines.append(f"BROKER (Aziza): {msg['content']}")
                
                record = {
                    "id": f"aziza-{uuid.uuid4().hex[:8]}",
                    "assistant_name": "Aziza",
                    "system_prompt": system_prompt,
                    "dialogue": "\n".join(dialogue_lines),
                    "context_injections": []
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + '\n')

print(f"Converted dataset saved to {output_file}")
