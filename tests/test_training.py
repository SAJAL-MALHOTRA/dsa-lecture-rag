"""
Unit tests for the training dataset pipeline and LoRA dataset processing.

Run: python -m pytest tests/test_training.py -v
"""

import json
import pytest
from pathlib import Path
from training.generate_dataset import generate_dataset, SYSTEM_PROMPT
from training.train_lora import GroundedChatDataset, collate_fn


def test_generate_dataset_structure(tmp_path):
    train_exs, val_exs = generate_dataset()

    assert len(train_exs) > 0
    assert len(val_exs) > 0

    # Verify schema of every single example
    for ex in train_exs + val_exs:
        assert "messages" in ex
        msgs = ex["messages"]
        assert len(msgs) == 3
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == SYSTEM_PROMPT
        assert msgs[1]["role"] == "user"
        assert "Question:" in msgs[1]["content"]
        assert "Lecture Excerpts:" in msgs[1]["content"]
        assert msgs[2]["role"] == "assistant"

        # Assistant content must be strict valid JSON
        parsed = json.loads(msgs[2]["content"])
        assert isinstance(parsed, dict)
        assert "bullets" in parsed
        assert isinstance(parsed["bullets"], list)
        for b in parsed["bullets"]:
            assert "text" in b and isinstance(b["text"], str)
            assert "sources" in b and isinstance(b["sources"], list)
            assert all(isinstance(s, int) and s >= 1 for s in b["sources"])


def test_adversarial_examples_are_present():
    train_exs, val_exs = generate_dataset()
    all_exs = train_exs + val_exs

    # Find examples with empty bullets (adversarial refusals)
    refusals = [
        ex for ex in all_exs
        if len(json.loads(ex["messages"][2]["content"])["bullets"]) == 0
    ]
    assert len(refusals) >= 10, "Adversarial refusal examples must be present in dataset"


def test_dataset_prompt_masking():
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    dataset = GroundedChatDataset(
        Path("training/data/val.jsonl"),
        tok,
        max_length=512,
    )

    assert len(dataset) > 0
    sample = dataset[0]
    assert "input_ids" in sample
    assert "labels" in sample

    # Check that labels have -100 masking for prompt tokens
    labels = sample["labels"]
    assert -100 in labels.tolist()
    # But not all tokens are masked
    assert any(l != -100 for l in labels.tolist())


def test_collate_fn_padding():
    import torch

    b1 = {
        "input_ids": torch.tensor([1, 2, 3]),
        "attention_mask": torch.tensor([1, 1, 1]),
        "labels": torch.tensor([-100, 2, 3]),
    }
    b2 = {
        "input_ids": torch.tensor([4, 5]),
        "attention_mask": torch.tensor([1, 1]),
        "labels": torch.tensor([-100, 5]),
    }

    batch = collate_fn([b1, b2], pad_token_id=0)
    assert batch["input_ids"].shape == (2, 3)
    assert batch["attention_mask"].shape == (2, 3)
    assert batch["labels"].shape == (2, 3)

    # b2 should have pad token 0 in input_ids and -100 in labels
    assert batch["input_ids"][1, 2].item() == 0
    assert batch["attention_mask"][1, 2].item() == 0
    assert batch["labels"][1, 2].item() == -100
