"""
Deterministic Markdown parser for avinash201199/DSA-KIT.
Extracts topic learning links, visualizers, and cheat sheets,
normalizing them into structured TopicResource objects.
DOES NOT embed into the vector store.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

from data_ingestion.schemas import ResourceLink, TopicResource

logger = logging.getLogger(__name__)

# Canonical Tag Normalization Map
CANONICAL_TOPIC_MAP = {
    "arrays & strings": ["arrays", "sliding_window", "two_pointers"],
    "arrays": ["arrays"],
    "strings": ["arrays"],
    "sliding window": ["sliding_window"],
    "two pointers": ["two_pointers"],
    "linked lists": ["linked_list"],
    "linked list": ["linked_list"],
    "stacks & queues": ["stacks_queues"],
    "stacks and queues": ["stacks_queues"],
    "trees & graphs": ["trees", "graphs"],
    "trees": ["trees"],
    "graphs": ["graphs"],
    "binary search tree": ["trees"],
    "dynamic programming": ["dynamic_programming"],
    "dp": ["dynamic_programming"],
    "recursion & backtracking": ["recursion"],
    "recursion": ["recursion"],
    "sorting & searching": ["sorting_searching"],
    "sorting": ["sorting_searching"],
    "binary search": ["sorting_searching"],
    "heaps & priority queues": ["heaps"],
    "heaps": ["heaps"],
    "hashing": ["hashing"],
    "greedy algorithms": ["greedy"],
    "greedy": ["greedy"],
    "bit manipulation": ["bit_manipulation"],
    "math & number theory": ["math"],
    "math": ["math"],
    "segment trees & fenwick trees": ["segment_tree"],
    "segment trees": ["segment_tree"],
    "tries": ["tries"],
    "trie": ["tries"],
    "disjoint set union (dsu)": ["graphs"],
    "dsu": ["graphs"],
}

# Dedicated Visualizer mappings per topic
TOPIC_VISUALIZER_MAP = {
    "trees": [
        ResourceLink(
            title="Binary Search Tree & AVL Tree Visualizer",
            url="https://www.cs.usfca.edu/~galles/visualization/BST.html",
            description="Interactive USFCA tree insertion, deletion, and rotation animation.",
            category="visualizer",
        ),
        ResourceLink(
            title="VisuAlgo - Binary Search Tree",
            url="https://visualgo.net/en/bst",
            description="Step-by-step BST traversal and balance visualizer.",
            category="visualizer",
        ),
    ],
    "graphs": [
        ResourceLink(
            title="CS Academy Graph Editor",
            url="https://csacademy.com/app/graph_editor/",
            description="Interactive graph visualizer & layout simulator with custom edge weights.",
            category="visualizer",
        ),
        ResourceLink(
            title="VisuAlgo - Graph Traversal (DFS/BFS)",
            url="https://visualgo.net/en/dfsbfs",
            description="Animated breadth-first and depth-first graph search simulator.",
            category="visualizer",
        ),
        ResourceLink(
            title="Pathfinding Visualizer",
            url="https://clementmihailescu.github.io/Pathfinding-Visualizer/",
            description="Grid-based Dijkstra, A*, and BFS shortest-path animation.",
            category="visualizer",
        ),
    ],
    "recursion": [
        ResourceLink(
            title="Recursion Tree Visualizer",
            url="https://recursion.vercel.app/",
            description="Interactive visualizer generating recursion call trees and stack states.",
            category="visualizer",
        ),
        ResourceLink(
            title="Python Tutor Code Visualizer",
            url="https://pythontutor.com/",
            description="Step-by-step call stack, heap memory, and pointer diagram execution.",
            category="visualizer",
        ),
    ],
    "sorting_searching": [
        ResourceLink(
            title="VisuAlgo - Sorting Algorithms",
            url="https://visualgo.net/en/sorting",
            description="Side-by-side comparison of QuickSort, MergeSort, and HeapSort.",
            category="visualizer",
        ),
        ResourceLink(
            title="Sort Visualizer",
            url="https://www.sortvisualizer.com/",
            description="Live audio-visual sorting algorithm benchmarks.",
            category="visualizer",
        ),
    ],
    "heaps": [
        ResourceLink(
            title="VisuAlgo - Binary Heap / Priority Queue",
            url="https://visualgo.net/en/heap",
            description="Interactive Min-Heap and Max-Heap sift-up and sift-down visualizer.",
            category="visualizer",
        ),
    ],
    "linked_list": [
        ResourceLink(
            title="VisuAlgo - Linked List Data Structure",
            url="https://visualgo.net/en/list",
            description="Singly, doubly, and circular linked list pointer operations visualizer.",
            category="visualizer",
        ),
    ],
    "stacks_queues": [
        ResourceLink(
            title="USFCA Stack and Queue Visualizer",
            url="https://www.cs.usfca.edu/~galles/visualization/StackArray.html",
            description="Array and linked-list implementations of LIFO/FIFO operations.",
            category="visualizer",
        ),
    ],
    "tries": [
        ResourceLink(
            title="USFCA Trie (Prefix Tree) Visualizer",
            url="https://www.cs.usfca.edu/~galles/visualization/Trie.html",
            description="Interactive prefix tree node insertion and substring search simulator.",
            category="visualizer",
        ),
    ],
    "sliding_window": [
        ResourceLink(
            title="Algorithm Visualizer - Sliding Window",
            url="https://algorithm-visualizer.org/",
            description="Contiguous window left/right boundary movement simulator.",
            category="visualizer",
        ),
    ],
    "two_pointers": [
        ResourceLink(
            title="VisuAlgo - Two Pointers / Linear Structures",
            url="https://visualgo.net/en",
            description="Interactive array convergence and partition animation.",
            category="visualizer",
        ),
    ],
    "arrays": [
        ResourceLink(
            title="VisuAlgo - Array Operations & Memory",
            url="https://visualgo.net/en/array",
            description="Fixed-size vs dynamic array allocation visualizer.",
            category="visualizer",
        ),
    ],
    "dynamic_programming": [
        ResourceLink(
            title="Algorithm Visualizer - Dynamic Programming",
            url="https://algorithm-visualizer.org/",
            description="Visual DP table memoization grid filling.",
            category="visualizer",
        ),
    ],
}


def _extract_markdown_links(text: str) -> List[Tuple[str, str]]:
    """Extracts all [title](url) pairs from a markdown string."""
    results = []
    # Pattern matching [Title](url)
    matches = re.findall(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", text)
    for title, url in matches:
        clean_title = re.sub(r"[*_`]", "", title).strip()
        clean_url = url.strip()
        if clean_title and clean_url:
            results.append((clean_title, clean_url))
    return results


def parse_dsa_kit(readme_path: Path | str) -> Dict[str, TopicResource]:
    """
    Parses DSA-KIT README.md into a map of canonical_topic -> TopicResource.
    """
    path = Path(readme_path)
    if not path.exists():
        raise FileNotFoundError(f"DSA-KIT README not found at {path}")

    content = path.read_text(encoding="utf-8", errors="ignore")

    # 1. Parse Global Cheat Sheets from ## Cheat Sheets & Quick References
    global_cheat_sheets: List[ResourceLink] = []
    cheat_sheet_match = re.search(r"## Cheat Sheets & Quick References\s*(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if cheat_sheet_match:
        for title, url in _extract_markdown_links(cheat_sheet_match.group(1)):
            global_cheat_sheets.append(
                ResourceLink(
                    title=title,
                    url=url,
                    category="cheat_sheet",
                    description="Curated algorithmic cheat sheet / quick reference.",
                )
            )

    # 2. Parse Topic-wise Resources from ## Topic-wise Resources
    topic_resources: Dict[str, TopicResource] = {}
    topic_section_match = re.search(r"## Topic-wise Resources\s*(.*?)(?=\n## [A-Z]|\Z)", content, re.DOTALL)
    topic_section_text = topic_section_match.group(1) if topic_section_match else ""

    # Split by ### subsection headers
    subsections = re.findall(r"###\s+([^\n]+)\n(.*?)(?=\n### |\Z)", topic_section_text, re.DOTALL)

    for header, section_body in subsections:
        header_clean = header.strip().lower()
        canonical_tags = CANONICAL_TOPIC_MAP.get(header_clean, [re.sub(r"[^a-z0-9_]+", "_", header_clean)])

        links = _extract_markdown_links(section_body)
        parsed_links = [
            ResourceLink(
                title=t,
                url=u,
                category="learning_resource",
                description=f"Resource from {header.strip()}",
            )
            for t, u in links
        ]

        for tag in canonical_tags:
            if tag not in topic_resources:
                display_name = tag.replace("_", " ").title()
                topic_resources[tag] = TopicResource(
                    canonical_topic=tag,
                    display_name=display_name,
                    visualizers=[],
                    cheat_sheets=[],
                    learning_links=[],
                )
            topic_resources[tag].learning_links.extend(parsed_links)

    # 3. Associate Topic Visualizers and Relevant Cheat Sheets
    for tag, res in topic_resources.items():
        # Add visualizers
        if tag in TOPIC_VISUALIZER_MAP:
            for viz in TOPIC_VISUALIZER_MAP[tag]:
                if viz not in res.visualizers:
                    res.visualizers.append(viz)

        # Map relevant cheat sheets
        for cs in global_cheat_sheets:
            cs_title_lower = cs.title.lower()
            tag_terms = tag.replace("_", " ").split()
            if any(term in cs_title_lower for term in tag_terms) or (tag == "arrays" and "big-o" in cs_title_lower):
                if cs not in res.cheat_sheets:
                    res.cheat_sheets.append(cs)

    # Guarantee canonical topics exist even if missing in subsection titles
    for canonical_key, viz_list in TOPIC_VISUALIZER_MAP.items():
        if canonical_key not in topic_resources:
            topic_resources[canonical_key] = TopicResource(
                canonical_topic=canonical_key,
                display_name=canonical_key.replace("_", " ").title(),
                visualizers=list(viz_list),
                cheat_sheets=[],
                learning_links=[],
            )

    return topic_resources


def build_and_save_topic_resources(
    readme_path: Path | str,
    output_path: Path | str,
) -> Dict[str, dict]:
    """Parses and writes topic_resources.json."""
    resources = parse_dsa_kit(readme_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    serialized = {k: v.model_dump() for k, v in resources.items()}
    out.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved %d topic resources to %s", len(resources), out)
    return serialized


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_ingestion.fetcher import ensure_external_repos
    paths = ensure_external_repos()
    data = build_and_save_topic_resources(
        paths["DSA-KIT"] / "README.md",
        Path(__file__).resolve().parent.parent / "data" / "topic_resources.json",
    )
    print(f"Generated {len(data)} topic resources.")
    for k, v in list(data.items())[:3]:
        print(f"- {k}: {len(v['visualizers'])} visualizers, {len(v['learning_links'])} links")
