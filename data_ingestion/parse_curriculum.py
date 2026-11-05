"""
Deterministic parser for Prince-1501/Complete-DSA-Preparation.
Builds the sequential curriculum and prerequisite DAG with curated LeetCode / GeeksforGeeks
practice problems mapped to canonical topics.
DOES NOT embed raw problem tables into the vector store.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from data_ingestion.schemas import CurriculumGraph, CurriculumTopic, PracticeProblem

logger = logging.getLogger(__name__)

# Complete Sequential Curriculum Order & Prerequisite DAG Definition
CURRICULUM_DAG = [
    {
        "canonical_topic": "math",
        "display_name": "Mathematics & Number Theory",
        "module_order": 1,
        "prerequisites": [],
        "next_topics": ["bit_manipulation", "arrays"],
        "readme_sections": ["Mathematics"],
    },
    {
        "canonical_topic": "bit_manipulation",
        "display_name": "Bit Manipulation",
        "module_order": 2,
        "prerequisites": ["math"],
        "next_topics": ["arrays"],
        "readme_sections": ["Bits Manipulation"],
    },
    {
        "canonical_topic": "arrays",
        "display_name": "Arrays & Hashing Foundations",
        "module_order": 3,
        "prerequisites": ["math"],
        "next_topics": ["two_pointers", "sliding_window", "sorting_searching"],
        "readme_sections": ["Arrays", "Matrix"],
    },
    {
        "canonical_topic": "two_pointers",
        "display_name": "Two Pointers Technique",
        "module_order": 4,
        "prerequisites": ["arrays"],
        "next_topics": ["sliding_window", "linked_list"],
        "readme_sections": ["Searching"],
    },
    {
        "canonical_topic": "sliding_window",
        "display_name": "Sliding Window Pattern",
        "module_order": 5,
        "prerequisites": ["arrays", "two_pointers"],
        "next_topics": ["hashing"],
        "readme_sections": ["String"],
    },
    {
        "canonical_topic": "sorting_searching",
        "display_name": "Sorting & Binary Search",
        "module_order": 6,
        "prerequisites": ["arrays"],
        "next_topics": ["hashing", "linked_list"],
        "readme_sections": ["Sorting", "Searching"],
    },
    {
        "canonical_topic": "hashing",
        "display_name": "Hashing & Hash Tables",
        "module_order": 7,
        "prerequisites": ["arrays"],
        "next_topics": ["linked_list", "stacks_queues"],
        "readme_sections": ["Hashing"],
    },
    {
        "canonical_topic": "linked_list",
        "display_name": "Linked Lists",
        "module_order": 8,
        "prerequisites": ["arrays", "two_pointers"],
        "next_topics": ["stacks_queues", "trees"],
        "readme_sections": ["Linked List"],
    },
    {
        "canonical_topic": "stacks_queues",
        "display_name": "Stacks & Queues",
        "module_order": 9,
        "prerequisites": ["linked_list"],
        "next_topics": ["trees", "graphs"],
        "readme_sections": ["Stack", "Queue"],
    },
    {
        "canonical_topic": "recursion",
        "display_name": "Recursion & Backtracking",
        "module_order": 10,
        "prerequisites": ["math", "stacks_queues"],
        "next_topics": ["trees", "dynamic_programming"],
        "readme_sections": ["Recursion", "Backtracking"],
    },
    {
        "canonical_topic": "trees",
        "display_name": "Binary Trees & BST",
        "module_order": 11,
        "prerequisites": ["recursion", "stacks_queues"],
        "next_topics": ["heaps", "graphs", "tries"],
        "readme_sections": ["Tree", "Binary Search Tree"],
    },
    {
        "canonical_topic": "heaps",
        "display_name": "Heaps & Priority Queues",
        "module_order": 12,
        "prerequisites": ["arrays", "trees"],
        "next_topics": ["graphs", "greedy"],
        "readme_sections": ["Heap"],
    },
    {
        "canonical_topic": "greedy",
        "display_name": "Greedy Algorithms",
        "module_order": 13,
        "prerequisites": ["sorting_searching", "heaps"],
        "next_topics": ["graphs", "dynamic_programming"],
        "readme_sections": ["Greedy"],
    },
    {
        "canonical_topic": "graphs",
        "display_name": "Graph Algorithms & BFS/DFS",
        "module_order": 14,
        "prerequisites": ["trees", "stacks_queues", "heaps"],
        "next_topics": ["dynamic_programming"],
        "readme_sections": ["Graph"],
    },
    {
        "canonical_topic": "dynamic_programming",
        "display_name": "Dynamic Programming",
        "module_order": 15,
        "prerequisites": ["recursion", "arrays"],
        "next_topics": ["segment_tree"],
        "readme_sections": ["Dynamic Programming"],
    },
    {
        "canonical_topic": "tries",
        "display_name": "Tries (Prefix Trees)",
        "module_order": 16,
        "prerequisites": ["trees", "hashing"],
        "next_topics": ["segment_tree"],
        "readme_sections": ["Trie"],
    },
    {
        "canonical_topic": "segment_tree",
        "display_name": "Segment Trees & Fenwick Trees",
        "module_order": 17,
        "prerequisites": ["trees", "arrays"],
        "next_topics": [],
        "readme_sections": [],
    },
]

# High-Yield Practice Problems for Topics with sparse tables in upstream repo
SUPPLEMENTAL_PRACTICE_PROBLEMS: Dict[str, List[PracticeProblem]] = {
    "arrays": [
        PracticeProblem(
            title="Two Sum",
            platform="LeetCode",
            url="https://leetcode.com/problems/two-sum/",
            difficulty="Easy",
            tag="Arrays, Hash Table",
        ),
        PracticeProblem(
            title="Best Time to Buy and Sell Stock",
            platform="LeetCode",
            url="https://leetcode.com/problems/best-time-to-buy-and-sell-stock/",
            difficulty="Easy",
            tag="Arrays, Dynamic Programming",
        ),
        PracticeProblem(
            title="Maximum Subarray (Kadane's Algorithm)",
            platform="LeetCode",
            url="https://leetcode.com/problems/maximum-subarray/",
            difficulty="Medium",
            tag="Arrays, Divide and Conquer",
        ),
    ],
    "two_pointers": [
        PracticeProblem(
            title="Two Sum II - Input Array Is Sorted",
            platform="LeetCode",
            url="https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/",
            difficulty="Medium",
            tag="Two Pointers, Binary Search",
        ),
        PracticeProblem(
            title="3Sum",
            platform="LeetCode",
            url="https://leetcode.com/problems/3sum/",
            difficulty="Medium",
            tag="Two Pointers, Sorting",
        ),
        PracticeProblem(
            title="Container With Most Water",
            platform="LeetCode",
            url="https://leetcode.com/problems/container-with-most-water/",
            difficulty="Medium",
            tag="Two Pointers, Greedy",
        ),
    ],
    "linked_list": [
        PracticeProblem(
            title="Reverse Linked List",
            platform="LeetCode",
            url="https://leetcode.com/problems/reverse-linked-list/",
            difficulty="Easy",
            tag="Linked List, Recursion",
        ),
        PracticeProblem(
            title="Linked List Cycle (Floyd's Algorithm)",
            platform="LeetCode",
            url="https://leetcode.com/problems/linked-list-cycle/",
            difficulty="Easy",
            tag="Linked List, Two Pointers",
        ),
        PracticeProblem(
            title="Middle of the Linked List",
            platform="LeetCode",
            url="https://leetcode.com/problems/middle-of-the-linked-list/",
            difficulty="Easy",
            tag="Linked List, Two Pointers",
        ),
        PracticeProblem(
            title="Merge Two Sorted Lists",
            platform="LeetCode",
            url="https://leetcode.com/problems/merge-two-sorted-lists/",
            difficulty="Easy",
            tag="Linked List, Recursion",
        ),
    ],
    "sliding_window": [
        PracticeProblem(
            title="Longest Substring Without Repeating Characters",
            platform="LeetCode",
            url="https://leetcode.com/problems/longest-substring-without-repeating-characters/",
            difficulty="Medium",
            tag="Sliding Window, Hash Table",
        ),
        PracticeProblem(
            title="Minimum Window Substring",
            platform="LeetCode",
            url="https://leetcode.com/problems/minimum-window-substring/",
            difficulty="Hard",
            tag="Sliding Window, Hash Table",
        ),
        PracticeProblem(
            title="Max Consecutive Ones III",
            platform="LeetCode",
            url="https://leetcode.com/problems/max-consecutive-ones-iii/",
            difficulty="Medium",
            tag="Sliding Window, Prefix Sum",
        ),
    ],
    "sorting_searching": [
        PracticeProblem(
            title="Binary Search",
            platform="LeetCode",
            url="https://leetcode.com/problems/binary-search/",
            difficulty="Easy",
            tag="Binary Search",
        ),
        PracticeProblem(
            title="Search in Rotated Sorted Array",
            platform="LeetCode",
            url="https://leetcode.com/problems/search-in-rotated-sorted-array/",
            difficulty="Medium",
            tag="Binary Search",
        ),
        PracticeProblem(
            title="Koko Eating Bananas",
            platform="LeetCode",
            url="https://leetcode.com/problems/koko-eating-bananas/",
            difficulty="Medium",
            tag="Binary Search on Answer",
        ),
    ],
    "dynamic_programming": [
        PracticeProblem(
            title="Climbing Stairs",
            platform="LeetCode",
            url="https://leetcode.com/problems/climbing-stairs/",
            difficulty="Easy",
            tag="Dynamic Programming",
        ),
        PracticeProblem(
            title="Coin Change",
            platform="LeetCode",
            url="https://leetcode.com/problems/coin-change/",
            difficulty="Medium",
            tag="Dynamic Programming, Knapsack",
        ),
        PracticeProblem(
            title="Longest Common Subsequence",
            platform="LeetCode",
            url="https://leetcode.com/problems/longest-common-subsequence/",
            difficulty="Medium",
            tag="Dynamic Programming, Strings",
        ),
    ],
    "greedy": [
        PracticeProblem(
            title="Jump Game",
            platform="LeetCode",
            url="https://leetcode.com/problems/jump-game/",
            difficulty="Medium",
            tag="Greedy, Dynamic Programming",
        ),
        PracticeProblem(
            title="Gas Station",
            platform="LeetCode",
            url="https://leetcode.com/problems/gas-station/",
            difficulty="Medium",
            tag="Greedy",
        ),
        PracticeProblem(
            title="Task Scheduler",
            platform="LeetCode",
            url="https://leetcode.com/problems/task-scheduler/",
            difficulty="Medium",
            tag="Greedy, Heap",
        ),
    ],
    "backtracking": [
        PracticeProblem(
            title="Subsets",
            platform="LeetCode",
            url="https://leetcode.com/problems/subsets/",
            difficulty="Medium",
            tag="Backtracking, Bit Manipulation",
        ),
        PracticeProblem(
            title="Permutations",
            platform="LeetCode",
            url="https://leetcode.com/problems/permutations/",
            difficulty="Medium",
            tag="Backtracking",
        ),
        PracticeProblem(
            title="N-Queens",
            platform="LeetCode",
            url="https://leetcode.com/problems/n-queens/",
            difficulty="Hard",
            tag="Backtracking",
        ),
    ],
    "tries": [
        PracticeProblem(
            title="Implement Trie (Prefix Tree)",
            platform="LeetCode",
            url="https://leetcode.com/problems/implement-trie-prefix-tree/",
            difficulty="Medium",
            tag="Trie, Design",
        ),
        PracticeProblem(
            title="Design Add and Search Words Data Structure",
            platform="LeetCode",
            url="https://leetcode.com/problems/design-add-and-search-words-data-structure/",
            difficulty="Medium",
            tag="Trie, Backtracking",
        ),
        PracticeProblem(
            title="Maximum XOR of Two Numbers in an Array",
            platform="LeetCode",
            url="https://leetcode.com/problems/maximum-xor-of-two-numbers-in-an-array/",
            difficulty="Medium",
            tag="Trie, Bit Manipulation",
        ),
    ],
    "segment_tree": [
        PracticeProblem(
            title="Range Sum Query - Mutable",
            platform="LeetCode",
            url="https://leetcode.com/problems/range-sum-query-mutable/",
            difficulty="Medium",
            tag="Segment Tree, Binary Indexed Tree",
        ),
        PracticeProblem(
            title="Count of Smaller Numbers After Self",
            platform="LeetCode",
            url="https://leetcode.com/problems/count-of-smaller-numbers-after-self/",
            difficulty="Hard",
            tag="Segment Tree, Binary Indexed Tree",
        ),
    ],
}


def _parse_problems_from_section(section_text: str) -> List[PracticeProblem]:
    """Parses markdown table rows for problem titles and links."""
    problems: List[PracticeProblem] = []
    lines = section_text.strip().splitlines()

    for line in lines:
        if not line.strip().startswith("|") or line.strip().startswith("|--") or "#" in line:
            continue

        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 3:
            continue

        # Check for [Title](URL) in Question / Title column
        title_col = cols[2] if len(cols) > 2 else ""
        link_match = re.search(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", title_col)

        # Or document column
        doc_col = cols[4] if len(cols) > 4 else ""
        if not link_match and doc_col:
            link_match = re.search(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", doc_col)

        if link_match:
            title = re.sub(r"[*_`]", "", link_match.group(1)).strip()
            url = link_match.group(2).strip()

            diff = "Medium"
            for c in cols:
                if "Easy" in c:
                    diff = "Easy"
                elif "Hard" in c:
                    diff = "Hard"

            platform = "LeetCode" if "leetcode.com" in url else ("GeeksforGeeks" if "geeksforgeeks.org" in url else "External")
            tag_col = cols[-2] if len(cols) > 6 else ""

            if url and title:
                problems.append(
                    PracticeProblem(
                        title=title,
                        platform=platform,
                        url=url,
                        difficulty=diff,
                        tag=tag_col,
                    )
                )

    return problems


def parse_curriculum_graph(readme_path: Path | str) -> CurriculumGraph:
    """
    Parses Complete-DSA-Preparation README into structured CurriculumGraph.
    """
    path = Path(readme_path)
    if not path.exists():
        raise FileNotFoundError(f"Curriculum README not found at {path}")

    content = path.read_text(encoding="utf-8", errors="ignore")

    topics_dict: Dict[str, CurriculumTopic] = {}

    for node in CURRICULUM_DAG:
        canonical_tag = node["canonical_topic"]
        display_name = node["display_name"]
        order = node["module_order"]
        prereqs = node["prerequisites"]
        next_top = node["next_topics"]

        problems: List[PracticeProblem] = []

        # 1. Parse problems from matching README sections
        for sec_name in node.get("readme_sections", []):
            pattern = rf"##\s+{re.escape(sec_name)}\s*\n(.*?)(?=\n## |\Z)"
            sec_match = re.search(pattern, content, re.DOTALL)
            if sec_match:
                parsed = _parse_problems_from_section(sec_match.group(1))
                problems.extend(parsed)

        # 2. If problem list is sparse, append curated high-yield practice problems
        if canonical_tag in SUPPLEMENTAL_PRACTICE_PROBLEMS:
            for p in SUPPLEMENTAL_PRACTICE_PROBLEMS[canonical_tag]:
                if not any(existing.url == p.url for existing in problems):
                    problems.append(p)

        # Deduplicate problems by URL
        seen_urls = set()
        deduped_problems = []
        for p in problems:
            if p.url not in seen_urls:
                seen_urls.add(p.url)
                deduped_problems.append(p)

        topics_dict[canonical_tag] = CurriculumTopic(
            canonical_topic=canonical_tag,
            display_name=display_name,
            module_order=order,
            prerequisites=prereqs,
            next_topics=next_top,
            practice_problems=deduped_problems,
        )

    return CurriculumGraph(topics=topics_dict)


def build_and_save_curriculum_graph(
    readme_path: Path | str,
    output_path: Path | str,
) -> Dict[str, dict]:
    """Parses curriculum graph and writes curriculum_graph.json."""
    graph = parse_curriculum_graph(readme_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    serialized = {k: v.model_dump() for k, v in graph.topics.items()}
    out.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved curriculum graph with %d modules to %s", len(graph.topics), out)
    return serialized


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_ingestion.fetcher import ensure_external_repos
    paths = ensure_external_repos()
    data = build_and_save_curriculum_graph(
        paths["Complete-DSA-Preparation"] / "README.md",
        Path(__file__).resolve().parent.parent / "data" / "curriculum_graph.json",
    )
    print(f"Generated curriculum graph with {len(data)} nodes.")
    for k, v in list(data.items())[:3]:
        print(f"- {k} (Order {v['module_order']}): {len(v['practice_problems'])} problems, prereqs: {v['prerequisites']}")
