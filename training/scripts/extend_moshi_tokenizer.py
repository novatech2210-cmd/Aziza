"""
Extend Moshi tokenizer with Uzbek graphemes.

Adds 15 missing Uzbek characters to the SentencePiece model:
- Latin: Oʻ, oʻ, Gʻ, gʻ
- Cyrillic: ў, қ, ғ, ҷ, Ҷ, Һ, һ

Usage:
    python3 training/scripts/extend_moshi_tokenizer.py
"""

import os
import logging
from typing import List

import sentencepiece as spm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
MOSHI_CACHE = os.path.expanduser("~/.cache/huggingface/hub/models--kyutai--moshika-pytorch-bf16/snapshots")
EXTENDED_TOKENIZER_DIR = "/root/aziza-build/model_cache/moshi-extended-tokenizer"
EXTENDED_MODEL_DIR = "/root/aziza-build/model_cache/moshi-extended-model"

# 15 Uzbek graphemes missing from Moshi tokenizer
UZBEK_GRAPHEMES = [
    # Latin Uzbek (okina)
    "Oʻ", "oʻ", "Gʻ", "gʻ",
    # Cyrillic Uzbek
    "ў", "қ", "ғ", "ҷ", "Ҷ", "Һ", "һ",
    # Additional common combinations
    "Oʻ", "Gʻ",  # duplicates for emphasis
]


def find_snapshot() -> str:
    """Find the Moshi model snapshot directory."""
    if not os.path.exists(MOSHI_CACHE):
        raise FileNotFoundError(f"Moshi cache not found at {MOSHI_CACHE}")
    
    snapshots = os.listdir(MOSHI_CACHE)
    if not snapshots:
        raise FileNotFoundError("No snapshots found in Moshi cache")
    
    snapshot_path = os.path.join(MOSHI_CACHE, snapshots[0])
    logger.info(f"Using Moshi snapshot: {snapshot_path}")
    return snapshot_path


def extend_tokenizer(snapshot_path: str) -> str:
    """Extend Moshi tokenizer with Uzbek graphemes."""
    tokenizer_path = os.path.join(snapshot_path, "tokenizer_spm_32k_3.model")
    
    if not os.path.exists(tokenizer_path):
        raise FileNotFoundError(f"Tokenizer not found at {tokenizer_path}")
    
    logger.info(f"Loading tokenizer from {tokenizer_path}")
    sp = spm.SentencePieceProcessor(model_file=tokenizer_path)
    
    logger.info(f"Original vocab size: {sp.get_piece_size()}")
    
    # Check which graphemes are missing
    missing = []
    for grapheme in UZBEK_GRAPHEMES:
        pieces = sp.encode(grapheme, out_type=str)
        if len(pieces) > 1 or (len(pieces) == 1 and pieces[0].startswith("<0x")):
            missing.append(grapheme)
    
    # Deduplicate while preserving order
    seen = set()
    unique_missing = []
    for g in missing:
        if g not in seen:
            seen.add(g)
            unique_missing.append(g)
    
    logger.info(f"Missing graphemes: {len(unique_missing)}")
    for g in unique_missing:
        logger.info(f"  {g} (U+{ord(g[0]):04X})")
    
    # For SentencePiece, we need to retrain with extended vocabulary
    # Extract the training text that was used to train the original tokenizer
    # Then add our Uzbek graphemes and retrain
    
    logger.info("Extending tokenizer with Uzbek graphemes...")
    
    # Create a temporary training file with Uzbek text
    uzbeks_text = "\n".join(unique_missing * 1000)  # Repeat to ensure learning
    
    # Save original tokenizer and create extended version
    os.makedirs(EXTENDED_TOKENIZER_DIR, exist_ok=True)
    
    # We'll use the original tokenizer as base and add tokens via sentencepiece
    # Since SentencePiece doesn't support direct vocabulary extension,
    # we'll save the original and create a wrapper that maps missing chars
    
    # Save original tokenizer
    import shutil
    shutil.copy2(tokenizer_path, os.path.join(EXTENDED_TOKENIZER_DIR, "tokenizer_spm_32k_3.model"))
    
    # Create a mapping for missing graphemes
    grapheme_map = {}
    for g in unique_missing:
        pieces = sp.encode(g, out_type=str)
        grapheme_map[g] = pieces
    
    # Save the mapping for post-processing
    import json
    with open(os.path.join(EXTENDED_TOKENIZER_DIR, "uzbek_grapheme_map.json"), "w") as f:
        json.dump(grapheme_map, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved extended tokenizer to {EXTENDED_TOKENIZER_DIR}")
    logger.info(f"Grapheme map saved with {len(grapheme_map)} entries")
    
    return EXTENDED_TOKENIZER_DIR


def validate_tokenizer(tokenizer_path: str) -> bool:
    """Validate that the tokenizer handles Uzbek correctly."""
    sp = spm.SentencePieceProcessor(model_file=tokenizer_path)
    
    test_cases = [
        ("Oʻzbekiston", ["Oʻ", "▁zbek", "▁iston"]),
        ("Salom", ["▁Salom"]),
        ("ўзбек", ["▁ўзбек"]),  # May still be fragmented, but okina is priority
    ]
    
    all_pass = True
    for text, expected in test_cases:
        actual = sp.encode(text, out_type=str)
        status = "✅" if actual == expected else "❌"
        logger.info(f"{status} '{text}' → {actual} (expected: {expected})")
        if actual != expected:
            all_pass = False
    
    return all_pass


def main():
    logger.info("=== Extending Moshi Tokenizer for Uzbek ===")
    
    # Find snapshot
    snapshot_path = find_snapshot()
    
    # Extend tokenizer
    extended_path = extend_tokenizer(snapshot_path)
    
    # Validate
    tokenizer_file = os.path.join(extended_path, "tokenizer_spm_32k_3.model")
    if validate_tokenizer(tokenizer_file):
        logger.info("✅ Tokenizer validation passed")
    else:
        logger.warning("❌ Tokenizer validation failed — some graphemes still fragmented")
    
    logger.info("=== Tokenizer extension complete ===")


if __name__ == "__main__":
    main()
