"""Unit tests for edge-case stress tester and Grill Me interview engine."""

from ytrag.stress_tester import (
    get_edge_cases_for_problem,
    generate_grill_question,
    evaluate_grill_answer,
    CANONICAL_EDGE_CASES,
)


def test_get_edge_cases_array():
    cases = get_edge_cases_for_problem(topic="Arrays", title="Kadane's Algorithm")
    assert len(cases) >= 3
    assert any("Negative" in c["name"] for c in cases)
    assert any("Duplicates" in c["name"] for c in cases)


def test_get_edge_cases_linked_list():
    cases = get_edge_cases_for_problem(topic="Linked List", title="Detect Cycle")
    assert len(cases) >= 2
    assert any("Single Node" in c["name"] for c in cases)


def test_get_edge_cases_binary_search():
    cases = get_edge_cases_for_problem(topic="Binary Search", title="Search in Rotated Sorted Array")
    assert len(cases) >= 2
    assert any("Target Not Present" in c["name"] for c in cases)


def test_generate_grill_question_canonical():
    q = generate_grill_question(title="3Sum", topic="Arrays", code="def threeSum(nums): pass")
    assert "duplicate" in q["trap_warning"].lower()
    assert len(q["question"]) > 20
    assert q["source"] == "canonical"


def test_evaluate_grill_answer_strong():
    res = evaluate_grill_answer(
        question="How do you handle duplicates?",
        trap_warning="Failing to skip duplicates causes duplicate triplets.",
        user_answer="We sort the array first, and while left < right we advance left++ and right-- to skip all duplicate values.",
        title="3Sum",
        topic="Arrays",
    )
    assert res["score"] >= 7
    assert res["verdict"] in ("Outstanding", "Strong")
    assert len(res["feedback"]) > 10
    assert res["source"] == "rule_based"


def test_evaluate_grill_answer_empty():
    res = evaluate_grill_answer(
        question="How do you handle duplicates?",
        trap_warning="Trap: duplicate tuples",
        user_answer="",
        title="3Sum",
        topic="Arrays",
    )
    assert res["score"] == 0
    assert res["verdict"] == "No Answer Provided"


def test_evaluate_grill_answer_brief():
    res = evaluate_grill_answer(
        question="How do you handle duplicates?",
        trap_warning="Trap: duplicate tuples",
        user_answer="I use sets.",
        title="3Sum",
        topic="Arrays",
    )
    assert res["score"] <= 4
    assert res["verdict"] == "Missed the Trap"
