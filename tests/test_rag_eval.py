"""
Unit tests for the 5-metric RAG evaluation suite.
"""

from eval.rag_eval import (
    context_precision,
    context_recall,
    evaluate_faithfulness,
    evaluate_relevancy,
    evaluate_correctness,
    run_rag_eval_suite,
)


def test_context_precision_deterministic():
    q = "how does binary search work on sorted arrays"
    good_chunk = "Binary search divides the sorted array into two halves by comparing the middle element with the target."
    bad_chunk = "In this lecture we discuss how to set up react hooks and useState components."
    
    score = context_precision(q, [good_chunk, bad_chunk])
    assert score == 0.5


def test_context_recall_deterministic():
    q = "what is the time complexity of merge sort"
    gt = "Merge sort has a time complexity of O(N log N) in all cases because it always divides the array into halves."
    ctx = "In merge sort, dividing takes log N levels and merging takes O(N) at each level, so total time is O(N log N)."
    
    res = context_recall(q, ctx, gt)
    assert res.score >= 0.7
    assert "Captured" in res.reason


def test_evaluate_faithfulness():
    q = "what pointers are used in cycle detection"
    ctx = "We use two pointers: a slow pointer moving 1 step and a fast pointer moving 2 steps."
    faithful_ans = "The algorithm uses two pointers: slow moving by 1 and fast moving by 2 steps."
    unfaithful_ans = "We use a hash table storing addresses with red-black trees and balanced AVL nodes."

    res_good = evaluate_faithfulness(q, ctx, faithful_ans)
    assert res_good.score >= 0.7

    res_bad = evaluate_faithfulness(q, ctx, unfaithful_ans)
    assert res_bad.score < 0.5


def test_evaluate_relevancy():
    q = "how to reverse a linked list"
    relevant_ans = "To reverse a linked list iteratively, maintain three pointers: prev, current, and next."
    off_topic_ans = "Quick sort picks a pivot element and partitions the array into smaller segments."

    res_rel = evaluate_relevancy(q, relevant_ans)
    assert res_rel.score >= 0.7

    res_off = evaluate_relevancy(q, off_topic_ans)
    assert res_off.score < 0.7


def test_evaluate_correctness():
    ans = "Kadane's algorithm finds maximum subarray sum in O(N) time and O(1) space."
    gt = "Kadane algorithm achieves O(N) time and O(1) auxiliary space complexity."

    res = evaluate_correctness(ans, gt)
    assert res.score >= 0.7


def test_run_rag_eval_suite():
    test_cases = [
        {
            "question": "What is two pointer technique in arrays?",
            "ground_truth": "Two pointers move from opposite ends or at different speeds to solve array problems in O(N) time.",
        }
    ]

    class FakeChunk:
        def __init__(self, text):
            self.snippet = text

    def fake_retriever(q):
        return [FakeChunk("Two pointers move across the array from left and right to find target pairs in O(N).")]

    def fake_generator(q, chunks):
        return "The two pointer technique uses pointers from left and right to scan array elements in O(N) time."

    report = run_rag_eval_suite(test_cases, fake_retriever, fake_generator)
    assert report["total_evaluated"] == 1
    assert "averages" in report
    assert report["averages"]["precision"] >= 0.7
    assert report["averages"]["faithfulness"] >= 0.7
