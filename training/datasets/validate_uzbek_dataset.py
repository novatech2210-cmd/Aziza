#!/usr/bin/env python3
import json
import sys

def validate(file_path):
    valid_count = 0
    latin_count = 0
    cyrillic_count = 0
    fail_count = 0

    UZBEK_LATIN = ["Oʻ", "oʻ", "Gʻ", "gʻ", "Sh", "sh", "Ch", "ch", "Ng", "ng"]
    UZBEK_CYRILLIC = ["Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў"]

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                try:
                    data = json.loads(line.strip())
                except json.JSONDecodeError:
                    print(f"FAIL: Invalid JSON on line {line_no}")
                    fail_count += 1
                    continue

                if "messages" not in data:
                    print(f"FAIL: Missing 'messages' key on line {line_no}")
                    fail_count += 1
                    continue
                
                messages = data["messages"]
                if len(messages) < 2:
                    print(f"FAIL: Less than 2 turns on line {line_no}")
                    fail_count += 1
                    continue

                sys_prompt = messages[0].get("content", "")
                if "Aziza" not in sys_prompt and "Азиза" not in sys_prompt:
                    print(f"FAIL: Persona injection missing Aziza on line {line_no}")
                    fail_count += 1
                    continue
                
                # Check script and English drift
                assistant_chars = 0
                ascii_chars = 0
                has_latin = False
                has_cyrillic = False

                for m in messages:
                    if m["role"] == "assistant":
                        content = m["content"]
                        assistant_chars += len(content)
                        for char in content:
                            if 32 <= ord(char) <= 126 and not char.isdigit() and not char.isspace() and char not in '.,!?()[]{}"\'-:;':
                                ascii_chars += 1
                        
                        if any(l in content for l in UZBEK_LATIN):
                            has_latin = True
                        if any(c in content for c in UZBEK_CYRILLIC):
                            has_cyrillic = True

                if has_cyrillic and not has_latin:
                    if assistant_chars > 0 and (ascii_chars / assistant_chars) > 0.1:
                        print(f"FAIL: English drift detected on line {line_no}")
                        fail_count += 1
                        continue
                
                if has_latin and has_cyrillic:
                    print(f"FAIL: Mixed scripts on line {line_no}")
                    fail_count += 1
                    continue

                if has_latin:
                    latin_count += 1
                elif has_cyrillic:
                    cyrillic_count += 1
                else:
                    # Could be generic, but let's assume it failed to identify if neither
                    print(f"FAIL: No specific Uzbek characters found on line {line_no}")
                    fail_count += 1
                    continue

                valid_count += 1

    except FileNotFoundError:
        print(f"FAIL: File not found {file_path}")
        sys.exit(1)

    print(f"Total lines: {valid_count + fail_count}")
    print(f"Latin count: {latin_count}")
    print(f"Cyrillic count: {cyrillic_count}")
    print(f"Failed lines: {fail_count}")

    if fail_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 validate_uzbek_dataset.py <dataset.jsonl>")
        sys.exit(1)
    validate(sys.argv[1])
