"""
Deterministic Context Enricher for DSA Queries.
Queries topic_resources.json and curriculum_graph.json to extract
interactive visualizers, prerequisites, next logical curriculum topics,
and curated practice problems.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TOPIC_RESOURCES_PATH = BASE_DIR / "data" / "topic_resources.json"
CURRICULUM_GRAPH_PATH = BASE_DIR / "data" / "curriculum_graph.json"


class ContextEnricher:
    """
    Enriches retrieval contexts with deterministic visualizer, curriculum,
    and problem routing metadata.
    """

    def __init__(
        self,
        topic_resources_path: Path | str = TOPIC_RESOURCES_PATH,
        curriculum_graph_path: Path | str = CURRICULUM_GRAPH_PATH,
    ):
        self.topic_resources_path = Path(topic_resources_path)
        self.curriculum_graph_path = Path(curriculum_graph_path)
        self.resources: Dict[str, dict] = {}
        self.curriculum: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.topic_resources_path.exists():
            try:
                self.resources = json.loads(self.topic_resources_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load topic resources: %s", exc)

        if self.curriculum_graph_path.exists():
            try:
                self.curriculum = json.loads(self.curriculum_graph_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load curriculum graph: %s", exc)

    def enrich(self, canonical_topics: List[str], max_problems: int = 3) -> Dict[str, Any]:
        """
        Gathers visualizers, curriculum prerequisites/next topics, and practice problems
        for the given canonical topics.
        """
        if not canonical_topics:
            return {
                "canonical_topics": [],
                "visualizers": [],
                "cheat_sheets": [],
                "prerequisites": [],
                "next_topics": [],
                "practice_problems": [],
            }

        visualizers: List[dict] = []
        cheat_sheets: List[dict] = []
        prereqs: List[str] = []
        next_topics: List[str] = []
        problems: List[dict] = []

        seen_viz_urls = set()
        seen_cs_urls = set()
        seen_prob_urls = set()

        for tag in canonical_topics:
            # 1. Fetch visualizers and cheat sheets from topic_resources.json
            res = self.resources.get(tag, {})
            for viz in res.get("visualizers", []):
                u = viz.get("url")
                if u and u not in seen_viz_urls:
                    seen_viz_urls.add(u)
                    visualizers.append(viz)

            for cs in res.get("cheat_sheets", []):
                u = cs.get("url")
                if u and u not in seen_cs_urls:
                    seen_cs_urls.add(u)
                    cheat_sheets.append(cs)

            # 2. Fetch curriculum node (prereqs, next_topics, practice_problems)
            node = self.curriculum.get(tag, {})
            for p in node.get("prerequisites", []):
                p_display = self.curriculum.get(p, {}).get("display_name", p.replace("_", " ").title())
                if p_display not in prereqs:
                    prereqs.append(p_display)

            for n in node.get("next_topics", []):
                n_display = self.curriculum.get(n, {}).get("display_name", n.replace("_", " ").title())
                if n_display not in next_topics:
                    next_topics.append(n_display)

            for prob in node.get("practice_problems", []):
                u = prob.get("url")
                if u and u not in seen_prob_urls:
                    seen_prob_urls.add(u)
                    problems.append(prob)

        # Slice to max problems
        curated_problems = problems[:max_problems]

        return {
            "canonical_topics": canonical_topics,
            "visualizers": visualizers[:3],
            "cheat_sheets": cheat_sheets[:2],
            "prerequisites": prereqs,
            "next_topics": next_topics,
            "practice_problems": curated_problems,
        }

    def format_markdown_section(self, enrichment_data: Dict[str, Any]) -> str:
        """
        Formats the deterministic enrichment metadata into clean GitHub-flavored Markdown
        to be appended to the LLM response.
        """
        lines = ["\n\n---\n### 🛠️ Practice, Visualizers & Next Steps\n"]

        # Visualizers
        viz_list = enrichment_data.get("visualizers", [])
        if viz_list:
            lines.append("**Interactive Visualizers:**")
            for v in viz_list:
                desc = f" — *{v.get('description', '')}*" if v.get("description") else ""
                lines.append(f"- 🎨 [{v['title']}]({v['url']}){desc}")
            lines.append("")

        # Curriculum Path
        prereqs = enrichment_data.get("prerequisites", [])
        next_top = enrichment_data.get("next_topics", [])
        if prereqs or next_top:
            lines.append("**Curriculum Roadmap & Prerequisites:**")
            if prereqs:
                lines.append(f"- ⬅️ **Prerequisites:** {', '.join(prereqs)}")
            if next_top:
                lines.append(f"- ➡️ **Next Logical Topic:** {', '.join(next_top)}")
            lines.append("")

        # Practice Problems
        probs = enrichment_data.get("practice_problems", [])
        if probs:
            lines.append("**Curated Practice Problems:**")
            for idx, p in enumerate(probs, start=1):
                diff = f" • *{p.get('difficulty', 'Medium')}*" if p.get("difficulty") else ""
                plat = p.get("platform", "LeetCode")
                lines.append(f"{idx}. 💻 [{p['title']}]({p['url']}) ({plat}{diff})")
            lines.append("")

        return "\n".join(lines).strip()


_global_enricher: Optional[ContextEnricher] = None


def get_context_enricher() -> ContextEnricher:
    """Returns singleton ContextEnricher."""
    global _global_enricher
    if _global_enricher is None:
        _global_enricher = ContextEnricher()
    return _global_enricher


if __name__ == "__main__":
    enricher = ContextEnricher()
    data = enricher.enrich(["sliding_window"])
    print(enricher.format_markdown_section(data))
