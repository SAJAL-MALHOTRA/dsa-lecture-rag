# 🔬 Research Appendix: LLM Fine-Tuning & Evaluation Study

This document details the empirical investigation into fine-tuning a small instruction-tuned language model (**Qwen2.5-0.5B-Instruct**) for citation-grounded technical Q&A over lecture transcripts, and why deterministic extractive citation was chosen as the production default.

---

## 1. Research Question & Hypothesis

**Hypothesis:** A parameter-efficient fine-tuned (PEFT/LoRA) compact model (0.5B parameters) can be deployed offline on consumer hardware (e.g. laptop CPU / RTX 5050) to produce JSON-structured, evidence-grounded lecture explanations with strict timestamp citations without hallucinating.

---

## 2. Experimental Setup

### Model & Training Configuration
- **Base Model**: `Qwen/Qwen2.5-0.5B-Instruct`
- **Tuning Method**: LoRA (Low-Rank Adaptation)
- **Target Modules**: `q_proj`, `k_proj`, `v_proj`, `o_proj`
- **LoRA Parameters**: Rank $r = 8$, Alpha $\alpha = 16$, Dropout = 0.05
- **Optimizer**: AdamW, Learning Rate = $3 \times 10^{-4}$, Linear decay
- **Training Data**: 60 synthetic DSA query-excerpt pairs generated from non-evaluation video transcripts
- **Leakage Controls**: Audited via `leakage_check.py` against both dev and test splits (0% n-gram or span overlap).

---

## 3. Comparative Benchmark Results

Evaluated on the frozen dev split ($n = 22$ queries: 16 answerable, 6 unanswerable / out-of-domain):

| Metric | Base (Zero-Shot) | Base (Few-Shot, 2 Exemplars) | LoRA Tuned Assistant (0.5B) | Extractive Default (Deterministic) |
|---|---|---|---|---|
| **Valid JSON Schema (First Try)** | 68% [47–84%] | 45% [27–65%] | **86% [67–95%]** | **100%** |
| **Valid JSON ($\le 2$ Retries)** | 86% [67–95%] | 73% [52–87%] | **100% [85–100%]** | **100%** |
| **Integer Source Resolution ($s \in [1, k]$)** | 15% [4–42%] | **100% [70–100%]** | **100% [72–100%]** | **100%** |
| **Grounding Proxy ($\ge 50\%$ word overlap)** | 8% [1–33%] | 67% [35–88%] | 50% [24–76%] | **100%** |
| **Answer OK** (Strict Schema + Grounded) | 0/16 (0%) | **5/16 (31%)** | 1/16 (6%) | 3/16 (19%) |
| **False Abstain Rate** (Refused valid question) | **0/16 (0%)** | **0/16 (0%)** | 4/16 (25%) | **0/16 (0%)** |
| **Abstain OK** (Refused unanswerable question) | 0/6 (0%) | 0/6 (0%) | 0/6 (0%) | **2/6 (33%)** |
| **Inference Latency** | Heavy CPU (~4.2s) | Heavy CPU (~5.8s) | Heavy CPU (~3.9s) | **< 0.05s** |
| **Memory Footprint** | ~1.2 GB | ~1.2 GB | ~1.3 GB | **0 MB** |

---

## 4. Analytical Findings & Diagnosis

1. **LoRA buys syntactic format adherence, not semantic reasoning:**
   Fine-tuning successfully taught the 0.5B model to reliably output clean JSON schema without conversational preambles (first-try validity: 86% vs 45%, $p = 0.022$). However, it did not improve conceptual question-answering accuracy over few-shot prompting (1/16 vs 5/16).

2. **Source indexing does not require parametric tuning:**
   Providing two in-context multi-turn exemplars completely closed the source-resolution gap from 15% to 100%, demonstrating that format conditioning can be achieved prompt-side without weights.

3. **The False Abstention Problem:**
   The LoRA adapter learned an overly cautious refusal behavior, falsely returning empty bullets on 25% (4/16) of valid technical questions. In technical education, false abstention is as damaging as hallucination because it misleads students into believing the concept is unaddressed.

---

## 5. Architectural Decision: The Two-Tier Production Model

Given these empirical findings, carrying a 0.5B local model as the primary answer generator creates an inferior user experience compared to deterministic sentence extraction. We therefore structured the platform into a clear **Two-Tier Architecture**:

1. **Production Offline Default (Deterministic Extractive Citation)**:
   - Zero hallucination risk (all sentences are verbatim transcripts)
   - Zero format or JSON failures
   - 0% false abstention rate
   - <50ms execution latency on any hardware
   - Deployed live on Render Free Tier without requiring PyTorch or GPU resources.

2. **Interactive Generative Mode (BYOK High-Capacity LLMs)**:
   - Visitors connect via Bring-Your-Own-Key (BYOK) to free Groq (Llama-3.3-70B), xAI Grok, or OpenAI.
   - Keys remain strictly in client-side `localStorage`.
   - High-capacity reasoning models synthesize deep explanations and conduct the interactive FAANG "Grill Me" mock interviews while citing verified lecture timestamps.

3. **Experimental LoRA Branch**:
   - The training pipeline, datasets, and LoRA checkpoints are preserved in branch `experiments/lora-qwen-0.5b`.
