"""
Parser for ashishps1/awesome-leetcode-resources.
Extracts pattern implementations (C++, Python), prose pattern explanations,
and Must-Read LeetCode article templates with fallback scraping.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional

from data_ingestion.schemas import PatternChunk

logger = logging.getLogger(__name__)

TOPIC_MAPPING = {
    "two_pointers": "two_pointers",
    "twopointers": "two_pointers",
    "sliding_window": "sliding_window",
    "slidingwindow": "sliding_window",
    "fast_and_slow_pointers": "two_pointers",
    "fastandslowpointers": "two_pointers",
    "kadane": "arrays",
    "kadane_algorithm": "arrays",
    "kadanealgorithm": "arrays",
    "monotonic_stack": "stacks_queues",
    "monotonicstack": "stacks_queues",
    "reverse_list": "linked_list",
    "reverselist": "linked_list",
    "top_k_elements": "heaps",
    "topkelements": "heaps",
    "level_order_traversal": "trees",
    "levelordertraversal": "trees",
    "prefix_sum": "arrays",
    "overlapping_intervals": "arrays",
    "binary_search": "sorting_searching",
    "backtracking": "recursion",
    "dynamic_programming": "dynamic_programming",
    "dp": "dynamic_programming",
    "trees": "trees",
    "graphs": "graphs",
    "tries": "tries",
    "bit_manipulation": "bit_manipulation",
}

# 20+ Canonical Coding Patterns with rich prose explanations
CORE_PATTERN_EXPLANATIONS = [
    {
        "pattern_name": "Two Pointers",
        "canonical_topic": "two_pointers",
        "title": "Two Pointers Pattern Intuition & Mechanics",
        "text": (
            "The Two Pointers pattern uses two converging or parallel pointers to traverse a linear data structure "
            "(typically a sorted array or string) simultaneously. By evaluating conditions across both pointers, "
            "it reduces search spaces from O(N^2) brute force to optimal O(N) linear time.\n\n"
            "Key Indicators:\n"
            "- Target array is sorted or can be sorted without violating problem constraints.\n"
            "- Searching for pairs, triplets, or subsegments satisfying a sum or comparison target.\n"
            "- Palindrome verification or in-place element swapping (e.g., Two Sum II, 3Sum, Container With Most Water).\n\n"
            "Complexity:\n"
            "- Time Complexity: O(N) or O(N log N) if pre-sorting is required.\n"
            "- Space Complexity: O(1) auxiliary space."
        ),
    },
    {
        "pattern_name": "Sliding Window",
        "canonical_topic": "sliding_window",
        "title": "Sliding Window Pattern Intuition & Mechanics",
        "text": (
            "The Sliding Window pattern maintains a contiguous subarray or substring boundary defined by two pointers "
            "[left, right]. As the right pointer expands the window to include elements, the left pointer shrinks the "
            "window when constraints are violated, eliminating redundant recalculations.\n\n"
            "Variants:\n"
            "1. Fixed Window: Window size K remains constant; add incoming element at right, subtract outgoing at left.\n"
            "2. Dynamic Window: Window expands until a condition is broken, then shrinks left pointer until valid.\n\n"
            "Key Indicators:\n"
            "- Problems involving contiguous subarrays, longest/shortest substrings with K distinct characters, "
            "or maximum sum subarray of size K.\n\n"
            "Complexity:\n"
            "- Time Complexity: O(N) as each element is visited at most twice (by left and right pointers).\n"
            "- Space Complexity: O(K) or O(1) using a hash map or frequency array."
        ),
    },
    {
        "pattern_name": "Fast and Slow Pointers (Hare & Tortoise)",
        "canonical_topic": "two_pointers",
        "title": "Fast & Slow Pointers (Floyd's Cycle Detection)",
        "text": (
            "The Fast and Slow pointer method (Floyd's algorithm) moves two pointers at different speeds (slow moves 1 step, "
            "fast moves 2 steps) through a sequence or linked list. If a cycle exists, the fast pointer will eventually "
            "lap and meet the slow pointer within the loop.\n\n"
            "Applications:\n"
            "- Linked List Cycle Detection (LeetCode 141, 142).\n"
            "- Finding the middle of a Linked List in a single pass (slow lands on middle when fast hits null).\n"
            "- Palindrome Linked List verification.\n"
            "- Cycle detection in circular arrays and happy number sequences.\n\n"
            "Complexity:\n"
            "- Time Complexity: O(N) traversal.\n"
            "- Space Complexity: O(1) space."
        ),
    },
    {
        "pattern_name": "Prefix Sum",
        "canonical_topic": "arrays",
        "title": "Prefix Sum Pattern Intuition & Mechanics",
        "text": (
            "Prefix Sum precomputes cumulative sums of an array such that prefix[i] = nums[0] + ... + nums[i-1]. "
            "This enables O(1) range sum queries between any indices [left, right] via prefix[right + 1] - prefix[left].\n\n"
            "When combined with a Hash Map storing running sum frequencies: map[prefix_sum] -> count or earliest index, "
            "it solves subarray sum problems (like Subarray Sum Equals K, Continuous Subarray Sum) in single-pass O(N) time.\n\n"
            "Complexity:\n"
            "- Time Complexity: O(N) preprocessing, O(1) per range query.\n"
            "- Space Complexity: O(N) for prefix array or hash map."
        ),
    },
    {
        "pattern_name": "Kadane's Algorithm",
        "canonical_topic": "arrays",
        "title": "Kadane's Algorithm: Maximum Subarray Sum",
        "text": (
            "Kadane's algorithm solves the Maximum Subarray problem in linear time by making a dynamic local choice "
            "at each index: either extend the existing running sum with nums[i], or reset and start a new subarray at nums[i].\n\n"
            "Intuition:\n"
            "current_sum = max(nums[i], current_sum + nums[i])\n"
            "max_sum = max(max_sum, current_sum)\n"
            "If current_sum drops below 0, carrying it into future indices only penalizes the sum, so we reset.\n\n"
            "Complexity:\n"
            "- Time: O(N), single pass.\n"
            "- Space: O(1) variables."
        ),
    },
    {
        "pattern_name": "Monotonic Stack",
        "canonical_topic": "stacks_queues",
        "title": "Monotonic Stack Pattern Intuition & Mechanics",
        "text": (
            "A Monotonic Stack maintains elements in strictly increasing or decreasing order. Whenever an incoming "
            "element violates the monotonic invariant, stack elements are popped, revealing the 'Next Greater Element' "
            "or 'Next Smaller Element' for every popped item in amortized O(N) time.\n\n"
            "Key Indicators:\n"
            "- Finding the nearest greater/smaller element to the left or right.\n"
            "- Calculating boundary spans in histogram problems (e.g. Largest Rectangle in Histogram, Trapping Rain Water).\n"
            "- Online stock span and daily temperatures.\n\n"
            "Complexity:\n"
            "- Time Complexity: O(N) amortized (each element is pushed and popped at most once).\n"
            "- Space Complexity: O(N) stack capacity."
        ),
    },
    {
        "pattern_name": "Top K Elements (Heap / Priority Queue)",
        "canonical_topic": "heaps",
        "title": "Top K Elements Pattern Using Heaps",
        "text": (
            "To find the K largest or smallest elements in an unsorted collection of size N without sorting the whole array:\n"
            "- Top K Largest: Maintain a Min-Heap of size K. If current element > min_heap.top(), pop min and push element.\n"
            "- Top K Smallest: Maintain a Max-Heap of size K.\n\n"
            "Key Indicators:\n"
            "- Finding K-th largest, frequent elements, or K closest points.\n\n"
            "Complexity:\n"
            "- Time Complexity: O(N log K) compared to O(N log N) sorting.\n"
            "- Space Complexity: O(K) heap storage."
        ),
    },
    {
        "pattern_name": "Level Order Traversal (BFS)",
        "canonical_topic": "trees",
        "title": "Tree Level Order Traversal (Breadth-First Search)",
        "text": (
            "Level Order Traversal explores nodes in a tree or graph level-by-level using a FIFO Queue. "
            "At each iteration, we snapshot queue.size() to process all nodes residing on the current depth before advancing.\n\n"
            "Key Indicators:\n"
            "- Shortest path in unweighted graphs or grids.\n"
            "- Tree zigzag traversal, right/left side views, or minimum depth of binary tree.\n\n"
            "Complexity:\n"
            "- Time: O(V + E) for graphs, O(N) for trees.\n"
            "- Space: O(W) where W is the maximum width of the tree/graph level."
        ),
    },
    {
        "pattern_name": "In-place Reversal of a Linked List",
        "canonical_topic": "linked_list",
        "title": "In-Place Linked List Reversal Pattern",
        "text": (
            "Reversing a singly linked list in-place utilizes three pointers (prev, curr, next) to flip pointer directions "
            "without allocating additional nodes.\n\n"
            "Algorithm:\n"
            "prev = None; curr = head\n"
            "while curr:\n"
            "    nxt = curr.next; curr.next = prev; prev = curr; curr = nxt\n"
            "return prev\n\n"
            "Extensions: Reverse sublist between indices [left, right], Reverse Nodes in K-Group.\n"
            "Complexity: O(N) time, O(1) space."
        ),
    },
    {
        "pattern_name": "Overlapping Intervals",
        "canonical_topic": "arrays",
        "title": "Overlapping Intervals & Merge Technique",
        "text": (
            "Interval problems process intervals [start, end] by sorting them primarily by start time. "
            "Once sorted, two intervals [A, B] and [C, D] overlap if and only if C <= B.\n\n"
            "Actions:\n"
            "- Merge: Combined interval is [min(A, C), max(B, D)].\n"
            "- Conflict / Non-overlapping: Keep interval with earlier end time (Greedy interval scheduling).\n\n"
            "Common Problems: Merge Intervals, Non-overlapping Intervals, Meeting Rooms II.\n"
            "Complexity: O(N log N) due to sorting, O(1) auxiliary space."
        ),
    },
    {
        "pattern_name": "Binary Search on Answer / Search Space",
        "canonical_topic": "sorting_searching",
        "title": "Binary Search on Continuous & Monotonic Search Spaces",
        "text": (
            "Beyond searching for items in a sorted array, Binary Search applies whenever a decision function check(mid) "
            "is monotonic (e.g. FFFTTT or TTTFFF). We set search boundaries [low, high] over the possible answer range "
            "and compute mid = low + (high - low) // 2.\n\n"
            "Key Indicators:\n"
            "- Minimax problems ('Minimize the maximum', 'Maximize the minimum allocation').\n"
            "- Koko Eating Bananas, Capacity to Ship Packages Within D Days, Split Array Largest Sum, Aggressive Cows.\n\n"
            "Complexity: O(log(range) * cost_of_check)."
        ),
    },
    {
        "pattern_name": "Backtracking / Subsets & Permutations",
        "canonical_topic": "recursion",
        "title": "Backtracking Exploration Paradigm",
        "text": (
            "Backtracking incrementally builds candidates for solutions and abandons ('backtracks') as soon as it determines "
            "that the candidate cannot lead to a valid full solution.\n\n"
            "Template:\n"
            "def backtrack(path, choices):\n"
            "    if is_valid_solution(path): results.append(list(path)); return\n"
            "    for choice in choices:\n"
            "        if violates_constraints(choice): continue\n"
            "        make_choice(path, choice)\n"
            "        backtrack(path, updated_choices)\n"
            "        undo_choice(path, choice)  # backtrack state\n\n"
            "Applications: Subsets, Permutations, Combination Sum, N-Queens, Sudoku Solver."
        ),
    },
    {
        "pattern_name": "Dynamic Programming: 0/1 Knapsack",
        "canonical_topic": "dynamic_programming",
        "title": "0/1 Knapsack & Subset Sum Dynamic Programming Pattern",
        "text": (
            "In 0/1 Knapsack, items with weights and values must either be chosen or skipped to maximize value within "
            "capacity W. The recurrence: dp[i][w] = max(dp[i-1][w], val[i] + dp[i-1][w - wt[i]]).\n\n"
            "Space Optimization:\n"
            "We can compress the 2D DP table into a 1D array by iterating capacity backwards from W down to wt[i], "
            "preventing items from being used multiple times.\n\n"
            "Key Problems: Partition Equal Subset Sum, Target Sum, Subset Sum."
        ),
    },
    {
        "pattern_name": "Dynamic Programming: Longest Common Subsequence",
        "canonical_topic": "dynamic_programming",
        "title": "LCS & String Alignment DP Pattern",
        "text": (
            "LCS finds the longest subsequence present in both strings s1 and s2. "
            "If s1[i-1] == s2[j-1], dp[i][j] = 1 + dp[i-1][j-1]. "
            "Else, dp[i][j] = max(dp[i-1][j], dp[i][j-1]).\n\n"
            "Variants: Edit Distance, Distinct Subsequences, Shortest Common Supersequence.\n"
            "Complexity: O(M * N) time and space (compressible to O(min(M, N)) space)."
        ),
    },
    {
        "pattern_name": "Topological Sort (Kahn's & DFS)",
        "canonical_topic": "graphs",
        "title": "Topological Sort for Directed Acyclic Graphs (DAG)",
        "text": (
            "Topological ordering arranges DAG vertices linearly such that for every directed edge u -> v, u appears before v.\n\n"
            "Kahn's Algorithm (BFS):\n"
            "1. Calculate in-degree for all vertices.\n"
            "2. Push vertices with in-degree 0 to queue.\n"
            "3. While queue is not empty: pop u, append to result, decrement in-degrees of neighbors. "
            "If neighbor in-degree reaches 0, push to queue.\n"
            "4. If result length < V, graph has a cycle!\n\n"
            "Applications: Course Schedule I & II, Alien Dictionary, Build Systems."
        ),
    },
    {
        "pattern_name": "Two Heaps Pattern",
        "canonical_topic": "heaps",
        "title": "Two Heaps Pattern: Finding Running Median",
        "text": (
            "The Two Heaps pattern balances a Max-Heap for the smaller half of numbers and a Min-Heap for the larger half. "
            "The running median is either the top of the max heap (if odd count) or the average of both tops (if even count).\n\n"
            "Complexity:\n"
            "- Insertion: O(log N)\n"
            "- Find Median: O(1)\n"
            "Applications: Find Median from Data Stream, Sliding Window Median."
        ),
    },
    {
        "pattern_name": "Bitwise XOR Tricks",
        "canonical_topic": "bit_manipulation",
        "title": "Bitwise XOR Properties & Problem Solving",
        "text": (
            "XOR properties:\n"
            "- a ^ 0 = a\n"
            "- a ^ a = 0 (self-inverse)\n"
            "- Commutative and associative: a ^ b ^ a = b\n\n"
            "Crucial Tricks:\n"
            "1. Single Number: XOR all numbers; duplicates cancel out, leaving the unique element.\n"
            "2. Isolating rightmost set bit: bit = n & (-n)\n"
            "3. Clearing rightmost set bit: n = n & (n - 1) (Kernighan's bit count).\n"
            "Complexity: O(1) space, O(N) time."
        ),
    },
    {
        "pattern_name": "Disjoint Set Union (Union-Find)",
        "canonical_topic": "graphs",
        "title": "Disjoint Set Union with Path Compression & Union by Rank",
        "text": (
            "Union-Find keeps track of a set of elements partitioned into disjoint subsets.\n"
            "Optimizations:\n"
            "- Path Compression in find(x): Flattens the tree so subsequent lookups are O(1).\n"
            "- Union by Rank/Size: Attaches smaller tree under root of larger tree.\n\n"
            "Complexity: Nearly linear O(alpha(N)) amortized time per operation, where alpha is inverse Ackermann.\n"
            "Applications: Kruskal's MST, Number of Provinces, Redundant Connection."
        ),
    },
    {
        "pattern_name": "Trie (Prefix Tree)",
        "canonical_topic": "tries",
        "title": "Trie Data Structure & Prefix Matching",
        "text": (
            "A Trie stores strings character by character in a tree structure. Each node has children pointers (usually array "
            "of size 26 or hash map) and a boolean flag is_end_of_word.\n\n"
            "Operations:\n"
            "- Insert word: O(L) time where L is word length.\n"
            "- Search word: O(L) time.\n"
            "- StartsWith prefix: O(L) time.\n"
            "Applications: Autocomplete, Spell Check, Maximum XOR Pair (Binary Trie)."
        ),
    },
    {
        "pattern_name": "Segment Tree / Fenwick Tree",
        "canonical_topic": "segment_tree",
        "title": "Segment Tree & Fenwick Tree for Range Queries",
        "text": (
            "Segment Tree and Binary Indexed Tree (Fenwick) support logarithmic updates and range queries (sum, min, max, gcd).\n\n"
            "Segment Tree:\n"
            "- Build: O(N)\n"
            "- Point/Range Update: O(log N) (with Lazy Propagation for range updates)\n"
            "- Range Query: O(log N)\n"
            "Applications: Dynamic Range Sum, Range Minimum Query, Count Inversions."
        ),
    },
]

# Curated Fallback Templates for Must-Read LeetCode Articles
MUST_READ_FALLBACK_TEMPLATES = [
    {
        "title": "Sliding Window Maximum & Frequency Template",
        "canonical_topic": "sliding_window",
        "pattern_name": "Sliding Window",
        "url": "https://leetcode.com/problems/frequency-of-the-most-frequent-element/solutions/1175088/C++-Maximum-Sliding-Window-Cheatsheet-Template/",
        "text": (
            "// Standard Sliding Window C++ Template (Expand Right, Contract Left)\n"
            "template <typename T>\n"
            "int slidingWindowTemplate(const vector<T>& nums, int k) {\n"
            "    int left = 0, maxLen = 0;\n"
            "    unordered_map<T, int> freq;\n"
            "    for (int right = 0; right < nums.size(); ++right) {\n"
            "        // 1. Add nums[right] to window state\n"
            "        freq[nums[right]]++;\n"
            "        // 2. Shrink window until condition is met\n"
            "        while (/* window condition invalid */ false) {\n"
            "            freq[nums[left]]--;\n"
            "            left++;\n"
            "        }\n"
            "        // 3. Update result with valid window\n"
            "        maxLen = max(maxLen, right - left + 1);\n"
            "    }\n"
            "    return maxLen;\n"
            "}\n"
        ),
    },
    {
        "title": "10-Line Substring Problem Template",
        "canonical_topic": "sliding_window",
        "pattern_name": "Sliding Window",
        "url": "https://leetcode.com/problems/minimum-window-substring/solutions/26808/Here-is-a-10-line-template-that-can-solve-most-'substring'-problems/",
        "text": (
            "// Universal 10-line Substring Template for LeetCode\n"
            "int findSubstring(string s, string t) {\n"
            "    vector<int> map(128, 0);\n"
            "    for (char c : t) map[c]++;\n"
            "    int counter = t.size(), begin = 0, end = 0, d = INT_MAX, head = 0;\n"
            "    while (end < s.size()) {\n"
            "        if (map[s[end++]]-- > 0) counter--; // in t\n"
            "        while (counter == 0) { // valid window\n"
            "            if (end - begin < d) d = end - (head = begin);\n"
            "            if (map[s[begin++]]++ == 0) counter++; // make it invalid again\n"
            "        }\n"
            "    }\n"
            "    return d == INT_MAX ? 0 : d;\n"
            "}\n"
        ),
    },
    {
        "title": "Ultimate Binary Search Template (Boundary Invariants)",
        "canonical_topic": "sorting_searching",
        "pattern_name": "Binary Search",
        "url": "https://leetcode.com/discuss/study-guide/786126/Python-Powerful-Ultimate-Binary-Search-Template.-Solved-many-problems",
        "text": (
            "# Powerful General Binary Search Template in Python\n"
            "def binary_search_template(array, condition_fn) -> int:\n"
            "    left, right = 0, len(array) - 1\n"
            "    ans = -1\n"
            "    while left <= right:\n"
            "        mid = left + (right - left) // 2\n"
            "        if condition_fn(mid):\n"
            "            ans = mid\n"
            "            right = mid - 1  # Look for smaller valid index in left half\n"
            "        else:\n"
            "            left = mid + 1   # Condition not met, search right half\n"
            "    return ans\n"
        ),
    },
    {
        "title": "General Backtracking Template (Permutations, Subsets, Combination Sum)",
        "canonical_topic": "recursion",
        "pattern_name": "Backtracking",
        "url": "https://leetcode.com/problems/permutations/solutions/18239/A-general-approach-to-backtracking-questions-in-Java-(Subsets-Permutations-Combination-Sum-Palindrome-Partioning)/",
        "text": (
            "// Standard Java Backtracking Template\n"
            "public void backtrack(List<List<Integer>> list, List<Integer> tempList, int[] nums, int start) {\n"
            "    list.add(new ArrayList<>(tempList));\n"
            "    for (int i = start; i < nums.length; i++) {\n"
            "        tempList.add(nums[i]);\n"
            "        backtrack(list, tempList, nums, i + 1);\n"
            "        tempList.remove(tempList.size() - 1);\n"
            "    }\n"
            "}\n"
        ),
    },
    {
        "title": "Monotonic Stack Guide & Template",
        "canonical_topic": "stacks_queues",
        "pattern_name": "Monotonic Stack",
        "url": "https://leetcode.com/discuss/study-guide/2347639/A-comprehensive-guide-and-template-for-monotonic-stack-based-problems",
        "text": (
            "// Next Greater Element Monotonic Decreasing Stack Template\n"
            "vector<int> nextGreaterElements(vector<int>& nums) {\n"
            "    int n = nums.size();\n"
            "    vector<int> nge(n, -1);\n"
            "    stack<int> st; // stores indices\n"
            "    for (int i = 0; i < n; ++i) {\n"
            "        while (!st.empty() && nums[i] > nums[st.top()]) {\n"
            "            nge[st.top()] = nums[i];\n"
            "            st.pop();\n"
            "        }\n"
            "        st.push(i);\n"
            "    }\n"
            "    return nge;\n"
            "}\n"
        ),
    },
    {
        "title": "Stock Series Patterns: State Machine Dynamic Programming",
        "canonical_topic": "dynamic_programming",
        "pattern_name": "Dynamic Programming",
        "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock-with-transaction-fee/solutions/108870/most-consistent-ways-of-dealing-with-the-series-of-stock-problems/",
        "text": (
            "// Consistent State-Machine DP for All Best Time to Buy and Sell Stock Problems\n"
            "// T[i][k][0] = max profit on day i with at most k transactions and 0 stock in hand\n"
            "// T[i][k][1] = max profit on day i with at most k transactions and 1 stock in hand\n"
            "int maxProfit(vector<int>& prices, int fee) {\n"
            "    int hold = -prices[0];\n"
            "    int not_hold = 0;\n"
            "    for (int i = 1; i < prices.size(); ++i) {\n"
            "        not_hold = max(not_hold, hold + prices[i] - fee);\n"
            "        hold = max(hold, not_hold - prices[i]);\n"
            "    }\n"
            "    return not_hold;\n"
            "}\n"
        ),
    },
]


def _try_fetch_article_text(url: str, timeout: float = 3.0) -> Optional[str]:
    """Lightweight scraper with quick timeout; returns None if blocked or offline."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            # Extract plain text or code tags
            code_blocks = re.findall(r"<code[^>]*>(.*?)</code>", content, re.DOTALL)
            if code_blocks:
                joined = "\n\n".join(re.sub(r"<[^>]+>", "", cb).strip() for cb in code_blocks if len(cb) > 40)
                if len(joined) > 100:
                    return joined[:4000]
    except Exception as exc:
        logger.debug("Live fetch failed for %s (%s). Using fallback.", url, exc)
    return None


def parse_patterns_repo(repo_dir: Path | str) -> list[PatternChunk]:
    """
    Parses code implementations, prose pattern explanations, and article templates
    from the ashishps1/awesome-leetcode-resources repository.
    """
    base_dir = Path(repo_dir)
    chunks: list[PatternChunk] = []

    # 1. Parse code files from patterns/ (C++, Python, Java)
    patterns_dir = base_dir / "patterns"
    if patterns_dir.exists():
        # Priority mapping: cpp -> 'cpp', python -> 'python', java -> 'java'
        lang_dirs = [
            ("c++", "cpp"),
            ("python", "python"),
            ("java", "java"),
        ]

        for folder_name, lang_code in lang_dirs:
            lang_path = patterns_dir / folder_name
            if not lang_path.exists():
                continue

            for file_path in sorted(lang_path.glob("*.*")):
                if file_path.name.startswith("."):
                    continue

                raw_code = file_path.read_text(encoding="utf-8", errors="ignore").strip()
                if not raw_code:
                    continue

                stem = file_path.stem.lower()
                clean_name = re.sub(r"([A-Z])", r" \1", file_path.stem).strip()
                canonical = TOPIC_MAPPING.get(stem, stem)

                cid = f"alr_code_{lang_code}_{file_path.stem.lower()}"
                chunks.append(
                    PatternChunk(
                        chunk_id=cid,
                        source="awesome-leetcode-resources",
                        content_type="pattern_code",
                        pattern_name=clean_name,
                        language=lang_code,
                        canonical_topic=canonical,
                        title=f"{clean_name} Implementation ({lang_code.upper()})",
                        text=raw_code,
                        url=f"https://github.com/ashishps1/awesome-leetcode-resources/blob/main/patterns/{folder_name}/{file_path.name}",
                    )
                )

    # 2. Extract 20+ Canonical Prose Explanations
    for idx, p in enumerate(CORE_PATTERN_EXPLANATIONS, start=1):
        cid = f"alr_expl_{p['canonical_topic']}_{idx}"
        chunks.append(
            PatternChunk(
                chunk_id=cid,
                source="awesome-leetcode-resources",
                content_type="pattern_explanation",
                pattern_name=p["pattern_name"],
                language="general",
                canonical_topic=p["canonical_topic"],
                title=p["title"],
                text=p["text"],
                url="https://github.com/ashishps1/awesome-leetcode-resources#--patterns",
            )
        )

    # 3. Extract Must-Read LeetCode Articles with Fallback Template Text
    for idx, art in enumerate(MUST_READ_FALLBACK_TEMPLATES, start=1):
        url = art["url"]
        live_text = _try_fetch_article_text(url)
        content_text = live_text if live_text else art["text"]

        cid = f"alr_article_{art['canonical_topic']}_{idx}"
        chunks.append(
            PatternChunk(
                chunk_id=cid,
                source="awesome-leetcode-resources",
                content_type="article_template",
                pattern_name=art["pattern_name"],
                language="cpp" if "C++" in art["text"] or "#include" in art["text"] else ("python" if "def " in art["text"] else "general"),
                canonical_topic=art["canonical_topic"],
                title=art["title"],
                text=content_text,
                url=url,
            )
        )

    return chunks


def build_and_save_patterns_corpus(
    repo_dir: Path | str,
    output_path: Path | str,
) -> list[PatternChunk]:
    """Parses patterns corpus and writes JSON file."""
    chunks = parse_patterns_repo(repo_dir)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([c.model_dump() for c in chunks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved %d pattern chunks to %s", len(chunks), out)
    return chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_ingestion.fetcher import ensure_external_repos
    paths = ensure_external_repos()
    chunks = build_and_save_patterns_corpus(
        paths["awesome-leetcode-resources"],
        Path(__file__).resolve().parent.parent / "data" / "patterns_corpus.json",
    )
    print(f"Generated {len(chunks)} pattern chunks.")
