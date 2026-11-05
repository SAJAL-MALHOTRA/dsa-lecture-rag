"""
Fine-tuning script for Lecture RAG Teaching Assistant using PEFT LoRA.

Fine-tunes a causal language model (default: Qwen/Qwen2.5-0.5B-Instruct) on
grounded lecture QA with strict citation verification and adversarial refusal.

Usage:
    python training/train_lora.py --epochs 3 --lr 2e-4 --output-dir models/teaching_assistant_lora
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = BASE_DIR / "training" / "data" / "train.jsonl"
DEFAULT_VAL = BASE_DIR / "training" / "data" / "val.jsonl"
DEFAULT_OUTPUT = BASE_DIR / "models" / "teaching_assistant_lora"


class GroundedChatDataset(Dataset):
    """Dataset that tokenizes chat messages and masks prompt tokens with -100."""

    def __init__(self, jsonl_path: Path, tokenizer, max_length: int = 1024):
        self.samples = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.samples.append(json.loads(line))

        self.tokenizer = tokenizer
        self.max_length = max_length
        self.features = [self._process_sample(s) for s in self.samples]
        # Filter out failed samples
        self.features = [f for f in self.features if f is not None]

    def _process_sample(self, sample: dict) -> dict | None:
        messages = sample["messages"]
        if len(messages) < 2:
            return None

        # Full text with assistant response
        full_text = self.tokenizer.apply_chat_template(messages, tokenize=False)
        # Prompt only (up to <|im_start|>assistant\n)
        prompt_text = self.tokenizer.apply_chat_template(
            messages[:-1], tokenize=False, add_generation_prompt=True
        )

        full_enc = self.tokenizer(
            full_text,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        prompt_enc = self.tokenizer(
            prompt_text,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )

        input_ids = full_enc.input_ids[0]
        attention_mask = full_enc.attention_mask[0]
        prompt_len = min(prompt_enc.input_ids.shape[1], input_ids.shape[0])

        labels = input_ids.clone()
        labels[:prompt_len] = -100  # mask prompt tokens so loss is only on generation

        # If all tokens were masked (e.g. truncated assistant response), skip
        if (labels != -100).sum() == 0:
            return None

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    def __len__(self) -> int:
        return len(self.features)

    def __getitem__(self, idx: int) -> dict:
        return self.features[idx]


def collate_fn(batch: list[dict], pad_token_id: int) -> dict:
    max_len = max(b["input_ids"].shape[0] for b in batch)

    batch_input_ids = []
    batch_attention_mask = []
    batch_labels = []

    for b in batch:
        pad_len = max_len - b["input_ids"].shape[0]
        if pad_len > 0:
            batch_input_ids.append(
                torch.cat([b["input_ids"], torch.full((pad_len,), pad_token_id, dtype=torch.long)])
            )
            batch_attention_mask.append(
                torch.cat([b["attention_mask"], torch.zeros(pad_len, dtype=torch.long)])
            )
            batch_labels.append(
                torch.cat([b["labels"], torch.full((pad_len,), -100, dtype=torch.long)])
            )
        else:
            batch_input_ids.append(b["input_ids"])
            batch_attention_mask.append(b["attention_mask"])
            batch_labels.append(b["labels"])

    return {
        "input_ids": torch.stack(batch_input_ids),
        "attention_mask": torch.stack(batch_attention_mask),
        "labels": torch.stack(batch_labels),
    }


def train(
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct",
    train_path: Path = DEFAULT_TRAIN,
    val_path: Path = DEFAULT_VAL,
    output_dir: Path = DEFAULT_OUTPUT,
    epochs: int = 3,
    lr: float = 2e-4,
    batch_size: int = 2,
    grad_accum: int = 4,
    max_length: int = 1024,
    lora_r: int = 8,
    lora_alpha: int = 16,
) -> Path:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"=== Starting LoRA Fine-Tuning ===")
    print(f"Base Model: {model_name}")
    print(f"Device: {device} | Epochs: {epochs} | LR: {lr} | Batch Size: {batch_size} (accum: {grad_accum})")

    # 1. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Prepare Datasets
    train_dataset = GroundedChatDataset(train_path, tokenizer, max_length=max_length)
    val_dataset = GroundedChatDataset(val_path, tokenizer, max_length=max_length)
    print(f"Loaded {len(train_dataset)} training samples and {len(val_dataset)} validation samples.")

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=lambda b: collate_fn(b, tokenizer.pad_token_id),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=lambda b: collate_fn(b, tokenizer.pad_token_id),
    )

    # 3. Load Model
    dtype = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else (
        torch.float16 if device == "cuda" else torch.float32
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )

    # 4. Apply LoRA
    peft_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.to(device)
    model.print_trainable_parameters()

    # 5. Optimizer & Scheduler
    total_steps = (len(train_loader) // grad_accum + 1) * epochs
    warmup_steps = max(1, int(total_steps * 0.1))
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    scheduler = get_cosine_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    # 6. Training Loop
    start_time = time.time()
    best_val_loss = float("inf")

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        step_count = 0
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader, start=1):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss / grad_accum
            loss.backward()

            epoch_loss += loss.item() * grad_accum

            if step % grad_accum == 0 or step == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                step_count += 1

        avg_train_loss = epoch_loss / len(train_loader)

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)

                outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                )
                val_loss += outputs.loss.item()

        avg_val_loss = val_loss / max(len(val_loader), 1)
        print(
            f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {avg_train_loss:.4f} | "
            f"Val Loss: {avg_val_loss:.4f} | LR: {scheduler.get_last_lr()[0]:.2e}"
        )

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss

    # 7. Save Adapter & Tokenizer
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Save training metadata
    meta = {
        "base_model": model_name,
        "epochs": epochs,
        "lr": lr,
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "best_val_loss": best_val_loss,
        "elapsed_sec": round(time.time() - start_time, 2),
    }
    with open(output_dir / "training_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"\n[DONE] Fine-tuned LoRA adapter saved to: {output_dir}")
    print(f"Total training time: {meta['elapsed_sec']} seconds")
    return output_dir


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Lecture RAG Assistant with LoRA")
    parser.add_argument("--model-name", default="Qwen/Qwen2.5-0.5B-Instruct", help="Base model identifier")
    parser.add_argument("--train-file", type=Path, default=DEFAULT_TRAIN, help="Path to train.jsonl")
    parser.add_argument("--val-file", type=Path, default=DEFAULT_VAL, help="Path to val.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Output directory for LoRA adapter")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=2, help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--max-length", type=int, default=1024, help="Maximum sequence length")
    parser.add_argument("--lora-r", type=int, default=8, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=16, help="LoRA alpha")
    args = parser.parse_args()

    train(
        model_name=args.model_name,
        train_path=args.train_file,
        val_path=args.val_file,
        output_dir=args.output_dir,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        max_length=args.max_length,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
    )


if __name__ == "__main__":
    main()
