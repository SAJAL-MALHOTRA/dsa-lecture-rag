"""
Unit tests for LeetCode direct resolution and integration helper.
"""

from ytrag.leetcode_helper import (
    resolve_leetcode_info,
    parse_problem_examples,
    normalize_to_leetcode_slug,
    enrich_dsa_snippet_with_leetcode,
)
from ytrag.dsa_sheet import DSASolution


def test_resolve_canonical_problems():
    two_sum = resolve_leetcode_info("2_sum_problem", "2 Sum Problem", "Arrays")
    assert two_sum["url"] == "https://leetcode.com/problems/two-sum/"
    assert two_sum["slug"] == "two-sum"
    assert two_sum["difficulty"] == "Easy"
    assert two_sum["id"] == 1

    kadane = resolve_leetcode_info("kadane_s_algorithm", "Kadane's Algorithm", "Arrays")
    assert kadane["url"] == "https://leetcode.com/problems/maximum-subarray/"
    assert kadane["slug"] == "maximum-subarray"
    assert kadane["difficulty"] == "Medium"
    assert kadane["id"] == 53

    rain = resolve_leetcode_info("trapping_rainwater", "Trapping Rainwater", "Stack and Queues")
    assert rain["url"] == "https://leetcode.com/problems/trapping-rain-water/"
    assert rain["difficulty"] == "Hard"


def test_normalize_slug_fallback():
    slug = normalize_to_leetcode_slug("Longest Subarray With Sum K Problem")
    assert "longest-subarray-with-sum-k" in slug


def test_parse_problem_examples():
    text = (
        "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\n"
        "Example 1:\n"
        "Input: nums = [2,7,11,15], target = 9\n"
        "Output: [0,1]\n"
        "Explanation: Because nums[0] + nums[1] == 9, we return [0, 1].\n\n"
        "Example 2:\n"
        "Input: nums = [3,2,4], target = 6\n"
        "Output: [1,2]\n"
    )
    examples = parse_problem_examples(text)
    assert len(examples) == 2
    assert "nums = [2,7,11,15]" in examples[0]["input"]
    assert "[0,1]" in examples[0]["output"]
    assert "Because nums[0]" in examples[0]["explanation"]
    assert "nums = [3,2,4]" in examples[1]["input"]
    assert "[1,2]" in examples[1]["output"]


def test_enrich_dsa_snippet():
    snippet = {
        "id": "2_sum_problem",
        "title": "2 Sum Problem",
        "topic": "Arrays",
        "question": "Example 1:\nInput: nums = [2,7,11,15], target = 9\nOutput: [0,1]",
    }
    enrich_dsa_snippet_with_leetcode(snippet)
    assert snippet["leetcode_url"] == "https://leetcode.com/problems/two-sum/"
    assert snippet["leetcode_difficulty"] == "Easy"
    assert len(snippet["leetcode_examples"]) == 1


def test_dsa_solution_to_dict_includes_leetcode():
    sol = DSASolution(
        id="kadane_s_algorithm",
        title="Kadane's Algorithm",
        topic="01.Arrays",
        subtopic="Medium",
        question="Find max contiguous subarray sum.\nExample 1:\nInput: nums = [-2,1,-3,4,-1,2,1,-5,4]\nOutput: 6",
        approach="Maintain running max",
        code_cpp="int maxSubArray(...) {}",
        code_python="def maxSubArray(...) -> int:",
        code_java="class Solution {}",
        time_complexity="O(N)",
        space_complexity="O(1)",
        file_path="dummy.txt",
    )
    d = sol.to_dict()
    assert "leetcode_url" in d
    assert d["leetcode_url"] == "https://leetcode.com/problems/maximum-subarray/"
    assert d["leetcode_difficulty"] == "Medium"
    assert len(d["leetcode_examples"]) == 1
