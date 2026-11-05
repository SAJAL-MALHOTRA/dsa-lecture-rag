"""
Data ingestion package for multi-source DSA resources.
"""

from data_ingestion.schemas import (
    ResourceLink,
    TopicResource,
    PracticeProblem,
    CurriculumTopic,
    CurriculumGraph,
    PatternChunk,
)
from data_ingestion.fetcher import ensure_external_repos
from data_ingestion.parse_patterns import parse_patterns_repo, build_and_save_patterns_corpus
from data_ingestion.parse_dsa_kit import parse_dsa_kit, build_and_save_topic_resources
from data_ingestion.parse_curriculum import parse_curriculum_graph, build_and_save_curriculum_graph

__all__ = [
    "ResourceLink",
    "TopicResource",
    "PracticeProblem",
    "CurriculumTopic",
    "CurriculumGraph",
    "PatternChunk",
    "ensure_external_repos",
    "parse_patterns_repo",
    "build_and_save_patterns_corpus",
    "parse_dsa_kit",
    "build_and_save_topic_resources",
    "parse_curriculum_graph",
    "build_and_save_curriculum_graph",
]
