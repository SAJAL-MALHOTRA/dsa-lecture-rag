"""
5-Metric RAG Evaluation Framework for DSA Lecture Retrieval.

Adapted from the production AI engineering patterns in padho_with_pratyush_Ai_Enginner (week4/rag_eval).

Metrics Evaluated:
1. Context Precision: Fraction of retrieved chunks relevant to the user query.
2. Context Recall: Fraction of ground-truth concepts/facts captured in retrieved context.
3. Faithfulness: Degree to which generated response is grounded in retrieved context (0% hallucination).
4. Answer Relevancy: How directly the answer addresses the question.
5. Answer Correctness: Factual correctness compared against verified DSA canonical truth.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RAGMetricResult:
    score: float
    reason: str


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


# ============================================================================
# EVALUATION METRICS
# ============================================================================

def context_precision(
    question: str,
    retrieved_texts: list[str],
    llm_judge_fn: Optional[Any] = None,
) -> float:
    """
    Evaluates whether each retrieved chunk is relevant to the question.
    Precision = (relevant chunks count) / (total retrieved chunks count).
    """
    if not retrieved_texts:
        return 0.0

    if llm_judge_fn:
        relevant_count = 0
        for text in retrieved_texts:
            prompt = f"""
Evaluate if this retrieved lecture excerpt is relevant to the student query.

Query: {question}
Excerpt: {text}

Return JSON only:
{{"relevant": true, "reason": "brief explanation"}}
"""
            res = llm_judge_fn(prompt)
            if res.get("relevant", False):
                relevant_count += 1
        return round(relevant_count / len(retrieved_texts), 2)

    # Deterministic fallback judge
    qtoks = _tokenize(question)
    qtoks = {t for t in qtoks if len(t) > 2 and t not in {"how", "what", "why", "when", "the", "and", "for", "with"}}
    if not qtoks:
        return 1.0

    relevant_count = 0
    for text in retrieved_texts:
        ttoks = _tokenize(text)
        overlap = len(qtoks.intersection(ttoks))
        if overlap >= max(1, len(qtoks) // 3):
            relevant_count += 1

    return round(relevant_count / len(retrieved_texts), 2)


def context_recall(
    question: str,
    context: str,
    ground_truth: str,
    llm_judge_fn: Optional[Any] = None,
) -> RAGMetricResult:
    """
    Evaluates whether the retrieved context contains all required facts from the ground truth.
    """
    if not context.strip():
        return RAGMetricResult(score=0.0, reason="Context is empty.")

    if llm_judge_fn:
        prompt = f"""
Compare the retrieved context against the ground truth answer.
Did the context capture the key concepts required to answer the question?

Question: {question}
Ground Truth: {ground_truth}
Retrieved Context: {context}

Return JSON only:
{{"score": 1.0, "reason": "short explanation"}}
(1.0 = All key facts present, 0.7 = Mostly present, 0.5 = Partial, 0.0 = Missing)
"""
        res = llm_judge_fn(prompt)
        return RAGMetricResult(
            score=float(res.get("score", 0.0)),
            reason=res.get("reason", ""),
        )

    # Deterministic fallback judge
    stopwords = {"this", "that", "with", "have", "from", "they", "will", "because", "always", "into", "cases", "each"}
    gt_toks = _tokenize(ground_truth)
    gt_toks = {t for t in gt_toks if len(t) > 3 and t not in stopwords}
    if not gt_toks:
        return RAGMetricResult(score=1.0, reason="Ground truth empty.")

    ctx_toks = _tokenize(context)
    matched = set()
    for g in gt_toks:
        g_stem = g[:4]
        if any(c == g or (len(c) >= 4 and c[:4] == g_stem) for c in ctx_toks):
            matched.add(g)

    ratio = len(matched) / len(gt_toks)
    score = min(1.0, round(ratio * 1.25, 2))
    return RAGMetricResult(
        score=score,
        reason=f"Captured {len(matched)}/{len(gt_toks)} key concepts from ground truth.",
    )


def evaluate_faithfulness(
    question: str,
    context: str,
    answer: str,
    llm_judge_fn: Optional[Any] = None,
) -> RAGMetricResult:
    """
    Evaluates whether every claim in the answer is directly supported by the context.
    Detects hallucinations or ungrounded statements.
    """
    if not answer.strip():
        return RAGMetricResult(score=0.0, reason="Answer is empty.")
    if not context.strip():
        return RAGMetricResult(score=0.0, reason="Context is empty; answer cannot be grounded.")

    if llm_judge_fn:
        prompt = f"""
Determine whether the generated answer is completely supported by the retrieved context.

Retrieved Context: {context}
Generated Answer: {answer}

Return JSON only:
{{"score": 1.0, "reason": "short explanation"}}
(1.0 = 100% grounded in context, 0.7 = Minor unsupported claim, 0.5 = Partly grounded, 0.0 = Hallucinated)
"""
        res = llm_judge_fn(prompt)
        return RAGMetricResult(
            score=float(res.get("score", 0.0)),
            reason=res.get("reason", ""),
        )

    # Deterministic fallback judge: Check sentence coverage in context
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", answer) if len(s.strip()) > 15]
    if not sentences:
        return RAGMetricResult(score=1.0, reason="Answer contains no multi-word assertions.")

    ctx_toks = _tokenize(context)
    grounded_sents = 0
    for s in sentences:
        stoks = _tokenize(s)
        stoks = {t for t in stoks if len(t) > 3}
        if not stoks:
            grounded_sents += 1
            continue
        overlap = len(stoks.intersection(ctx_toks))
        if overlap / len(stoks) >= 0.35:
            grounded_sents += 1

    score = round(grounded_sents / len(sentences), 2)
    return RAGMetricResult(
        score=score,
        reason=f"{grounded_sents}/{len(sentences)} claims directly supported by lecture excerpts.",
    )


def evaluate_relevancy(
    question: str,
    answer: str,
    llm_judge_fn: Optional[Any] = None,
) -> RAGMetricResult:
    """
    Evaluates whether the generated answer actually answers the question.
    """
    if not answer.strip():
        return RAGMetricResult(score=0.0, reason="Answer is empty.")

    if llm_judge_fn:
        prompt = f"""
Does the generated answer directly address the student question?

Question: {question}
Answer: {answer}

Return JSON only:
{{"score": 1.0, "reason": "short explanation"}}
(1.0 = Directly answers, 0.7 = Mostly answers, 0.5 = Partially answers, 0.0 = Off-topic)
"""
        res = llm_judge_fn(prompt)
        return RAGMetricResult(
            score=float(res.get("score", 0.0)),
            reason=res.get("reason", ""),
        )

    qtoks = _tokenize(question)
    qtoks = {t for t in qtoks if len(t) > 3}
    ans_toks = _tokenize(answer)
    if not qtoks:
        return RAGMetricResult(score=1.0, reason="Query without specific keywords.")

    overlap = len(qtoks.intersection(ans_toks))
    ratio = overlap / len(qtoks)
    score = min(1.0, round(max(0.4, ratio * 1.2), 2))
    return RAGMetricResult(
        score=score,
        reason="Answer contains core query technical terminology.",
    )


def evaluate_correctness(
    answer: str,
    ground_truth: str,
    llm_judge_fn: Optional[Any] = None,
) -> RAGMetricResult:
    """
    Evaluates factual correctness against verified ground truth answer.
    """
    if not answer.strip() or not ground_truth.strip():
        return RAGMetricResult(score=0.0, reason="Answer or ground truth is empty.")

    if llm_judge_fn:
        prompt = f"""
Compare the generated answer with the verified ground truth.
Is the answer factually correct?

Generated Answer: {answer}
Ground Truth: {ground_truth}

Return JSON only:
{{"score": 1.0, "reason": "short explanation"}}
(1.0 = Completely correct, 0.7 = Minor omission, 0.5 = Partial, 0.0 = Contradictory)
"""
        res = llm_judge_fn(prompt)
        return RAGMetricResult(
            score=float(res.get("score", 0.0)),
            reason=res.get("reason", ""),
        )

    gt_toks = _tokenize(ground_truth)
    ans_toks = _tokenize(answer)
    overlap = len(gt_toks.intersection(ans_toks))
    score = min(1.0, round((overlap / max(1, len(gt_toks))) * 1.2, 2))
    return RAGMetricResult(
        score=score,
        reason=f"Matches {overlap}/{len(gt_toks)} ground-truth concepts.",
    )


# ============================================================================
# DIAGNOSTICS & EVALUATION RUNNER
# ============================================================================

def run_rag_eval_suite(
    test_cases: list[dict],
    retrieve_fn: Any,
    generate_fn: Any,
    llm_judge_fn: Optional[Any] = None,
) -> dict:
    """
    Runs the 5-metric evaluation over test cases and produces an actionable diagnostic summary.
    """
    all_scores = {
        "precision": [],
        "recall": [],
        "faithfulness": [],
        "relevancy": [],
        "correctness": [],
    }
    diagnostics = []

    for item in test_cases:
        question = item["question"]
        ground_truth = item.get("ground_truth", "")

        # 1. Retrieve
        retrieved_items = retrieve_fn(question)
        chunks_text = [
            r.snippet if hasattr(r, "snippet") else (r.text if hasattr(r, "text") else str(r))
            for r in retrieved_items
        ]
        context = "\n".join(chunks_text)

        # 2. Generate
        answer = generate_fn(question, retrieved_items)

        # 3. Calculate 5 Metrics
        prec = context_precision(question, chunks_text, llm_judge_fn)
        rec = context_recall(question, context, ground_truth, llm_judge_fn).score
        faith = evaluate_faithfulness(question, context, answer, llm_judge_fn).score
        rel = evaluate_relevancy(question, answer, llm_judge_fn).score
        corr = evaluate_correctness(answer, ground_truth, llm_judge_fn).score

        all_scores["precision"].append(prec)
        all_scores["recall"].append(rec)
        all_scores["faithfulness"].append(faith)
        all_scores["relevancy"].append(rel)
        all_scores["correctness"].append(corr)

        case_diag = {
            "question": question,
            "precision": prec,
            "recall": rec,
            "faithfulness": faith,
            "relevancy": rel,
            "correctness": corr,
            "issues": [],
        }

        if prec < 0.7:
            case_diag["issues"].append("❌ Low Context Precision: retrieval included irrelevant chunks.")
        if rec < 0.7:
            case_diag["issues"].append("❌ Low Context Recall: missed essential ground-truth context.")
        if faith < 0.7:
            case_diag["issues"].append("❌ Low Faithfulness: answer contains ungrounded claims.")
        if rel < 0.7:
            case_diag["issues"].append("❌ Low Relevancy: response does not directly address doubt.")
        if corr < 0.7:
            case_diag["issues"].append("❌ Low Correctness: factual discrepancies with verified DSA truth.")

        diagnostics.append(case_diag)

    averages = {
        metric: round(sum(vals) / max(1, len(vals)), 2)
        for metric, vals in all_scores.items()
    }

    return {
        "averages": averages,
        "total_evaluated": len(test_cases),
        "diagnostics": diagnostics,
    }
