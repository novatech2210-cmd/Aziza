import os
from transformers import AutoTokenizer

def audit_and_extend_tokenizer(model_id="Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24", output_dir="adapters/tokenizer-uz-extended"):
    print(f"Loading tokenizer from {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    # Test cases for Uzbek Latin and Cyrillic
    uzbek_latin = ["Oʻ", "oʻ", "Gʻ", "gʻ", "Sh", "sh", "Ch", "ch", "Ng", "ng"]
    uzbek_cyrillic = ["Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў"]

    all_chars = uzbek_latin + uzbek_cyrillic
    
    missing_chars = []
    print("\n--- Auditing Tokenizer Coverage ---")
    for char in all_chars:
        tokens = tokenizer.encode(char, add_special_tokens=False)
        # If a single character or digraph splits into more than 2 tokens, it's poorly represented.
        if len(tokens) > 2:
            print(f"Poor coverage for '{char}': splits into {len(tokens)} tokens -> {tokenizer.convert_ids_to_tokens(tokens)}")
            missing_chars.append(char)
        else:
            print(f"Good coverage for '{char}': {len(tokens)} tokens")

    if missing_chars:
        print(f"\nAdding missing chars to tokenizer: {missing_chars}")
        tokenizer.add_tokens(missing_chars)
        os.makedirs(output_dir, exist_ok=True)
        tokenizer.save_pretrained(output_dir)
        print(f"Extended tokenizer saved to {output_dir}")
    else:
        print("\nTokenizer has adequate coverage for Uzbek. No extension needed.")

if __name__ == "__main__":
    audit_and_extend_tokenizer()
