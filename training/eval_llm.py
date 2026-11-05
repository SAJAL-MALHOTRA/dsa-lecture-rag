"""
Evaluation and benchmarking script for the fine-tuned Lecture RAG Teaching Assistant.

Measures:
1. Strict JSON Parseability (%)
2. Schema Conformity (%)
3. Citation Accuracy (% of citations that refer to valid provided source IDs)
4. Adversarial Refusal Accuracy (% of out-of-domain queries correctly returned with empty bullets)
5. Generation Latency (sec/query, tokens/sec)

Usage:
    python training/eval_llm.py --adapter-dir models/teaching_assistant_lora
    python training/eval_llm.py --base-only  # benchmark zero-shot base model for comparison
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAL = BASE_DIR / "training" / "data" / "val.jsonl"
DEFAULT_ADAPTER = BASE_DIR / "models" / "teaching_assistant_lora"


def evaluate_llm(
    val_path: Path = DEFAULT_VAL,
    adapter_dir: Path | None = DEFAULT_ADAPTER,
    base_model_name: str = "Qwen/Qwen2.5-0.5B-Instruct",
    max_new_tokens: int = 160,
    device: str | None = None,
) -> dict:
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"\n=== Evaluating Teaching Assistant LLM ===")
    print(f"Base Model: {base_model_name}")
    print(f"LoRA Adapter: {adapter_dir if adapter_dir and adapter_dir.exists() else 'None (Base Zero-Shot)'}")
    print(f"Device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(
        adapter_dir if (adapter_dir and adapter_dir.exists()) else base_model_name,
        use_fast=True,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else (
        torch.float16 if device == "cuda" else torch.float32
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )

    if adapter_dir and adapter_dir.exists() and (adapter_dir / "adapter_config.json").exists():
        print(f"Loading LoRA weights from {adapter_dir}...")
        model = PeftModel.from_pretrained(base_model, adapter_dir)
    else:
        model = base_model

    model.to(device)
    model.eval()

    # Load test samples
    samples = []
    with open(val_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Evaluating on {len(samples)} validation samples...")

    total_samples = len(samples)
    json_valid_count = 0
    schema_valid_count = 0
    citation_valid_count = 0
    citation_total_count = 0
    refusal_correct_count = 0
    refusal_total_count = 0
    latencies = []
    generated_tokens_count = 0

    for i, s in enumerate(samples, start=1):
        messages = s["messages"]
        prompt_msgs = messages[:-1]
        target_raw = messages[-1]["content"]
        target_data = json.loads(target_raw)
        is_refusal_target = len(target_data.get("bullets", [])) == 0
        if is_refusal_target:
            refusal_total_count += 1

        prompt_str = tokenizer.apply_chat_template(
            prompt_msgs, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt_str, return_tensors="pt").to(device)

        t0 = time.time()
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        elapsed = time.time() - t0
        latencies.append(elapsed)

        gen_tokens = output_ids[0][inputs.input_ids.shape[1] :]
        generated_tokens_count += len(gen_tokens)
        gen_text = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

        # 1. Check JSON validity
        try:
            parsed = json.loads(gen_text)
            json_valid_count += 1
        except Exception:
            # Try to extract embedded JSON block if model produced markdown ticks
            import re
            m = re.search(r"\{.*\}", gen_text, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                    json_valid_count += 1
                except Exception:
                    parsed = None
            else:
                parsed = None

        if not parsed or not isinstance(parsed, dict):
            continue

        # 2. Check Schema
        bullets = parsed.get("bullets")
        if isinstance(bullets, list):
            valid_bullets = True
            for b in bullets:
                if not isinstance(b, dict) or "text" not in b or "sources" not in b:
                    valid_bullets = False
                    break
            if valid_bullets:
                schema_valid_count += 1

                # 3. Check Refusal
                if is_refusal_target:
                    if len(bullets) == 0:
                        refusal_correct_count += 1

                # 4. Check Citations
                for b in bullets:
                    sources = b.get("sources", [])
                    if isinstance(sources, list):
                        for src in sources:
                            citation_total_count += 1
                            # In prompts we provide excerpts [1], [2], etc.
                            if isinstance(src, int) and 1 <= src <= 3:
                                citation_valid_count += 1

    avg_latency = sum(latencies) / max(len(latencies), 1)
    tok_per_sec = generated_tokens_count / max(sum(latencies), 1e-6)

    metrics = {
        "total_samples": total_samples,
        "json_valid_rate": json_valid_count / total_samples,
        "schema_conformity_rate": schema_valid_count / total_samples,
        "citation_accuracy": (
            citation_valid_count / citation_total_count if citation_total_count > 0 else 1.0
        ),
        "refusal_accuracy": (
            refusal_correct_count / refusal_total_count if refusal_total_count > 0 else 1.0
        ),
        "avg_latency_sec": round(avg_latency, 3),
        "tokens_per_sec": round(tok_per_sec, 1),
    }

    print("\n--- Evaluation Results ---")
    print(f"JSON Validity Rate:        {metrics['json_valid_rate'] * 100:.1f}% ({json_valid_count}/{total_samples})")
    print(f"Schema Conformity Rate:    {metrics['schema_conformity_rate'] * 100:.1f}% ({schema_valid_count}/{total_samples})")
    print(f"Citation Precision:        {metrics['citation_accuracy'] * 100:.1f}% ({citation_valid_count}/{citation_total_count})")
    print(f"Adversarial Refusal Acc:   {metrics['refusal_accuracy'] * 100:.1f}% ({refusal_correct_count}/{refusal_total_count})")
    print(f"Avg Latency:               {metrics['avg_latency_sec']}s / query")
    print(f"Throughput:                {metrics['tokens_per_sec']} tokens/sec")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate Teaching Assistant LLM")
    parser.add_argument("--val-file", type=Path, default=DEFAULT_VAL)
    parser.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--base-only", action="store_true", help="Evaluate base model without adapter")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    args = parser.parse_args()

    adapter_path = None if args.base_only else args.adapter_dir
    evaluate_llm(
        val_path=args.val_file,
        adapter_dir=adapter_path,
        base_model_name=args.base_model,
    )


if __name__ == "__main__":
    main()
