"""
Fast Canonical DSA Topic Classifier.
Maps user queries to 1-2 canonical topic tags using keyword matching,
pedagogical aliases, and token overlap.
"""

from __future__ import annotations

import re
from typing import List, Tuple

CANONICAL_TOPICS = [
    "arrays",
    "two_pointers",
    "sliding_window",
    "linked_list",
    "stacks_queues",
    "trees",
    "heaps",
    "graphs",
    "dynamic_programming",
    "recursion",
    "bit_manipulation",
    "tries",
    "segment_tree",
    "sorting_searching",
    "greedy",
    "hashing",
    "math",
]

TOPIC_PATTERNS = {
    "sliding_window": [
        r"\bsliding\s*window\b",
        r"\bmax(?:imum)?\s*subarray\s*of\s*size\b",
        r"\blongest\s*substring\b",
        r"\bminimum\s*window\b",
        r"\bwindow\b",
    ],
    "two_pointers": [
        r"\btwo\s*pointers?\b",
        r"\b2\s*pointers?\b",
        r"\bfast\s*and\s*slow\b",
        r"\bfloyd'?s?\b",
        r"\bconverging\s*pointers?\b",
        r"\b3\s*sum\b",
        r"\bthree\s*sum\b",
        r"\b2\s*sum\s*ii\b",
        r"\bcontainer\s*with\s*most\s*water\b",
    ],
    "linked_list": [
        r"\blinked\s*list\b",
        r"\bsingly\s*linked\b",
        r"\bdoubly\s*linked\b",
        r"\bdetect\s*loop\b",
        r"\bdetect\s*cycle\b",
        r"\breverse\s*(?:a\s*)?list\b",
        r"\bmiddle\s*of\s*(?:the\s*)?linked\s*list\b",
        r"\bnode->next\b",
        r"\bhead\s*pointer\b",
    ],
    "dynamic_programming": [
        r"\bdynamic\s*programming\b",
        r"\bdp\b",
        r"\bmemoiz(?:ation|e)\b",
        r"\btabulation\b",
        r"\bknapsack\b",
        r"\blcs\b",
        r"\blis\b",
        r"\blongest\s*common\s*subsequence\b",
        r"\blongest\s*increasing\s*subsequence\b",
        r"\bcoin\s*change\b",
        r"\bedit\s*distance\b",
        r"\boptimal\s*substructure\b",
        r"\boverlapping\s*subproblems\b",
    ],
    "stacks_queues": [
        r"\bmonotonic\s*stack\b",
        r"\bnext\s*greater\s*element\b",
        r"\bnext\s*smaller\s*element\b",
        r"\bstack\b",
        r"\bqueue\b",
        r"\blargest\s*rectangle\s*in\s*histogram\b",
        r"\btrapping\s*rain\s*water\b",
        r"\bparenthes(?:is|es)\b",
        r"\bvalid\s*parentheses\b",
    ],
    "trees": [
        r"\bbinary\s*tree\b",
        r"\bbst\b",
        r"\bbinary\s*search\s*tree\b",
        r"\blevel\s*order\b",
        r"\binorder\b",
        r"\bpreorder\b",
        r"\bpostorder\b",
        r"\bheight\s*of\s*tree\b",
        r"\blca\b",
        r"\blowest\s*common\s*ancestor\b",
        r"\btree\b",
    ],
    "heaps": [
        r"\bmin[- ]?heap\b",
        r"\bmax[- ]?heap\b",
        r"\bpriority\s*queue\b",
        r"\btop\s*k\b",
        r"\bkth\s*largest\b",
        r"\bkth\s*smallest\b",
        r"\bmedian\s*from\s*data\s*stream\b",
        r"\bheap\b",
    ],
    "graphs": [
        r"\bgraph\b",
        r"\bbfs\b",
        r"\bdfs\b",
        r"\bdijkstra\b",
        r"\btopological\s*sort\b",
        r"\bkahn'?s?\b",
        r"\bcycle\s*detection\s*in\s*graph\b",
        r"\bconnected\s*components\b",
        r"\bshortest\s*path\b",
        r"\bbipartite\b",
        r"\bdisjoint\s*set\b",
        r"\bdsu\b",
        r"\bunion[- ]?find\b",
        r"\bmst\b",
        r"\bkruskal\b",
        r"\bprim'?s?\b",
    ],
    "recursion": [
        r"\brecursion\b",
        r"\brecursive\b",
        r"\bbacktrack(?:ing)?\b",
        r"\bsubsets\b",
        r"\bpermutations\b",
        r"\bcombination\s*sum\b",
        r"\bn-?queens\b",
        r"\bsudoku\b",
    ],
    "bit_manipulation": [
        r"\bbit\s*manipulation\b",
        r"\bbitwise\b",
        r"\bxor\b",
        r"\bset\s*bit\b",
        r"\bcount\s*bits\b",
        r"\bsingle\s*number\b",
        r"\bpower\s*of\s*two\b",
    ],
    "tries": [
        r"\btrie\b",
        r"\bprefix\s*tree\b",
        r"\bautocomplete\b",
        r"\bwords?\s*dictionary\b",
    ],
    "segment_tree": [
        r"\bsegment\s*tree\b",
        r"\bfenwick\b",
        r"\bbinary\s*indexed\s*tree\b",
        r"\brange\s*query\b",
        r"\blazy\s*propagation\b",
    ],
    "sorting_searching": [
        r"\bbinary\s*search\b",
        r"\bsearch\s*in\s*rotated\b",
        r"\bsearch\s*space\b",
        r"\bmonotonic\s*search\b",
        r"\bmerge\s*sort\b",
        r"\bquick\s*sort\b",
        r"\bboundary\s*check\b",
    ],
    "greedy": [
        r"\bgreedy\b",
        r"\binterval\s*scheduling\b",
        r"\bactivity\s*selection\b",
        r"\bjump\s*game\b",
        r"\bgas\s*station\b",
    ],
    "hashing": [
        r"\bhash\s*table\b",
        r"\bhash\s*map\b",
        r"\bfrequency\s*map\b",
        r"\bunordered_map\b",
        r"\bhashing\b",
    ],
    "math": [
        r"\bmath\b",
        r"\bprime\b",
        r"\bsieve\b",
        r"\bgcd\b",
        r"\bmodulo\b",
        r"\bfactorial\b",
    ],
    "arrays": [
        r"\barray\b",
        r"\bmatrices\b",
        r"\bmatrix\b",
        r"\bkadane\b",
        r"\bprefix\s*sum\b",
        r"\b2\s*sum\b",
        r"\btwo\s*sum\b",
        r"\bpascal\b",
        r"\brotate\s*array\b",
    ],
}


def classify_canonical_topics(query: str, max_topics: int = 2, fallback_default: bool = False) -> List[str]:
    """
    Classifies an input user query into 1-2 canonical DSA topic tags.

    Parameters
    ----------
    query : str
        The user query / doubt.
    max_topics : int
        Maximum number of canonical topics to return.
    fallback_default : bool
        If True, returns ['arrays'] when no topics match. Defaults to False.

    Returns
    -------
    List[str]
        List of matching canonical topics sorted by match confidence.
    """
    q_lower = query.lower().strip()
    if not q_lower:
        return ["arrays"] if fallback_default else []

    scored_topics: list[Tuple[str, int]] = []

    for topic, patterns in TOPIC_PATTERNS.items():
        score = 0
        for pat in patterns:
            matches = re.findall(pat, q_lower)
            if matches:
                # Give higher weight to multi-word or highly specific pattern matches
                score += len(matches) * (3 if " " in pat else 2)

        if score > 0:
            scored_topics.append((topic, score))

    if not scored_topics:
        # Fallback keyword match
        tokens = set(re.findall(r"\b\w+\b", q_lower))
        for topic in CANONICAL_TOPICS:
            if topic in tokens:
                scored_topics.append((topic, 1))

    if not scored_topics:
        return ["arrays"] if fallback_default else []

    scored_topics.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored_topics[:max_topics]]


if __name__ == "__main__":
    queries = [
        "Explain the sliding window pattern in C++ and give me practice problems",
        "How do I detect a loop in a linked list using slow and fast pointers?",
        "What is Kadane's algorithm for maximum subarray?",
        "Can you explain 0/1 knapsack dynamic programming?",
        "How does Dijkstra's algorithm work on graphs?",
    ]
    for q in queries:
        topics = classify_canonical_topics(q)
        print(f"'{q}' -> {topics}")
