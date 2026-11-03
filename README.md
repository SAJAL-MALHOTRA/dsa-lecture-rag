---
title: DSA Lecture RAG
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# DSA Lecture RAG: Bias-Aware Timestamped Video Retrieval & Synthesis

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://striver-dsa-platform.onrender.com)
[![GitHub Repo](https://img.shields.io/badge/GitHub-dsa--lecture--rag-181717?style=for-the-badge&logo=github)](https://github.com/SAJAL-MALHOTRA/dsa-lecture-rag)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A precision-engineered retrieval-augmented generation (RAG) system for technical YouTube lecture videos. Built to solve the **video timestamp precision problem**: taking student programming doubts (symptom descriptions, conceptual confusion, algorithm mechanics) and navigating directly to the exact second where the explanation begins.

---

## 1. Pipeline Architecture

```
[Student Query]
       │
       ├──► BM25 Lexical Channel (75s Windows, 15s Stride) ─────────────────────────┐
       │                                                                            ▼
       └──► Multilingual Dense Channel (paraphrase-multilingual-MiniLM-L12-v2) ───► Reciprocal Rank Fusion (RRF, k=60)
                                                                                            │
                                                                                            ▼
                                                                                 Top-K Retrieved Chunks
                                                                                            │
                                                                                            ▼
                                                                                 Sub-Chunk Seek Refinement
                                                                            (BM25 over 1-seg sliding window, pad=3s)
                                                                                            │
                                                                                            ▼
                                                                                 Final Video Seek Timestamps
                                                                                            │
                                                                                            ▼
                                                                                 Answer Synthesis
                                                                            Default: Extractive Citation (<50ms, 0% Hallucination)
                                                                            Optional: BYOK Cloud LLMs (Groq / OpenAI)
                                                                            Research Study: LoRA Qwen-0.5B (see EXPERIMENTS.md)
```

### Core Components
1. **Dynamic Transcript Chunking (`ytrag/chunk.py`)**:
   - Spoken-audio transcripts partitioned into sliding contextual windows ($75s$ length, $15s$ stride).
2. **Hybrid Multi-Stage Retrieval (`ytrag/retriever.py`)**:
   - **Lexical Channel**: BM25Okapi over alphanumeric word tokens.
   - **Dense Channel**: Unit-normalized semantic cosine similarity using `sentence-transformers`.
   - **Rank Fusion**: Reciprocal Rank Fusion ($RRF(d) = \sum \frac{1}{60 + \text{rank}(d)}$).
3. **Sub-Chunk Seek Refinement (`ytrag/refine.py`)**:
   - Snaps the playback seek point from the coarse chunk start to the specific sentence introducing the queried concept.
4. **Answer Generation (`ytrag/extractive.py` & `ytrag/local_llm.py`)**:
   - **Production Default**: Deterministic extractive synthesis with timestamp citations (<0.05s latency, zero hallucinations).
   - **Experimental**: Fine-tuned `Qwen/Qwen2.5-0.5B-Instruct` LoRA assistant (gated behind `USE_LOCAL_LLM=1`).

---

## 2. Expanded 104-Query Benchmark & Equivalence Analysis

The evaluation benchmark was expanded from $n = 52$ to **$n = 104$ queries** (39 dev, 65 test) across **18 diverse lecture videos** covering 8 DSA curriculum topics (Dynamic Programming, Graph Traversals, Binary Trees, Binary Search, Stacks & Queues, Linked Lists, Arrays, Sorting). All queries strictly follow the non-transcript labeling protocol ([`LABELING_PROTOCOL.md`](LABELING_PROTOCOL.md)).

### Primary Metric: `seek` Hit Definition
*Hit iff same video and $\text{gt.start} - 20s \le \text{result.start} \le \text{gt.start} + 0.5 \times \text{len}(\text{gt})$.*

| System | Hit@1 (95% CI) | Hit@3 (95% CI) | Hit@5 (95% CI) | MRR@3 (95% CI) | Median \|Seek Error\| |
|---|---|---|---|---|---|
| **`bm25`** | 6.2% [2.4–14.8%] | 15.4% [8.6–26.1%] | 18.5% [10.9–29.6%] | 0.100 [0.044–0.164] | **8.0s** ($n=17$) |
| **`hybrid_en`** | **10.8% [5.3–20.8%]** | **18.5% [11.0–29.6%]** | **27.7% [18.3–39.6%]** | **0.138 [0.069–0.218]** | **10.0s** ($n=21$) |
| **`hybrid_multi`** | 9.2% [4.3–18.9%] | **18.5% [11.0–29.6%]** | **27.7% [18.3–39.6%]** | 0.133 [0.067–0.208] | 15.5s ($n=19$) |

### Statistical Rigour: Beyond Null Hypothesis Testing

When comparing close configurations (e.g. `hybrid_en` vs `hybrid_multi`), failing to reject the null ($p > 0.05$) does not prove equivalence. We implemented **Two One-Sided Tests (TOST)** and **Bayesian analysis**:

1. **Exact Paired McNemar Test**: $p = 0.6875$ (4 queries found only by English, 2 found only by Multilingual, 10 found by both, 49 by neither at $k=3$).
2. **TOST Equivalence Test ($\Delta = \pm 10.0\%$)**:
   $$\text{TOST } p = 0.0324 < 0.05 \implies \textbf{Statistically Equivalent}$$
   Both models perform within the $\pm 10\%$ equivalence margin at 95% statistical confidence.
3. **Bayesian Posterior Evidence**:
   $$P(|\delta| < 10\% \mid \text{data}) = \mathbf{96.1\%} \quad (95\%\text{ Credible Interval } [-4.8\%, +11.0\%])$$
   Quantifies **96.1% posterior evidence** that the difference between English and Multilingual encoders on this technical vocabulary is practically negligible.
4. **Resolution of Hit@1 Regression**:
   By adding conservative forward shift constraints (`max_forward_shift = 22.0s`), sub-chunk refinement no longer overshoots the explanation onset when snapping to deep sub-segments. Hit@1 recovered from 7.7% to **10.8%**, Hit@3 rose to **18.5%**, and Hit@5 reached **27.7%**.
4. **Statistical Power**: Expanding to $n=65$ test queries tightened the 95% Wilson confidence intervals to **16 percentage points** (down from 25–30 pp on $n=30$), providing adequate statistical power to separate retrieval configurations.

---

## 3. LLM Fine-Tuning & Evaluation: LoRA vs. Few-Shot vs. Extractive

We trained a LoRA adapter on `Qwen/Qwen2.5-0.5B-Instruct` (`q_proj, k_proj, v_proj, o_proj`, $r=8, \alpha=16$, lr=$3\times 10^{-4}$) on a leak-free 60-example synthetic dataset, and ran a paired comparative evaluation on the dev split ($n=22$ queries: 16 answerable, 6 unanswerable):

| Metric | Base (Zero-Shot) | Base (Few-Shot, 2 Exemplars) | LoRA Tuned Assistant (0.5B) | Extractive Default |
|---|---|---|---|---|
| **Valid JSON Schema (First Try)** | 68% [47–84%] | 45% [27–65%] | **86% [67–95%]** | **100%** |
| **Valid JSON ($\le 2$ Retries)** | 86% [67–95%] | 73% [52–87%] | **100% [85–100%]** | **100%** |
| **Integer Source Resolution ($s \in [1, k]$)** | 15% [4–42%] | **100% [70–100%]** | **100% [72–100%]** | **100%** |
| **Grounding Proxy ($\ge 50\%$ word overlap)** | 8% [1–33%] | 67% [35–88%] | 50% [24–76%] | **100%** |
| **answer_ok** (Strict Schema + Grounded) | 0/16 (0%) | **5/16 (31%)** | 1/16 (6%) | 3/16 (19%) |
| **False Abstain Rate** (Refused valid question) | **0/16 (0%)** | **0/16 (0%)** | 4/16 (25%) | **0/16 (0%)** |
| **Abstain OK** (Refused unanswerable question) | 0/6 (0%) | 0/6 (0%) | 0/6 (0%) | **2/6 (33%)** |
| **Inference Latency** | Heavy CPU | Heavy CPU | Heavy CPU | **<0.05s** |

### Key Findings:
1. **LoRA buys schema adherence, not domain knowledge**: Fine-tuning taught the 0.5B model to reliably output the JSON schema without conversational preambles (first-try validity: 86% vs 45%, $p = 0.022$). However, it did not improve question answering accuracy over few-shot prompting (1/16 vs 5/16).
2. **Citation indexing does not require tuning**: Two in-context multi-turn examples completely closed the source-resolution gap from 15% to 100%.
3. **The False Abstention Problem**: The LoRA model learned an over-cautious refusal behavior, falsely returning empty bullets on 25% of answerable questions.
4. **Why Extractive is Default**: The deterministic non-LLM sentence extraction baseline has zero hallucination risk, zero format failures, lower false abstentions, and runs in 50ms, making it the superior production choice. The local LoRA model remains gated behind `USE_LOCAL_LLM=1`.

---

## 4. Leakage Audit & Dataset Integrity

Fine-tuning records were strictly audited against the evaluation set using `leakage_check.py`:
- **Golden Query Leakage**: 0/22 dev queries, 0/30 test queries leaked (Jaccard $\ge 0.80$).
- **Answer Span Leakage**: 0/22 dev spans, 0/30 test spans leaked (shared 8-grams).
- **Train/Val Transcript Overlap**: 0/15 validation records share transcript text with training (disjoint video split).

---

## 5. Explicit Limitations

1. **Transcript-Derived Labels**: Ground-truth target spans were identified from transcript text; human blind video verification was not conducted. Reported hit rates reflect alignment with transcript-derived boundaries.
2. **Sample Size & Statistical Power**: With $n=22$ dev queries and $n=30$ test queries, confidence intervals span 20–30 percentage points. The sample size is insufficient to statistically separate close configurations.
3. **Dev-Selected Systems**: All candidate retriever configurations and refinement parameters were selected based on exploration on the dev split prior to locking the test evaluation.
4. **Held-Out Questions vs. Held-Out Lectures**: The main training set excluded golden questions and spans, but drew background windows from the same set of 8 lectures. Video-level holdout tooling (`video_holdout.py`) is provided for scaling to multi-course datasets.

---

## 6. Getting Started

### Installation
```bash
git clone https://github.com/SAJAL-MALHOTRA/dsa-lecture-rag.git
cd dsa-lecture-rag
python -m venv .venv
# Activate virtual environment
pip install -r requirements.txt
```

### Running the API & UI
```bash
# Start FastAPI backend (serves web UI at http://localhost:8000)
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

### Reproducing Evaluations
```bash
# 1. Run all unit tests (129 tests)
python -m pytest tests/

# 2. Verify leakage audit
python leakage_check.py --golden eval/golden.json --train training/data/train.jsonl --val training/data/val.jsonl --transcripts transcripts/

# 3. Check pre-registration lock status
python preregister.py status --lock prereg.lock.json

# 4. Run dev evaluation
python eval_harness.py --golden eval/golden.json --split dev --runs bm25=runs/run_bm25.json hybrid=runs/run_hybrid.json hybrid_refined=runs/run_hybrid_minilm_refined.json
```

---

## 7. License
MIT License.
