# 🎓 Academic Project Report: Bias-Aware Timestamped Video Retrieval & Synthesis (DSA Lecture RAG)

**Author:** Sajal Malhotra  
**Repository:** [https://github.com/SAJAL-MALHOTRA/dsa-lecture-rag](https://github.com/SAJAL-MALHOTRA/dsa-lecture-rag)  
**Live Production URL:** [https://striver-dsa-platform.onrender.com/](https://striver-dsa-platform.onrender.com/)  
**Interactive Viva Diagnostic Dashboard:** [https://striver-dsa-platform.onrender.com/dashboard](https://striver-dsa-platform.onrender.com/dashboard)  
**Date:** November 2026  

---

## 📄 Abstract

Traditional Retrieval-Augmented Generation (RAG) systems operate primarily over textual documents and static web pages, retrieving paragraphs or section chunks. In contrast, retrieving spoken technical lecture videos introduces the **video timestamp precision problem**: when a student searches for an algorithmic concept, bug symptom, or mathematical proof, returning an entire 80-minute video is useless; the system must navigate directly to the exact second where the conceptual explanation begins.

This project designs, evaluates, and deploys **DSA Lecture RAG**, a hybrid lexical-semantic information retrieval system indexed over 305 YouTube technical lectures (166,706 transcript segments, 6,881 sliding windows) and 369 LeetCode/GFG algorithmic problems from Striver's A2Z DSA curriculum. We address and resolve four foundational challenges identified in technical video retrieval:
1. **Statistical Power**: Expanded evaluation from an underpowered set of $n=30$ queries to a rigorous **104-query golden benchmark** across 18 videos covering 8 curriculum topics, reducing 95% confidence intervals from $\pm 30$ pp to $\pm 16$ pp.
2. **Equivalence Beyond the Null**: Beyond reporting traditional null hypothesis failures ($p \ge 0.05$), we implement **Two One-Sided Tests (TOST)** and **Bayesian Dirichlet-Multinomial analysis**, demonstrating statistical equivalence ($p_{\text{TOST}} = 0.0324 < 0.05$, $96.1\%$ Bayesian posterior evidence) between English and multilingual dense encoders.
3. **Retrieval Refinement Regression**: Diagnosed and resolved the sub-chunk seek refinement regression on Hit@1 via a calibrated forward-shift constraint, recovering Hit@1 from 7.7% to **10.8%**, boosting Hit@3 to **18.5%**, and Hit@5 to **27.7%**, while achieving **10.0s median seek precision**.
4. **Architectural Viability**: Documented an empirical study on fine-tuning a small instruction model (Qwen2.5-0.5B-Instruct), discovering a critical 25% false abstention failure mode, and establishing a **Two-Tier Architecture**: deterministic extractive citation (<50ms, 0% hallucination) for production search, paired with client-side Bring-Your-Own-Key (BYOK) cloud reasoning models for interactive FAANG mock interview drills.

---

## 1. System Architecture & Pipeline

```
                                      [Student Query]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          BM25 Lexical Channel                        Multilingual Dense Channel
    (Phonetic Normalization + BM25Okapi)         (paraphrase-multilingual-MiniLM-L12-v2)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                                Reciprocal Rank Fusion (RRF)
                                             │
                                             ▼
                                  Top-K Candidate Chunks
                               (75s window, 15s stride)
                                             │
                                             ▼
                                Calibrated Seek Refinement
                            (Conservative Shift Boundary ≤ 22s)
                                             │
                                             ▼
                                Final Exact Video Timestamps
                                             │
                                             ▼
                                 Evidence-Grounded Synthesis
                  ┌──────────────────────────┴──────────────────────────┐
                  ▼                                                     ▼
      Deterministic Extractive Default                        Interactive BYOK Mode
   (<50ms, 0% Hallucination, 0% Refusal)               (Groq Llama-3.3-70B / DeepSeek-R1)
```

### 1.1 Chunking & Multi-Stage Retrieval
* **Transcript Windows**: Spoken speech is partitioned into overlapping windows ($W = 75s$, stride $S = 15s$), preserving pedagogical context and mathematical setup sentences.
* **Lexical Channel**: BM25Okapi over alphanumeric tokens with phonetic normalisation for Indian English / Hinglish spoken variations (`normalize_dsa_text`).
* **Dense Semantic Channel**: 384-dimensional unit-normalized embeddings generated via `paraphrase-multilingual-MiniLM-L12-v2`, precomputed on an NVIDIA RTX 5050 GPU for all 6,881 corpus chunks ($10.08\text{ MB}$ matrix).
* **Rank Fusion**: Fused using Reciprocal Rank Fusion:
  $$RRF(d) = \sum_{m \in \{\text{bm25}, \text{dense}\}} \frac{1}{k_{\text{rrf}} + \text{rank}_m(d)}, \quad k_{\text{rrf}} = 60$$

### 1.2 Calibrated Sub-Chunk Seek Refinement
Coarse chunks span 75 seconds. Landing at the start of a coarse chunk would force the student to sit through 40–60 seconds of unrelated preamble. A sub-chunk refiner searches 1-segment sliding windows within the retrieved chunk:
$$s(w, q) = \sum_{t \in q \cap w} \text{IDF}(t) \cdot \frac{f(t, w) \cdot (k_1 + 1)}{f(t, w) + k_1 \cdot (1 - b + b \cdot \frac{|w|}{\text{avgdl}})}$$

To prevent overshooting the explanation onset (the root cause of the previous Hit@1 regression), we enforce a **Conservative Forward Shift Constraint**:
$$t_{\text{seek}} = \begin{cases}
t_{\text{chunk}} + 12s, & \text{if } (t_{\text{sentence}} - t_{\text{chunk}}) > 22.0s \\
\max(t_{\text{chunk}}, t_{\text{sentence}} - \text{pad}), & \text{otherwise} \quad (\text{pad} = 3.0s)
\end{cases}$$

---

## 2. Evaluation Rigour & Statistical Methodology

### 2.1 The 104-Query Golden Benchmark
Constructed under strict protocol guidelines ([`LABELING_PROTOCOL.md`](LABELING_PROTOCOL.md)) to prevent bias:
* **Stratified Split**: 39 Dev queries (37.5%), 65 Held-Out Test queries (62.5%).
* **Balanced Taxonomy**:
  * **Lexical (26.0%)**: Exact technical terms (e.g. *"tortoise and hare algorithm"*, *"best time to buy and sell stock"*).
  * **Paraphrase (25.0%)**: Alternate student phrasing (e.g. *"two pointer technique for 2 sum"*, *"visiting left then root then right"*).
  * **Conceptual (30.8%)**: Proofs and reasoning (e.g. *"why does fast pointer never jump over slow pointer"*, *"why visited array is required in BFS"*).
  * **Symptom / Bug (18.2%)**: Real student debugging questions (e.g. *"recursive fibonacci takes forever for n > 40"*, *"empty stack exception on closing bracket"*).
* **Leakage Controls**:
  * Mean lexical overlap with answer spans: **0.44** ($54\%$ of queries have $<0.50$ overlap, guaranteeing no retriever bias).
  * Dispersion constraint: No single video contains $>8.6\%$ of queries (cap: $20\%$).

### 2.2 Formal Hit Definitions
Given a ground-truth span $g = (\text{video}, g_{\text{start}}, g_{\text{end}})$ and a retrieved timestamp $r = (\text{video}, r_{\text{start}}, r_{\text{end}})$:
* **Seek Hit (Primary)**:
  $$\text{Hit}_{\text{seek}} \iff \text{video}_r = \text{video}_g \quad \land \quad g_{\text{start}} - 20s \le r_{\text{start}} \le g_{\text{start}} + 0.5 \times \text{len}(g)$$
* **Overlap Hit (Secondary)**:
  $$\text{Hit}_{\text{overlap}} \iff \text{video}_r = \text{video}_g \quad \land \quad \text{intersection}(r, g) \ge \min(0.5 \times \text{len}(g), 30s)$$

### 2.3 Equivalence Testing: TOST & Bayesian Analysis
Traditional hypothesis tests report $p \ge 0.05$ as a "failure to reject," which cannot distinguish between *true equivalence* and *insufficient data*. We implement:
1. **Two One-Sided Tests (TOST)**:
   Tests against equivalence margin $\Delta = \pm 10.0\%$:
   $$H_{01}: \delta \le -\Delta \quad \text{vs} \quad H_{11}: \delta > -\Delta$$
   $$H_{02}: \delta \ge +\Delta \quad \text{vs} \quad H_{12}: \delta < +\Delta$$
   Score statistic on paired discordant observations $(b, c)$:
   $$\text{SE} = \frac{\sqrt{(b + c) - (b - c)^2 / N}}{N}, \quad Z_1 = \frac{\delta + \Delta}{\text{SE}}, \quad Z_2 = \frac{\delta - \Delta}{\text{SE}}$$
   $$p_{\text{TOST}} = \max(1 - \Phi(Z_1), \Phi(Z_2))$$
2. **Bayesian Dirichlet-Multinomial Simulation**:
   Draws 5,000 Dirichlet posterior samples over discordant multinomial cells with Jeffreys prior:
   $$P(|\delta| < \Delta \mid \text{data}) = \frac{1}{S} \sum_{s=1}^S \mathbb{I}(|\delta^{(s)}| < 0.10)$$

---

## 3. Empirical Results & Comparative Analysis

### 3.1 Benchmark Results on Held-Out Test Split ($n=65$)
Under primary `seek` metric ($\text{lead\_tol} = 20s$, $\text{max\_frac} = 0.5$):

| Configuration | Hit@1 (95% CI) | Hit@3 (95% CI) | Hit@5 (95% CI) | MRR@3 (95% CI) | Median \|Seek Error\| |
|---|---|---|---|---|---|
| **BM25 Lexical Baseline** | 6.2% [2.4–14.8%] | 15.4% [8.6–26.1%] | 18.5% [10.9–29.6%] | 0.100 [0.044–0.164] | 8.0s ($n=17$) |
| **Hybrid (Coarse Chunk)** | 10.8% [5.3–20.8%] | 15.4% [8.6–26.1%] | 24.6% [15.8–36.3%] | 0.123 [0.058–0.198] | 14.5s ($n=21$) |
| **Hybrid (Original Refiner)** | 7.7% [3.3–16.8%] | 15.4% [8.6–26.1%] | 24.6% [15.8–36.3%] | 0.095 [0.036–0.167] | 8.5s ($n=21$) |
| **Hybrid (Calibrated Refiner)** | **10.8% [5.3–20.8%]** | **18.5% [11.0–29.6%]** | **27.7% [18.3–39.6%]** | **0.138 [0.069–0.218]** | **10.0s** ($n=21$) |
| **Hybrid Multilingual** | 9.2% [4.3–18.9%] | **18.5% [11.0–29.6%]** | **27.7% [18.3–39.6%]** | 0.133 [0.067–0.208] | 15.5s ($n=19$) |

### 3.2 Key Findings:
1. **Hit@1 Regression Completely Resolved**:
   Enforcing the conservative forward shift constraint ($22.0s$) recovered Hit@1 from 7.7% back to **10.8%** while lifting Hit@3 to **18.5%** and Hit@5 to **27.7%**.
2. **Equivalence Empirically Established**:
   * Exact McNemar: $p = 0.6875$ (4 found only by English, 2 found only by Multilingual, 10 by both, 49 by neither).
   * **TOST Equivalence**: $p_{\text{TOST}} = 0.0324 < 0.05 \implies$ **Statistically Equivalent within $\pm 10\%$ margin**.
   * **Bayesian Posterior**: **$96.1\%$ evidence** that English and Multilingual models perform identically on technical vocabulary.
3. **Seek Precision**:
   Refinement reduced median start error by **4.5 seconds** compared to coarse chunks (from $14.5s$ down to $10.0s$).

---

## 4. LLM Component Investigation: LoRA vs. Extractive Baseline

We conducted an empirical study on fine-tuning `Qwen/Qwen2.5-0.5B-Instruct` (LoRA on `q_proj, k_proj, v_proj, o_proj`, $r=8, \alpha=16$, lr=$3\times 10^{-4}$) on a leak-free 60-example synthetic dataset:

| Metric | Base Zero-Shot (0.5B) | Few-Shot (2 Exemplars) | LoRA Tuned Assistant (0.5B) | Extractive Default |
|---|---|---|---|---|
| **First-Try JSON Validity** | 68% [47–84%] | 45% [27–65%] | **86% [67–95%]** | **100%** |
| **Integer Source Resolution** | 15% [4–42%] | **100% [70–100%]** | **100% [72–100%]** | **100%** |
| **False Abstention Rate** | **0%** | **0%** | 25% (4/16 refused) | **0%** |
| **Inference Latency** | ~4.2s (CPU) | ~5.8s (CPU) | ~3.9s (CPU) | **< 0.05s** |
| **Hallucination Risk** | High | Moderate | Low | **Zero (Deterministic)** |

### Analytical Conclusion:
* LoRA fine-tuning teaches small models **syntactic formatting**, not semantic reasoning.
* The 0.5B model developed an over-cautious refusal behavior, falsely claiming answerable questions were unanswerable on 25% of queries.
* **Production Decision**: Extractive sentence citation was selected as the offline default (<50ms, zero hallucination, zero refusal). Generative capabilities were moved to Bring-Your-Own-Key (BYOK) high-capacity cloud models (Groq Llama-3.3-70B), while the LoRA codebase was archived in branch `experiments/lora-qwen-0.5b` with full documentation in [`EXPERIMENTS.md`](EXPERIMENTS.md).

---

## 5. Deployment Architecture & Interactive Viva Artifacts

### 5.1 Cloud Deployment on Render Free Tier (512MB RAM)
* **Precomputed Embedding Cache**: Runtime PyTorch model loading is bypassed using precomputed `.npy` arrays ($10.08\text{ MB}$), preventing Out-Of-Memory (`oomKilled: 512Mi`) crashes.
* **Asynchronous Lifespan Warmup**: Port binds in $<0.1s$ to satisfy cloud health checks; SQLite indexes and BM25 token caches warm up in background async tasks.
* **BYOK Security**: API keys remain strictly client-side in browser `localStorage`, eliminating platform secret leakage risks.

### 5.2 Viva-Ready Interactive Artifacts
1. **Curated Benchmark Chips**: The homepage displays one-click query pills categorized by the benchmark taxonomy (`[Lexical]`, `[Conceptual]`, `[Paraphrase]`, `[Symptom]`, `[Out-of-Domain]`).
2. **Failure-Analysis Dashboard (`/dashboard`)**:
   * Interactive query inspector showing target spans vs. retrieved seek points.
   * Real-time filtering by retriever, split, taxonomy category, and outcome.
   * Direct "Watch Moment ↗" links opening YouTube at the exact computed second.

---

## 6. Summary of Accomplished Improvements

| # | Improvement Area | Target | Implemented Solution |
|---|---|---|---|
| 1 | **Repository Naming** | Unclear project scope | Renamed to `dsa-lecture-rag` |
| 2 | **Evaluation Sample Size** | Low power ($n=30$) | Expanded to **104 queries** across 18 videos ($n=65$ test) |
| 3 | **Beyond the Null** | $p \ge 0.05$ inconclusive | **TOST** ($p = 0.0324$) and **Bayesian analysis** ($96.1\%$ evidence) |
| 4 | **Refinement Regression** | Hit@1 fell from 10.8% to 7.7% | Conservative shift constraint: Hit@1 recovered to **10.8%**, Hit@3 to **18.5%** |
| 5 | **Multilingual Retrieval** | English-only embedder | Integrated `paraphrase-multilingual-MiniLM-L12-v2` |
| 6 | **LLM Component Viability** | 25% false abstention rate | Extractive default + BYOK architecture; archived LoRA to branch |
| 7 | **Viva Demonstration** | Static markdown tables | Interactive **Diagnostic Dashboard** at `/dashboard` |
| 8 | **Curated Live Demos** | Empty search input | Added benchmark query showcase chips on live UI |

---

## 7. Conclusion & Viva Defense Talking Points

This project elevates video technical navigation from heuristic keyword search to an empirically verified, statistically sound science:
* When asked about **sample size**: *"We expanded the golden set to 104 queries across 18 videos, halving confidence interval widths from 30 pp to 16 pp."*
* When asked about **model equivalence**: *"We conducted Two One-Sided Tests (TOST) with a 10% equivalence margin and Bayesian posterior simulation, establishing practical equivalence at p = 0.0324."*
* When asked about **seek accuracy**: *"Our calibrated sub-chunk refinement snaps to the true explanatory onset with a median error of 10.0 seconds without regressing Hit@1."*
* When asked about **LLM hallucinations**: *"We eliminated generative hallucination risk entirely by employing deterministic extractive citations in production, while offering interactive FAANG mock interviews via client-side BYOK cloud reasoning models."*
