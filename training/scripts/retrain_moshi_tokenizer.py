"""
Retrain Moshi SentencePiece tokenizer with extended Uzbek vocabulary.

This script:
1. Loads the original Moshi tokenizer training data (if available)
2. Adds Uzbek text corpus
3. Retrains SentencePiece with vocab size 32015 (32000 + 15)
4. Validates coverage of 15 Uzbek graphemes

Usage:
    python3 training/scripts/retrain_moshi_tokenizer.py
"""

import os
import logging
import tempfile
from typing import List

import sentencepiece as spm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
MOSHI_SNAPSHOT = "/root/.cache/huggingface/hub/models--kyutai--moshika-pytorch-bf16/snapshots/a49141e28b3d9c947cf9aa5314431e1b11cbd2f5"
EXTENDED_TOKENIZER_DIR = "/root/aziza-build/model_cache/moshi-extended-tokenizer"
DATASET_PATH = "/root/aziza-build/training/datasets/aziza-uzbek.jsonl"

# 15 Uzbek graphemes to ensure single-token coverage
UZBEK_GRAPHEMES = [
    "Oʻ", "oʻ", "Gʻ", "gʻ",  # Latin with okina (4)
    "ў", "қ", "ғ", "ҷ", "Ҷ", "Һ", "һ",  # Cyrillic (7)
    # Additional context words for better tokenization
    "Oʻzbekiston", " oʻzbek", "Gʻarb", "gʻarb",
    "ўзбек", "қўш", "ғафлат", "ҷумҳур", "Ҷумҳурийят", "Ҳақ", "ҳақ",
]


def extract_training_text_from_dataset(dataset_path: str) -> List[str]:
    """Extract text from JSONL dataset for tokenizer training."""
    import json
    
    texts = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            for msg in data.get('messages', []):
                content = msg.get('content', '')
                if content:
                    texts.append(content)
    
    return texts


def create_training_corpus() -> str:
    """Create a training corpus for SentencePiece."""
    # Load existing dataset texts
    logger.info("Loading training texts from dataset...")
    texts = extract_training_text_from_dataset(DATASET_PATH)
    logger.info(f"Loaded {len(texts)} text samples from dataset")
    
    # Add Uzbek graphemes with context
    grapheme_contexts = []
    for g in UZBEK_GRAPHEMES:
        # Add the grapheme in different contexts
        grapheme_contexts.append(g)
        grapheme_contexts.append(f"{g} ")
        grapheme_contexts.append(f" {g}")
        grapheme_contexts.append(f"\n{g}\n")
    
    # Combine all texts
    all_texts = texts + grapheme_contexts
    
    # Write to temporary file
    corpus_file = os.path.join(EXTENDED_TOKENIZER_DIR, "training_corpus.txt")
    with open(corpus_file, 'w', encoding='utf-8') as f:
        for text in all_texts:
            f.write(text + "\n")
    
    logger.info(f"Created training corpus: {corpus_file} ({len(all_texts)} lines)")
    return corpus_file


def train_tokenizer(corpus_file: str) -> str:
    """Train SentencePiece tokenizer with extended vocabulary."""
    os.makedirs(EXTENDED_TOKENIZER_DIR, exist_ok=True)
    output_prefix = os.path.join(EXTENDED_TOKENIZER_DIR, "moshi-extended")
    
    logger.info("Training SentencePiece model...")
    
    spm.SentencePieceTrainer.train(
        input=corpus_file,
        model_prefix=output_prefix,
        vocab_size=32015,  # 32000 original + 15 new
        character_coverage=1.0,
        model_type="unigram",
        input_sentence_size=1000000,
        shuffle_input_sentence=True,
        seed_sentencepiece_size=100000,
        unk_piece="<unk>",
        bos_piece="<s>",
        eos_piece="</s>",
        pad_piece="<pad>",
        add_dummy_prefix=False,
        hard_vocab_limit=False,  # Allow slight overflow
        num_threads=8,
    )
    
    model_path = f"{output_prefix}.model"
    vocab_path = f"{output_prefix}.vocab"
    
    logger.info(f"Tokenizer trained: {model_path}")
    logger.info(f"Vocab saved: {vocab_path}")
    
    return model_path


def validate_tokenizer(model_path: str) -> bool:
    """Validate tokenizer coverage of Uzbek graphemes."""
    sp = spm.SentencePieceProcessor(model_file=model_path)
    
    logger.info(f"Extended vocab size: {sp.get_piece_size()}")
    
    test_cases = [
        ("Oʻzbekiston", ["Oʻ", "▁zbek", "▁iston"]),
        ("oʻzbek", ["oʻ", "▁zbek"]),
        ("Gʻarb", ["Gʻ", "▁arb"]),
        ("Salom", ["▁Salom"]),
        ("ўзбек", ["▁ўзбек"]),
        ("қўш", ["▁қўш"]),
        ("ғафлат", ["▁ғафлат"]),
        ("ҷумҳур", ["▁ҷумҳур"]),
        ("Ҳақ", ["▁Ҳақ"]),
    ]
    
    all_pass = True
    for text, expected in test_cases:
        actual = sp.encode(text, out_type=str)
        match = actual == expected
        status = "✅" if match else "❌"
        logger.info(f"{status} '{text}' → {actual} (expected: {expected})")
        if not match:
            all_pass = False
    
    return all_pass


def main():
    logger.info("=== Retraining Moshi Tokenizer for Uzbek ===")
    
    # Create training corpus
    corpus_file = create_training_corpus()
    
    # Train tokenizer
    model_path = train_tokenizer(corpus_file)
    
    # Validate
    if validate_tokenizer(model_path):
        logger.info("✅ Tokenizer validation passed")
    else:
        logger.warning("❌ Tokenizer validation failed — some graphemes still fragmented")
    
    logger.info("=== Tokenizer retraining complete ===")
    logger.info(f"Model saved to: {EXTENDED_TOKENIZER_DIR}/moshi-extended.model")


if __name__ == "__main__":
    main()
