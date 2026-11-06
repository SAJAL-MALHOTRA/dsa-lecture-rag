"""
LeetCode Resolution and Integration Helper.

Provides direct question resolution, canonical slug mapping, difficulty badges,
testcase parsing, and LeetCode action links inspired by shuzijun/leetcode-editor.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Base URL for official LeetCode problem portal
LEETCODE_BASE_URL = "https://leetcode.com/problems"

# Comprehensive canonical mapping of Striver A2Z problem IDs and titles to LeetCode
CANONICAL_LEETCODE_MAP: Dict[str, Dict[str, Any]] = {
    # Arrays
    "2_sum_problem": {
        "slug": "two-sum",
        "id": 1,
        "title": "Two Sum",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table"],
        "default_input": "nums = [2,7,11,15], target = 9",
        "default_output": "[0,1]",
    },
    "two_sum": {
        "slug": "two-sum",
        "id": 1,
        "title": "Two Sum",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table"],
        "default_input": "nums = [2,7,11,15], target = 9",
        "default_output": "[0,1]",
    },
    "kadane_s_algorithm": {
        "slug": "maximum-subarray",
        "id": 53,
        "title": "Maximum Subarray (Kadane's Algorithm)",
        "difficulty": "Medium",
        "tags": ["Array", "Divide and Conquer", "Dynamic Programming"],
        "default_input": "nums = [-2,1,-3,4,-1,2,1,-5,4]",
        "default_output": "6",
    },
    "sort_0_1_2": {
        "slug": "sort-colors",
        "id": 75,
        "title": "Sort Colors (Dutch National Flag)",
        "difficulty": "Medium",
        "tags": ["Array", "Two Pointers", "Sorting"],
        "default_input": "nums = [2,0,2,1,1,0]",
        "default_output": "[0,0,1,1,2,2]",
    },
    "majority_element": {
        "slug": "majority-element",
        "id": 169,
        "title": "Majority Element (Boyer-Moore Voting)",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table", "Divide and Conquer", "Counting"],
        "default_input": "nums = [3,2,3]",
        "default_output": "3",
    },
    "majority_element_2": {
        "slug": "majority-element-ii",
        "id": 229,
        "title": "Majority Element II (> N/3 times)",
        "difficulty": "Medium",
        "tags": ["Array", "Hash Table", "Sorting", "Counting"],
        "default_input": "nums = [3,2,3]",
        "default_output": "[3]",
    },
    "stock_buy_sell": {
        "slug": "best-time-to-buy-and-sell-stock",
        "id": 121,
        "title": "Best Time to Buy and Sell Stock",
        "difficulty": "Easy",
        "tags": ["Array", "Dynamic Programming"],
        "default_input": "prices = [7,1,5,3,6,4]",
        "default_output": "5",
    },
    "rearange_elements_by_sign": {
        "slug": "rearrange-array-elements-by-sign",
        "id": 2149,
        "title": "Rearrange Array Elements by Sign",
        "difficulty": "Medium",
        "tags": ["Array", "Two Pointers", "Simulation"],
        "default_input": "nums = [3,1,-2,-5,2,-4]",
        "default_output": "[3,-2,1,-5,2,-4]",
    },
    "next_permutation": {
        "slug": "next-permutation",
        "id": 31,
        "title": "Next Permutation",
        "difficulty": "Medium",
        "tags": ["Array", "Two Pointers"],
        "default_input": "nums = [1,2,3]",
        "default_output": "[1,3,2]",
    },
    "longest_consecutive_subsequence": {
        "slug": "longest-consecutive-sequence",
        "id": 128,
        "title": "Longest Consecutive Sequence",
        "difficulty": "Medium",
        "tags": ["Array", "Hash Table", "Union Find"],
        "default_input": "nums = [100,4,200,1,3,2]",
        "default_output": "4",
    },
    "set_matrix_0_s": {
        "slug": "set-matrix-zeroes",
        "id": 73,
        "title": "Set Matrix Zeroes",
        "difficulty": "Medium",
        "tags": ["Array", "Hash Table", "Matrix"],
        "default_input": "matrix = [[1,1,1],[1,0,1],[1,1,1]]",
        "default_output": "[[1,0,1],[0,0,0],[1,0,1]]",
    },
    "rotate_matrix": {
        "slug": "rotate-image",
        "id": 48,
        "title": "Rotate Image (Rotate Matrix 90°)",
        "difficulty": "Medium",
        "tags": ["Array", "Math", "Matrix"],
        "default_input": "matrix = [[1,2,3],[4,5,6],[7,8,9]]",
        "default_output": "[[7,4,1],[8,5,2],[9,6,3]]",
    },
    "spiral_traversal": {
        "slug": "spiral-matrix",
        "id": 54,
        "title": "Spiral Matrix",
        "difficulty": "Medium",
        "tags": ["Array", "Matrix", "Simulation"],
        "default_input": "matrix = [[1,2,3],[4,5,6],[7,8,9]]",
        "default_output": "[1,2,3,6,9,8,7,4,5]",
    },
    "pascal_triangle": {
        "slug": "pascals-triangle",
        "id": 118,
        "title": "Pascal's Triangle",
        "difficulty": "Easy",
        "tags": ["Array", "Dynamic Programming"],
        "default_input": "numRows = 5",
        "default_output": "[[1],[1,1],[1,2,1],[1,3,3,1],[1,4,6,4,1]]",
    },
    "3_sum": {
        "slug": "3sum",
        "id": 15,
        "title": "3Sum",
        "difficulty": "Medium",
        "tags": ["Array", "Two Pointers", "Sorting"],
        "default_input": "nums = [-1,0,1,2,-1,-4]",
        "default_output": "[[-1,-1,2],[-1,0,1]]",
    },
    "4_sum": {
        "slug": "4sum",
        "id": 18,
        "title": "4Sum",
        "difficulty": "Medium",
        "tags": ["Array", "Two Pointers", "Sorting"],
        "default_input": "nums = [1,0,-1,0,-2,2], target = 0",
        "default_output": "[[-2,-1,1,2],[-2,0,0,2]]",
    },
    "merge_overlapping_subinterval": {
        "slug": "merge-intervals",
        "id": 56,
        "title": "Merge Intervals",
        "difficulty": "Medium",
        "tags": ["Array", "Sorting"],
        "default_input": "intervals = [[1,3],[2,6],[8,10],[15,18]]",
        "default_output": "[[1,6],[8,10],[15,18]]",
    },
    "check_if_array_is_sorted_and_rotated": {
        "slug": "check-if-array-is-sorted-and-rotated",
        "id": 1752,
        "title": "Check if Array Is Sorted and Rotated",
        "difficulty": "Easy",
        "tags": ["Array"],
        "default_input": "nums = [3,4,5,1,2]",
        "default_output": "true",
    },
    "remove_duplicates_from_sorted_array": {
        "slug": "remove-duplicates-from-sorted-array",
        "id": 26,
        "title": "Remove Duplicates from Sorted Array",
        "difficulty": "Easy",
        "tags": ["Array", "Two Pointers"],
        "default_input": "nums = [1,1,2]",
        "default_output": "2, nums = [1,2,_]",
    },
    "move_0_s_to_end": {
        "slug": "move-zeroes",
        "id": 283,
        "title": "Move Zeroes",
        "difficulty": "Easy",
        "tags": ["Array", "Two Pointers"],
        "default_input": "nums = [0,1,0,3,12]",
        "default_output": "[1,3,12,0,0]",
    },
    "missing_number": {
        "slug": "missing-number",
        "id": 268,
        "title": "Missing Number",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table", "Math", "Bit Manipulation"],
        "default_input": "nums = [3,0,1]",
        "default_output": "2",
    },
    "max_consecutive_1_s": {
        "slug": "max-consecutive-ones",
        "id": 485,
        "title": "Max Consecutive Ones",
        "difficulty": "Easy",
        "tags": ["Array"],
        "default_input": "nums = [1,1,0,1,1,1]",
        "default_output": "3",
    },
    "rotate_array_left_right_by_k_places": {
        "slug": "rotate-array",
        "id": 189,
        "title": "Rotate Array",
        "difficulty": "Medium",
        "tags": ["Array", "Math", "Two Pointers"],
        "default_input": "nums = [1,2,3,4,5,6,7], k = 3",
        "default_output": "[5,6,7,1,2,3,4]",
    },
    "number_of_subarray_sum_equal_k": {
        "slug": "subarray-sum-equals-k",
        "id": 560,
        "title": "Subarray Sum Equals K",
        "difficulty": "Medium",
        "tags": ["Array", "Hash Table", "Prefix Sum"],
        "default_input": "nums = [1,1,1], k = 2",
        "default_output": "2",
    },

    # Binary Search
    "search_insert_position": {
        "slug": "search-insert-position",
        "id": 35,
        "title": "Search Insert Position",
        "difficulty": "Easy",
        "tags": ["Array", "Binary Search"],
        "default_input": "nums = [1,3,5,6], target = 5",
        "default_output": "2",
    },
    "search_in_rotated_sorted_array": {
        "slug": "search-in-rotated-sorted-array",
        "id": 33,
        "title": "Search in Rotated Sorted Array",
        "difficulty": "Medium",
        "tags": ["Array", "Binary Search"],
        "default_input": "nums = [4,5,6,7,0,1,2], target = 0",
        "default_output": "4",
    },
    "find_minimum_in_rotated_sorted_array": {
        "slug": "find-minimum-in-rotated-sorted-array",
        "id": 153,
        "title": "Find Minimum in Rotated Sorted Array",
        "difficulty": "Medium",
        "tags": ["Array", "Binary Search"],
        "default_input": "nums = [3,4,5,1,2]",
        "default_output": "1",
    },
    "single_element_in_a_sorted_array": {
        "slug": "single-element-in-a-sorted-array",
        "id": 540,
        "title": "Single Element in a Sorted Array",
        "difficulty": "Medium",
        "tags": ["Array", "Binary Search"],
        "default_input": "nums = [1,1,2,3,3,4,4,8,8]",
        "default_output": "2",
    },
    "find_peak_element": {
        "slug": "find-peak-element",
        "id": 162,
        "title": "Find Peak Element",
        "difficulty": "Medium",
        "tags": ["Array", "Binary Search"],
        "default_input": "nums = [1,2,3,1]",
        "default_output": "2",
    },
    "koko_eating_bananas": {
        "slug": "koko-eating-bananas",
        "id": 875,
        "title": "Koko Eating Bananas",
        "difficulty": "Medium",
        "tags": ["Array", "Binary Search"],
        "default_input": "piles = [3,6,7,11], h = 8",
        "default_output": "4",
    },
    "capacity_to_ship_packages": {
        "slug": "capacity-to-ship-packages-within-d-days",
        "id": 1011,
        "title": "Capacity To Ship Packages Within D Days",
        "difficulty": "Medium",
        "tags": ["Array", "Binary Search"],
        "default_input": "weights = [1,2,3,4,5,6,7,8,9,10], days = 5",
        "default_output": "15",
    },
    "median_of_2_sorted_arrays": {
        "slug": "median-of-two-sorted-arrays",
        "id": 4,
        "title": "Median of Two Sorted Arrays",
        "difficulty": "Hard",
        "tags": ["Array", "Binary Search", "Divide and Conquer"],
        "default_input": "nums1 = [1,3], nums2 = [2]",
        "default_output": "2.00000",
    },

    # Linked List
    "reverse_a_linked_list": {
        "slug": "reverse-linked-list",
        "id": 206,
        "title": "Reverse Linked List",
        "difficulty": "Easy",
        "tags": ["Linked List", "Recursion"],
        "default_input": "head = [1,2,3,4,5]",
        "default_output": "[5,4,3,2,1]",
    },
    "middle_of_a_linked_list": {
        "slug": "middle-of-the-linked-list",
        "id": 876,
        "title": "Middle of the Linked List (Tortoise and Hare)",
        "difficulty": "Easy",
        "tags": ["Linked List", "Two Pointers"],
        "default_input": "head = [1,2,3,4,5]",
        "default_output": "[3,4,5]",
    },
    "detect_a_loop_in_linked_list": {
        "slug": "linked-list-cycle",
        "id": 141,
        "title": "Linked List Cycle (Floyd's Cycle Finding)",
        "difficulty": "Easy",
        "tags": ["Hash Table", "Linked List", "Two Pointers"],
        "default_input": "head = [3,2,0,-4], pos = 1",
        "default_output": "true",
    },
    "starting_point_of_loop_in_linked_list": {
        "slug": "linked-list-cycle-ii",
        "id": 142,
        "title": "Linked List Cycle II (Find Start Node)",
        "difficulty": "Medium",
        "tags": ["Hash Table", "Linked List", "Two Pointers"],
        "default_input": "head = [3,2,0,-4], pos = 1",
        "default_output": "node at index 1",
    },
    "check_if_linked_list_is_palindrome": {
        "slug": "palindrome-linked-list",
        "id": 234,
        "title": "Palindrome Linked List",
        "difficulty": "Easy",
        "tags": ["Linked List", "Two Pointers", "Stack", "Recursion"],
        "default_input": "head = [1,2,2,1]",
        "default_output": "true",
    },
    "remove_nth_node_from_end": {
        "slug": "remove-nth-node-from-end-of-list",
        "id": 19,
        "title": "Remove Nth Node From End of List",
        "difficulty": "Medium",
        "tags": ["Linked List", "Two Pointers"],
        "default_input": "head = [1,2,3,4,5], n = 2",
        "default_output": "[1,2,3,5]",
    },
    "merge_two_sorted_lists": {
        "slug": "merge-two-sorted-lists",
        "id": 21,
        "title": "Merge Two Sorted Lists",
        "difficulty": "Easy",
        "tags": ["Linked List", "Recursion"],
        "default_input": "list1 = [1,2,4], list2 = [1,3,4]",
        "default_output": "[1,1,2,3,4,4]",
    },
    "sort_a_linked_list": {
        "slug": "sort-list",
        "id": 148,
        "title": "Sort List (Merge Sort on Linked List)",
        "difficulty": "Medium",
        "tags": ["Linked List", "Two Pointers", "Divide and Conquer", "Sorting"],
        "default_input": "head = [4,2,1,3]",
        "default_output": "[1,2,3,4]",
    },

    # Stacks and Queues
    "valid_parentheses": {
        "slug": "valid-parentheses",
        "id": 20,
        "title": "Valid Parentheses",
        "difficulty": "Easy",
        "tags": ["String", "Stack"],
        "default_input": 's = "()[]{}"',
        "default_output": "true",
    },
    "next_greater_element": {
        "slug": "next-greater-element-i",
        "id": 496,
        "title": "Next Greater Element I",
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table", "Stack", "Monotonic Stack"],
        "default_input": "nums1 = [4,1,2], nums2 = [1,3,4,2]",
        "default_output": "[-1,3,-1]",
    },
    "trapping_rainwater": {
        "slug": "trapping-rain-water",
        "id": 42,
        "title": "Trapping Rain Water",
        "difficulty": "Hard",
        "tags": ["Array", "Two Pointers", "Dynamic Programming", "Stack", "Monotonic Stack"],
        "default_input": "height = [0,1,0,2,1,0,1,3,2,1,2,1]",
        "default_output": "6",
    },
    "largest_rectangle_in_histogram": {
        "slug": "largest-rectangle-in-histogram",
        "id": 84,
        "title": "Largest Rectangle in Histogram",
        "difficulty": "Hard",
        "tags": ["Array", "Stack", "Monotonic Stack"],
        "default_input": "heights = [2,1,5,6,2,3]",
        "default_output": "10",
    },
    "sliding_window_maximum": {
        "slug": "sliding-window-maximum",
        "id": 239,
        "title": "Sliding Window Maximum (Monotonic Deque)",
        "difficulty": "Hard",
        "tags": ["Array", "Queue", "Sliding Window", "Heap", "Monotonic Queue"],
        "default_input": "nums = [1,3,-1,-3,5,3,6,7], k = 3",
        "default_output": "[3,3,5,5,6,7]",
    },
    "lru_cache": {
        "slug": "lru-cache",
        "id": 146,
        "title": "LRU Cache (Least Recently Used)",
        "difficulty": "Medium",
        "tags": ["Hash Table", "Linked List", "Design", "Doubly-Linked List"],
        "default_input": '["LRUCache", "put", "put", "get", "put", "get", "put", "get", "get", "get"]\n[[2], [1, 1], [2, 2], [1], [3, 3], [2], [4, 4], [1], [3], [4]]',
        "default_output": "[null, null, null, 1, null, -1, null, -1, 3, 4]",
    },

    # Binary Trees
    "preorder_traversal": {
        "slug": "binary-tree-preorder-traversal",
        "id": 144,
        "title": "Binary Tree Preorder Traversal",
        "difficulty": "Easy",
        "tags": ["Stack", "Tree", "Depth-First Search", "Binary Tree"],
        "default_input": "root = [1,null,2,3]",
        "default_output": "[1,2,3]",
    },
    "inorder_traversal": {
        "slug": "binary-tree-inorder-traversal",
        "id": 94,
        "title": "Binary Tree Inorder Traversal",
        "difficulty": "Easy",
        "tags": ["Stack", "Tree", "Depth-First Search", "Binary Tree"],
        "default_input": "root = [1,null,2,3]",
        "default_output": "[1,3,2]",
    },
    "postorder_traversal": {
        "slug": "binary-tree-postorder-traversal",
        "id": 145,
        "title": "Binary Tree Postorder Traversal",
        "difficulty": "Easy",
        "tags": ["Stack", "Tree", "Depth-First Search", "Binary Tree"],
        "default_input": "root = [1,null,2,3]",
        "default_output": "[3,2,1]",
    },
    "level_order_traversal": {
        "slug": "binary-tree-level-order-traversal",
        "id": 102,
        "title": "Binary Tree Level Order Traversal",
        "difficulty": "Medium",
        "tags": ["Tree", "Breadth-First Search", "Binary Tree"],
        "default_input": "root = [3,9,20,null,null,15,7]",
        "default_output": "[[3],[9,20],[15,7]]",
    },
    "maximum_depth_in_binary_tree": {
        "slug": "maximum-depth-of-binary-tree",
        "id": 104,
        "title": "Maximum Depth of Binary Tree",
        "difficulty": "Easy",
        "tags": ["Tree", "Depth-First Search", "Breadth-First Search", "Binary Tree"],
        "default_input": "root = [3,9,20,null,null,15,7]",
        "default_output": "3",
    },
    "diameter_of_binary_tree": {
        "slug": "diameter-of-binary-tree",
        "id": 543,
        "title": "Diameter of Binary Tree",
        "difficulty": "Easy",
        "tags": ["Tree", "Depth-First Search", "Binary Tree"],
        "default_input": "root = [1,2,3,4,5]",
        "default_output": "3",
    },
    "lowest_common_ancestor_in_binary_tree": {
        "slug": "lowest-common-ancestor-of-a-binary-tree",
        "id": 236,
        "title": "Lowest Common Ancestor of a Binary Tree",
        "difficulty": "Medium",
        "tags": ["Tree", "Depth-First Search", "Binary Tree"],
        "default_input": "root = [3,5,1,6,2,0,8,null,null,7,4], p = 5, q = 1",
        "default_output": "3",
    },

    # Graphs
    "number_of_islands": {
        "slug": "number-of-islands",
        "id": 200,
        "title": "Number of Islands",
        "difficulty": "Medium",
        "tags": ["Array", "Depth-First Search", "Breadth-First Search", "Union Find", "Matrix"],
        "default_input": 'grid = [\n  ["1","1","1","1","0"],\n  ["1","1","0","1","0"],\n  ["1","1","0","0","0"],\n  ["0","0","0","0","0"]\n]',
        "default_output": "1",
    },
    "rotting_oranges": {
        "slug": "rotting-oranges",
        "id": 994,
        "title": "Rotting Oranges",
        "difficulty": "Medium",
        "tags": ["Array", "Breadth-First Search", "Matrix"],
        "default_input": "grid = [[2,1,1],[1,1,0],[0,1,1]]",
        "default_output": "4",
    },
    "course_schedule_1": {
        "slug": "course-schedule",
        "id": 207,
        "title": "Course Schedule (Topological Sort / Kahn's)",
        "difficulty": "Medium",
        "tags": ["Depth-First Search", "Breadth-First Search", "Graph", "Topological Sort"],
        "default_input": "numCourses = 2, prerequisites = [[1,0]]",
        "default_output": "true",
    },

    # Dynamic Programming
    "climbing_stairs": {
        "slug": "climbing-stairs",
        "id": 70,
        "title": "Climbing Stairs",
        "difficulty": "Easy",
        "tags": ["Math", "Dynamic Programming", "Memoization"],
        "default_input": "n = 3",
        "default_output": "3",
    },
    "house_robber": {
        "slug": "house-robber",
        "id": 198,
        "title": "House Robber",
        "difficulty": "Medium",
        "tags": ["Array", "Dynamic Programming"],
        "default_input": "nums = [1,2,3,1]",
        "default_output": "4",
    },
    "coin_change": {
        "slug": "coin-change",
        "id": 322,
        "title": "Coin Change",
        "difficulty": "Medium",
        "tags": ["Array", "Dynamic Programming", "Breadth-First Search"],
        "default_input": "coins = [1,2,5], amount = 11",
        "default_output": "3",
    },
    "longest_common_subsequence": {
        "slug": "longest-common-subsequence",
        "id": 1143,
        "title": "Longest Common Subsequence",
        "difficulty": "Medium",
        "tags": ["String", "Dynamic Programming"],
        "default_input": 'text1 = "abcde", text2 = "ace"',
        "default_output": "3",
    },
    "longest_increasing_subsequence": {
        "slug": "longest-increasing-subsequence",
        "id": 300,
        "title": "Longest Increasing Subsequence (LIS)",
        "difficulty": "Medium",
        "tags": ["Array", "Binary Search", "Dynamic Programming"],
        "default_input": "nums = [10,9,2,5,3,7,101,18]",
        "default_output": "4",
    },
    "edit_distance": {
        "slug": "edit-distance",
        "id": 72,
        "title": "Edit Distance (Levenshtein Distance)",
        "difficulty": "Medium",
        "tags": ["String", "Dynamic Programming"],
        "default_input": 'word1 = "horse", word2 = "ros"',
        "default_output": "3",
    },
}

# Cache for curriculum graph LeetCode practice problems
_CURRICULUM_LEETCODE_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _load_curriculum_leetcode() -> Dict[str, Dict[str, Any]]:
    """Loads verified LeetCode problem URLs from data/curriculum_graph.json."""
    global _CURRICULUM_LEETCODE_CACHE
    if _CURRICULUM_LEETCODE_CACHE is not None:
        return _CURRICULUM_LEETCODE_CACHE

    _CURRICULUM_LEETCODE_CACHE = {}
    cg_path = Path(__file__).resolve().parent.parent / "data" / "curriculum_graph.json"
    if not cg_path.exists():
        return _CURRICULUM_LEETCODE_CACHE

    try:
        with open(cg_path, "r", encoding="utf-8") as f:
            cg = json.load(f)
        for topic_key, topic_data in cg.items():
            for p in topic_data.get("practice_problems", []):
                url = p.get("url", "")
                if "leetcode.com/problems/" in url:
                    slug = url.split("leetcode.com/problems/")[1].strip("/").split("/")[0]
                    title = p.get("title", "")
                    clean_title_key = re.sub(r"[^a-zA-Z0-9]", "", title.lower())
                    clean_slug_key = re.sub(r"[^a-zA-Z0-9]", "", slug.lower())
                    entry = {
                        "slug": slug,
                        "title": title,
                        "url": f"{LEETCODE_BASE_URL}/{slug}/",
                        "difficulty": p.get("difficulty", "Medium"),
                        "tags": [t.strip() for t in p.get("tag", "").split(",") if t.strip()],
                    }
                    if clean_title_key:
                        _CURRICULUM_LEETCODE_CACHE[clean_title_key] = entry
                    if clean_slug_key:
                        _CURRICULUM_LEETCODE_CACHE[clean_slug_key] = entry
    except Exception:
        pass

    return _CURRICULUM_LEETCODE_CACHE


def parse_problem_examples(question_text: str) -> List[Dict[str, str]]:
    """
    Parses Example blocks from problem question statements (Input / Output / Explanation)
    for shuzijun/leetcode-editor interactive test cases.
    """
    if not question_text:
        return []

    examples: List[Dict[str, str]] = []
    # Match blocks like "Example 1:" or "Example:" or "Input:"
    pattern = re.compile(
        r"(?:Example\s*(\d+)?[:\n]|Input:)(.*?)(?=(?:Example|\Z))",
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(question_text):
        block = match.group(0)
        in_m = re.search(r"Input:\s*(.+?)(?=\n\s*Output:|\Z)", block, re.DOTALL | re.IGNORECASE)
        out_m = re.search(r"Output:\s*(.+?)(?=\n\s*Explanation:|\n\s*Example|\Z)", block, re.DOTALL | re.IGNORECASE)
        exp_m = re.search(r"Explanation:\s*(.+?)(?=\n\s*Example|\Z)", block, re.DOTALL | re.IGNORECASE)
        if in_m or out_m:
            in_val = in_m.group(1).strip() if in_m else ""
            out_val = out_m.group(1).strip() if out_m else ""
            exp_val = exp_m.group(1).strip() if exp_m else ""
            examples.append({
                "input": in_val,
                "output": out_val,
                "explanation": exp_val,
            })

    return examples


def normalize_to_leetcode_slug(raw_str: str) -> str:
    """Normalizes any problem title or ID into a standard LeetCode slug."""
    s = raw_str.lower()
    # Strip common noise tokens
    s = re.sub(r"\b(problem|algorithm|algo|approach|solution|in cpp|in python|using|striver|sheet)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def resolve_leetcode_info(
    sol_id: str = "",
    title: str = "",
    topic: str = "",
    question: str = "",
) -> Dict[str, Any]:
    """
    Resolves comprehensive LeetCode metadata, direct URLs, difficulty ratings,
    and test cases for a given DSA problem.
    """
    clean_id = (sol_id or "").lower().strip()
    clean_title = (title or "").lower().strip()

    # 1. Check direct canonical map
    meta = None
    if clean_id in CANONICAL_LEETCODE_MAP:
        meta = dict(CANONICAL_LEETCODE_MAP[clean_id])
    else:
        # Check title keywords against canonical map keys
        for key, entry in CANONICAL_LEETCODE_MAP.items():
            if key in clean_id or key.replace("_", " ") in clean_title:
                meta = dict(entry)
                break

    # 2. Check curriculum graph cache
    if not meta:
        curriculum = _load_curriculum_leetcode()
        norm_key = re.sub(r"[^a-zA-Z0-9]", "", clean_title)
        norm_id = re.sub(r"[^a-zA-Z0-9]", "", clean_id)
        if norm_key in curriculum:
            meta = dict(curriculum[norm_key])
        elif norm_id in curriculum:
            meta = dict(curriculum[norm_id])

    # 3. Fallback: normalize slug
    if not meta:
        fallback_slug = normalize_to_leetcode_slug(clean_id or clean_title)
        if not fallback_slug:
            fallback_slug = "problem"
        meta = {
            "slug": fallback_slug,
            "title": title or fallback_slug.replace("-", " ").title(),
            "difficulty": "Medium",
            "tags": [topic] if topic else ["Algorithms"],
        }

    slug = meta.get("slug", "two-sum")
    url = f"{LEETCODE_BASE_URL}/{slug}/"
    submit_url = f"{LEETCODE_BASE_URL}/{slug}/"

    # Extract examples from problem statement
    examples = parse_problem_examples(question)
    if not examples and meta.get("default_input"):
        examples.append({
            "input": meta.get("default_input", ""),
            "output": meta.get("default_output", ""),
            "explanation": "Standard LeetCode example test case",
        })

    return {
        "url": url,
        "slug": slug,
        "submit_url": submit_url,
        "title": meta.get("title", title),
        "difficulty": meta.get("difficulty", "Medium"),
        "id": meta.get("id"),
        "tags": meta.get("tags", [topic] if topic else []),
        "default_input": meta.get("default_input", examples[0]["input"] if examples else ""),
        "default_output": meta.get("default_output", examples[0]["output"] if examples else ""),
        "examples": examples,
    }


def enrich_dsa_snippet_with_leetcode(dsa_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Enriches a DSA problem dictionary with LeetCode metadata, direct links, and examples."""
    if not dsa_dict or not isinstance(dsa_dict, dict):
        return dsa_dict

    sol_id = dsa_dict.get("id", "")
    title = dsa_dict.get("title", "")
    topic = dsa_dict.get("topic", "")
    question = dsa_dict.get("question", "")

    lc = resolve_leetcode_info(sol_id, title, topic, question)
    dsa_dict["leetcode_url"] = lc["url"]
    dsa_dict["leetcode_slug"] = lc["slug"]
    dsa_dict["leetcode_submit_url"] = lc["submit_url"]
    dsa_dict["leetcode_difficulty"] = lc["difficulty"]
    dsa_dict["leetcode_title"] = lc["title"]
    dsa_dict["leetcode_tags"] = lc["tags"]
    dsa_dict["leetcode_id"] = lc["id"]
    dsa_dict["leetcode_examples"] = lc["examples"]
    dsa_dict["leetcode_default_input"] = lc["default_input"]
    dsa_dict["leetcode_default_output"] = lc["default_output"]
    return dsa_dict
