import json
import sentencepiece
from huggingface_hub import hf_hub_download
import argparse

TEST_STRINGS = {
    "ru":      "Привет, меня зовут Азиза. Как я могу вам помочь сегодня?",
    "uz-latn": "Salom, mening ismim Aziza. Qanday yordam bera olaman?",
    "uz-cyrl": "Салом, менинг исмим Азиза. Қандай ёрдам бера оламан?",
    "en":      "Hello, my name is Aziza. How can I help you today?",
}

REQUIRED_CHARS = {
    "uz-latn": ["Oʻ", "oʻ", "Gʻ", "gʻ"],
    "uz-cyrl": ["Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў"],
    "ru":      ["Ё", "ё"],
}

def audit():
    from moshi.models import loaders
    import os
    print("Downloading/Locating Moshi tokenizer from HF Hub...")
    # Get token from env if needed
    hf_token = os.environ.get("HF_TOKEN")
    tokenizer_path = hf_hub_download(loaders.DEFAULT_REPO, loaders.TEXT_TOKENIZER_NAME, token=hf_token)
    sp = sentencepiece.SentencePieceProcessor(tokenizer_path)
    
    results = {}
    vocab_size = sp.get_piece_size()
    
    for lang, text in TEST_STRINGS.items():
        tokens = sp.encode_as_ids(text)
        decoded = sp.decode_ids(tokens)
        
        coverage = sum(1 for t in tokens if t < vocab_size) / len(tokens) if len(tokens) > 0 else 0
        roundtrip_ok = (decoded.strip() == text.strip())
        
        special_ok = True
        unk_id = sp.unk_id()
        for c in REQUIRED_CHARS.get(lang, []):
            encoded_c = sp.encode_as_ids(c)
            if len(encoded_c) == 1 and encoded_c[0] == unk_id:
                special_ok = False
                break
                
        results[lang] = {
            "coverage": coverage,
            "roundtrip": roundtrip_ok,
            "special_chars_ok": special_ok,
            "token_count": len(tokens),
        }
        status = "✓ PASS" if coverage > 0.95 and roundtrip_ok else "✗ FAIL"
        print(f"{lang}: {status} — coverage={coverage:.1%}, roundtrip={roundtrip_ok}, tokens={len(tokens)}")
    
    with open("tokenizer_audit.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to tokenizer_audit.json")

if __name__ == "__main__":
    audit()
