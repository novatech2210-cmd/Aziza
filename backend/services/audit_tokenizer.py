import sentencepiece as spm
import sys

def audit_uzbek_coverage(model_path: str):
    print(f"Auditing Tokenizer: {model_path}")
    try:
        sp = spm.SentencePieceProcessor()
        sp.load(model_path)
    except Exception as e:
        print(f"Error loading tokenizer: {e}")
        sys.exit(1)

    uzbek_latin = ["Oʻ", "oʻ", "Gʻ", "gʻ"]
    uzbek_cyrillic = ["Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў"]
    
    print("\n--- Uzbek Latin Special Graphemes ---")
    for char in uzbek_latin:
        tokens = sp.encode_as_ids(char)
        token_pieces = sp.encode_as_pieces(char)
        print(f"'{char}' -> Tokens: {tokens} | Pieces: {token_pieces} (Length: {len(tokens)})")
        
    print("\n--- Uzbek Cyrillic Special Characters ---")
    for char in uzbek_cyrillic:
        tokens = sp.encode_as_ids(char)
        token_pieces = sp.encode_as_pieces(char)
        print(f"'{char}' -> Tokens: {tokens} | Pieces: {token_pieces} (Length: {len(tokens)})")

if __name__ == "__main__":
    audit_uzbek_coverage("/root/aziza-build/model_cache/models--kyutai--moshika-pytorch-bf16/snapshots/a49141e28b3d9c947cf9aa5314431e1b11cbd2f5/tokenizer_spm_32k_3.model")
