#!/usr/bin/env python3
"""
Train Moshi LoRA adapter for Uzbek language.

This script fine-tunes the Moshi language model on Uzbek conversations
using LoRA (Low-Rank Adaptation) to minimize VRAM usage.

Usage:
    python3 training/scripts/train_moshi_lora.py \
        --base_model kyutai/moshika-pytorch-bf16 \
        --dataset_path /root/aziza-build/training/datasets/aziza-uzbek.jsonl \
        --output_dir /root/aziza-build/training/lora/adapters/moshi_uz_v1 \
        --lora_rank 16 \
        --lora_alpha 32 \
        --learning_rate 1e-4
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List

import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

# Add backend to path
sys.path.insert(0, '/root/aziza-build/backend')
sys.path.insert(0, '/root/aziza-build/backend/services')

from moshi.models import loaders
from moshi.models.lm import LMGen

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UzbekConversationDataset(Dataset):
    """Dataset for Uzbek conversations in Moshi format."""
    
    def __init__(self, dataset_path: str, tokenizer, max_length: int = 1024):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.conversations = []
        
        with open(dataset_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line.strip())
                self.conversations.append(data)
        
        logger.info(f"Loaded {len(self.conversations)} conversations from {dataset_path}")
    
    def __len__(self):
        return len(self.conversations)
    
    def __getitem__(self, idx):
        conv = self.conversations[idx]
        
        # Format conversation as text
        text = self._format_conversation(conv)
        
        # Tokenize
        tokens = self.tokenizer.encode(text, out_type=int)
        
        # Truncate if needed
        if len(tokens) > self.max_length:
            tokens = tokens[:self.max_length]
        
        # Pad to max_length
        pad_length = self.max_length - len(tokens)
        tokens = tokens + [self.tokenizer.pad_id()] * pad_length
        
        # Create input/labels
        input_ids = torch.tensor(tokens, dtype=torch.long)
        labels = input_ids.clone()
        
        # Mask padding tokens in labels
        labels[labels == self.tokenizer.pad_id()] = -100
        
        return {
            "input_ids": input_ids,
            "labels": labels,
            "attention_mask": torch.tensor([1] * (self.max_length - pad_length) + [0] * pad_length, dtype=torch.long),
        }
    
    def _format_conversation(self, conv: Dict) -> str:
        """Format conversation as text for training."""
        parts = []
        for msg in conv.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"<{role}>: {content}")
        return "\n".join(parts)


def load_moshi_model(device: str = "cuda"):
    """Load Moshi language model."""
    logger.info("Loading Moshi model...")
    
    mimi_path = loaders.hf_hub_download('kyutai/moshika-pytorch-bf16', loaders.MIMI_NAME)
    mimi = loaders.get_mimi(mimi_path, device=device)
    
    moshi_path = loaders.hf_hub_download('kyutai/moshika-pytorch-bf16', 'model.safetensors', local_files_only=True)
    moshi_lm = loaders.get_moshi_lm(moshi_path, device=device)
    
    # Freeze all parameters
    for param in mimi.parameters():
        param.requires_grad = False
    for param in moshi_lm.parameters():
        param.requires_grad = False
    
    mimi.eval()
    moshi_lm.eval()
    
    logger.info("Moshi model loaded")
    return mimi, moshi_lm


def apply_lora(model, target_modules: List[str], rank: int = 16, alpha: int = 32, dropout: float = 0.05):
    """Apply LoRA adapters to Moshi model."""
    try:
        from peft import LoraConfig, get_peft_model, TaskType
        
        # Monkey-patch Moshi LM for PEFT compatibility
        class DummyConfig:
            is_encoder_decoder = False
            model_type = "moshi"
            
        if not hasattr(model, "prepare_inputs_for_generation"):
            model.prepare_inputs_for_generation = lambda *args, **kwargs: {}
        if not hasattr(model, "config"):
            model.config = DummyConfig()
        
        # Expand target module patterns
        expanded_targets = []
        for pattern in target_modules:
            if "{}" in pattern:
                if "transformer" in pattern and "depformer" not in pattern:
                    for i in range(32):
                        expanded_targets.append(pattern.format(i))
                elif "depformer" in pattern:
                    for i in range(6):
                        for j in range(8):
                            expanded_targets.append(pattern.format(i, j))
            else:
                expanded_targets.append(pattern)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for t in expanded_targets:
            if t not in seen:
                seen.add(t)
                unique_targets.append(t)
        
        logger.info(f"Applying LoRA to {len(unique_targets)} target modules")
        logger.info(f"Sample targets: {unique_targets[:5]}")
        
        config = LoraConfig(
            r=rank,
            lora_alpha=alpha,
            target_modules=unique_targets,
            lora_dropout=dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        
        model = get_peft_model(model, config)
        model.print_trainable_parameters()
        
        return model
    except ImportError:
        logger.error("PEFT not installed. Install with: pip install peft")
        raise
    except Exception as e:
        logger.error(f"Failed to apply LoRA: {e}")
        raise


def train_epoch(model, dataloader, optimizer, device, epoch):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    num_batches = 0
    
    progress_bar = tqdm(dataloader, desc=f"Epoch {epoch}")
    
    for batch in progress_bar:
        input_ids = batch["input_ids"].to(device)
        labels = batch["labels"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        
        # Forward pass
        outputs = model(input_ids=input_ids, labels=labels, attention_mask=attention_mask)
        loss = outputs.loss
        
        # Backward pass
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        
        total_loss += loss.item()
        num_batches += 1
        
        progress_bar.set_postfix({
            "loss": f"{loss.item():.4f}",
            "avg_loss": f"{total_loss/num_batches:.4f}",
        })
    
    return total_loss / num_batches


def validate(model, dataloader, device):
    """Validate model."""
    model.eval()
    total_loss = 0.0
    num_batches = 0
    
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            labels = batch["labels"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            
            outputs = model(input_ids=input_ids, labels=labels, attention_mask=attention_mask)
            loss = outputs.loss
            
            total_loss += loss.item()
            num_batches += 1
    
    return total_loss / num_batches


def main():
    parser = argparse.ArgumentParser(description="Train Moshi LoRA for Uzbek")
    parser.add_argument("--base_model", type=str, default="kyutai/moshika-pytorch-bf16")
    parser.add_argument("--dataset_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--lora_rank", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--per_device_train_batch_size", type=int, default=4)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=8)
    parser.add_argument("--max_steps", type=int, default=1000)
    parser.add_argument("--warmup_steps", type=int, default=100)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--save_steps", type=int, default=200)
    parser.add_argument("--eval_steps", type=int, default=100)
    parser.add_argument("--logging_dir", type=str, default="./logs")
    parser.add_argument("--target_modules", type=str, default=None)
    parser.add_argument("--bf16", action="store_true", default=True)
    parser.add_argument("--gradient_checkpointing", action="store_true", default=True)
    parser.add_argument("--resume_from_checkpoint", action="store_true", default=False)
    
    args = parser.parse_args()
    
    # Setup
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    # Load model
    mimi, moshi_lm = load_moshi_model(device)
    
    # Apply LoRA
    if args.target_modules:
        target_modules = args.target_modules.split(",")
    else:
        # Default Moshi target modules
        target_modules = [
            "transformer.layers.{}.self_attn.in_projs.0",
            "transformer.layers.{}.self_attn.out_projs.0",
            "transformer.layers.{}.gating.linear_in",
            "transformer.layers.{}.gating.linear_out",
            "depformer.layers.{}.self_attn.in_projs.{}",
            "depformer.layers.{}.self_attn.out_projs.{}",
            "depformer.layers.{}.gating.{}.linear_in",
            "depformer.layers.{}.gating.{}.linear_out",
        ]
    
    moshi_lm = apply_lora(
        moshi_lm,
        target_modules,
        rank=args.lora_rank,
        alpha=args.lora_alpha,
        dropout=args.lora_dropout,
    )
    
    # Load tokenizer
    sys.path.insert(0, '/root/aziza-build/model_cache/moshi-extended-tokenizer')
    from extended_tokenizer import get_tokenizer
    tokenizer = get_tokenizer()
    
    # Prepare dataset
    dataset = UzbekConversationDataset(args.dataset_path, tokenizer)
    
    # Split into train/val
    train_size = int(0.9 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    logger.info(f"Train size: {len(train_dataset)}, Val size: {len(val_dataset)}")
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.per_device_train_batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.per_device_train_batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True,
    )
    
    # Optimizer
    optimizer = torch.optim.AdamW(
        [p for p in moshi_lm.parameters() if p.requires_grad],
        lr=args.learning_rate,
        weight_decay=0.01,
    )
    
    # Learning rate scheduler
    from torch.optim.lr_scheduler import CosineAnnealingLR
    scheduler = CosineAnnealingLR(optimizer, T_max=args.max_steps, eta_min=1e-6)
    
    # Training loop
    logger.info("Starting training...")
    best_val_loss = float('inf')
    
    for epoch in range(100):  # Max epochs, will stop at max_steps
        train_loss = train_epoch(moshi_lm, train_loader, optimizer, device, epoch)
        val_loss = validate(moshi_lm, val_loader, optimizer, device)
        
        scheduler.step()
        
        logger.info(f"Epoch {epoch}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            moshi_lm.save_pretrained(os.path.join(args.output_dir, "best"))
            logger.info(f"Saved best model with val_loss={val_loss:.4f}")
        
        # Save checkpoint
        if (epoch + 1) % (args.save_steps // len(train_loader)) == 0:
            checkpoint_dir = os.path.join(args.output_dir, f"checkpoint-{epoch}")
            moshi_lm.save_pretrained(checkpoint_dir)
            logger.info(f"Saved checkpoint to {checkpoint_dir}")
    
    # Save final model
    moshi_lm.save_pretrained(os.path.join(args.output_dir, "final"))
    logger.info(f"Training complete. Final adapter saved to {args.output_dir}/final")


if __name__ == "__main__":
    main()
