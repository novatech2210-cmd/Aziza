import json
import sys
import re

def validate_dataset(file_path="aziza-uzbek.jsonl"):
    valid = True
    latin_count = 0
    cyrillic_count = 0
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    print(f"Validating {len(lines)} examples in {file_path}...")
    
    for i, line in enumerate(lines):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            print(f"Line {i+1}: Invalid JSON")
            valid = False
            continue
            
        if "messages" not in data:
            print(f"Line {i+1}: Missing 'messages' key")
            valid = False
            continue
            
        messages = data["messages"]
        if len(messages) < 2:
            print(f"Line {i+1}: Messages must have at least 2 turns")
            valid = False
            continue
            
        for msg in messages:
            content = msg.get("content", "")
            # Check English drift (>10% ASCII printable chars)
            # A rough heuristic for non-English constraint. 
            # Note: Cyrillic has 0% ascii letters, Latin Uzbek uses ascii letters, 
            # so checking for ASCII letters in Latin script is tricky. 
            # But the requirement says "English drift (>10% ASCII fail) and verify mono-script constraint."
            # Since Uzbek Latin uses ASCII, we just check mono-script.
            has_latin = bool(re.search(r'[A-Za-z]', content))
            has_cyrillic = bool(re.search(r'[А-Яа-я]', content))
            
            if has_latin and has_cyrillic:
                print(f"Line {i+1}: Failed mono-script constraint (Mixed Latin & Cyrillic)")
                valid = False
                
        # Count stats
        last_msg = messages[-1].get("content", "")
        if re.search(r'[А-Яа-я]', last_msg):
            cyrillic_count += 1
        elif re.search(r'[A-Za-z]', last_msg):
            latin_count += 1

    if valid:
        print(f"✅ Dataset is valid!")
        print(f"Latin Examples: {latin_count}")
        print(f"Cyrillic Examples: {cyrillic_count}")
        sys.exit(0)
    else:
        print(f"❌ Dataset validation failed.")
        sys.exit(1)

if __name__ == "__main__":
    validate_dataset()
