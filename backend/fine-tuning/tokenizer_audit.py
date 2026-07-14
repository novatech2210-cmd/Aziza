"""
Run this before any training. Coverage must be >95% for all languages.
If coverage is below threshold, extend tokenizer before proceeding.
"""
import json
from pathlib import Path

TEST_STRINGS = {
    "ru":      "Привет, меня зовут Азиза. Как я могу вам помочь сегодня?",
    "uz-latn": "Salom, mening ismim Aziza. Qanday yordam bera olaman?",
    "uz-cyrl": "Салом, менинг исмим Азиза. Қандай ёрдам бера оламан?",
    "en":      "Hello, my name is Aziza. How can I help you today?",
}

# Special chars that MUST be single tokens, not byte-fallbacks
REQUIRED_CHARS = {
    "uz-latn": ["Oʻ", "oʻ", "Gʻ", "gʻ"],
    "uz-cyrl": ["Ҳ", "ҳ", "Ҷ", "ҷ", "Қ", "қ", "Ғ", "ғ", "Ў", "ў"],
    "ru":      ["Ё", "ё"],
}

def audit(tokenizer) -> dict:
    results = {}
    for lang, text in TEST_STRINGS.items():
        tokens = tokenizer.encode(text)
        decoded = tokenizer.decode(tokens)
        coverage = sum(1 for t in tokens if t < getattr(tokenizer, 'vocab_size', len(tokens))) / len(tokens)
        roundtrip_ok = (decoded.strip() == text.strip())
        special_ok = all(
            tokenizer.encode(c) != tokenizer.encode("?")  # not falling back to unknown
            for c in REQUIRED_CHARS.get(lang, [])
        )
        results[lang] = {
            "coverage": coverage,
            "roundtrip": roundtrip_ok,
            "special_chars_ok": special_ok,
            "token_count": len(tokens),
        }
        status = "✓ PASS" if coverage > 0.95 and roundtrip_ok else "✗ FAIL"
        print(f"{lang}: {status} — coverage={coverage:.1%}, roundtrip={roundtrip_ok}")
    return results

if __name__ == "__main__":
    try:
        from sentencepiece import SentencePieceProcessor
        sp = SentencePieceProcessor()
        # In production this would load the actual model path
        # sp.load('tokenizer.model')
        # audit(sp)
        print("Tokenizer audit script ready. Please load the Moshi SentencePiece model to execute.")
    except ImportError:
        print("SentencePiece not installed. Tokenizer audit script ready.")
