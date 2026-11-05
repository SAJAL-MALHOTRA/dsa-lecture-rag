"""
Unit tests for multi-source DSA ingestion, schema validation,
URL integrity, code syntax preservation, and enriched retrieval.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import pytest

from data_ingestion.schemas import (
    TopicResource,
    CurriculumTopic,
    PatternChunk,
    PracticeProblem,
    ResourceLink,
)
from ytrag.topic_classifier import classify_canonical_topics
from ytrag.pattern_retriever import PatternRetriever
from ytrag.context_enricher import ContextEnricher

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TOPIC_RESOURCES_PATH = DATA_DIR / "topic_resources.json"
CURRICULUM_GRAPH_PATH = DATA_DIR / "curriculum_graph.json"
PATTERNS_CORPUS_PATH = DATA_DIR / "patterns_corpus.json"


@pytest.fixture(scope="module")
def topic_resources_data() -> dict:
    assert TOPIC_RESOURCES_PATH.exists(), f"Missing {TOPIC_RESOURCES_PATH}"
    return json.loads(TOPIC_RESOURCES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def curriculum_graph_data() -> dict:
    assert CURRICULUM_GRAPH_PATH.exists(), f"Missing {CURRICULUM_GRAPH_PATH}"
    return json.loads(CURRICULUM_GRAPH_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def patterns_corpus_data() -> list:
    assert PATTERNS_CORPUS_PATH.exists(), f"Missing {PATTERNS_CORPUS_PATH}"
    return json.loads(PATTERNS_CORPUS_PATH.read_text(encoding="utf-8"))


def test_topic_resources_schema_and_urls(topic_resources_data):
    """Verifies topic_resources.json conforms to Pydantic schema with strictly valid URLs."""
    assert len(topic_resources_data) >= 10, "Expected at least 10 canonical topics in topic_resources"

    for tag, raw_item in topic_resources_data.items():
        # Schema validation
        item = TopicResource.model_validate(raw_item)
        assert item.canonical_topic == tag
        assert len(item.display_name) > 0

        # Validate Visualizers URLs
        for viz in item.visualizers:
            assert viz.url.startswith("http://") or viz.url.startswith("https://")
            assert len(viz.title) > 0

        # Validate Cheat Sheet URLs
        for cs in item.cheat_sheets:
            assert cs.url.startswith("http://") or cs.url.startswith("https://")
            assert len(cs.title) > 0

        # Validate Learning Links URLs
        for link in item.learning_links:
            assert link.url.startswith("http://") or link.url.startswith("https://")
            assert len(link.title) > 0

    # Specifically check essential topics have interactive visualizers
    for essential_topic in ("trees", "graphs", "recursion", "heaps", "linked_list"):
        assert essential_topic in topic_resources_data
        viz_list = topic_resources_data[essential_topic]["visualizers"]
        assert len(viz_list) >= 1, f"Expected interactive visualizers for {essential_topic}"


def test_curriculum_graph_schema_and_urls(curriculum_graph_data):
    """Verifies curriculum_graph.json validates against schema with non-empty URLs and valid DAG structure."""
    assert len(curriculum_graph_data) >= 15, "Expected at least 15 curriculum topics"

    canonical_set = set(curriculum_graph_data.keys())

    for tag, raw_item in curriculum_graph_data.items():
        # Schema validation
        topic = CurriculumTopic.model_validate(raw_item)
        assert topic.canonical_topic == tag
        assert topic.module_order >= 1

        # Check DAG prerequisite references exist in canonical set
        for prereq in topic.prerequisites:
            assert prereq in canonical_set, f"Prerequisite {prereq} for {tag} not in canonical set"

        for next_t in topic.next_topics:
            assert next_t in canonical_set, f"Next topic {next_t} for {tag} not in canonical set"

        # Check practice problems
        assert len(topic.practice_problems) >= 1, f"Expected practice problems for {tag}"
        for prob in topic.practice_problems:
            assert prob.url.startswith("http://") or prob.url.startswith("https://")
            assert len(prob.title) > 0
            assert prob.platform in ("LeetCode", "GeeksforGeeks", "External")
            assert prob.difficulty in ("Easy", "Medium", "Hard")


def test_awesome_leetcode_code_chunks_syntax_and_metadata(patterns_corpus_data):
    """Verifies code chunks from awesome-leetcode-resources preserve full syntax and metadata."""
    assert len(patterns_corpus_data) >= 30, "Expected at least 30 pattern chunks"

    cpp_count = 0
    python_count = 0

    for raw_chunk in patterns_corpus_data:
        chunk = PatternChunk.model_validate(raw_chunk)
        assert chunk.source == "awesome-leetcode-resources"
        assert chunk.content_type in ("pattern_code", "pattern_explanation", "article_template")
        assert len(chunk.text) > 20

        # Syntax integrity for Python code chunks
        if chunk.language == "python" and chunk.content_type == "pattern_code":
            python_count += 1
            # Must parse without SyntaxError
            try:
                ast.parse(chunk.text)
            except SyntaxError as e:
                pytest.fail(f"Python code chunk {chunk.chunk_id} has invalid syntax: {e}")

        # Syntax integrity for C++ code chunks
        if chunk.language == "cpp" and chunk.content_type == "pattern_code":
            cpp_count += 1
            # Check for fundamental C++ tokens
            assert any(k in chunk.text for k in ("#include", "class", "void", "int", "double", "vector"))
            # Balanced braces
            assert chunk.text.count("{") == chunk.text.count("}"), f"Unbalanced curly braces in {chunk.chunk_id}"

    assert cpp_count >= 5, f"Expected at least 5 C++ code pattern chunks, found {cpp_count}"
    assert python_count >= 5, f"Expected at least 5 Python code pattern chunks, found {python_count}"


def test_sample_query_multi_source_retrieval():
    """
    Verifies that a sample query retrieves both pattern code/explanations
    and deterministic visualizers, prerequisites, and practice problems.
    """
    query = "Explain the sliding window pattern in C++ and give me practice problems"

    # 1. Topic Classification
    canonical_topics = classify_canonical_topics(query)
    assert "sliding_window" in canonical_topics

    # 2. Pattern Retrieval
    pattern_retriever = PatternRetriever(corpus_path=PATTERNS_CORPUS_PATH)
    matched_patterns = pattern_retriever.retrieve(
        query=query,
        k=2,
        canonical_topic=canonical_topics[0],
        language="cpp",
    )
    assert len(matched_patterns) >= 1
    top_chunk, score = matched_patterns[0]
    assert score > 0.0
    assert top_chunk.canonical_topic == "sliding_window"
    assert top_chunk.language in ("cpp", "general")

    # 3. Deterministic Context Enrichment
    enricher = ContextEnricher(
        topic_resources_path=TOPIC_RESOURCES_PATH,
        curriculum_graph_path=CURRICULUM_GRAPH_PATH,
    )
    enrichment = enricher.enrich(canonical_topics, max_problems=3)

    assert "sliding_window" in enrichment["canonical_topics"]
    assert len(enrichment["visualizers"]) >= 1
    assert len(enrichment["prerequisites"]) >= 1
    assert len(enrichment["practice_problems"]) >= 2

    # Check Markdown section formatting
    md_section = enricher.format_markdown_section(enrichment)
    assert "Practice, Visualizers & Next Steps" in md_section
    assert "Interactive Visualizers:" in md_section
    assert "Curriculum Roadmap & Prerequisites:" in md_section
    assert "Curated Practice Problems:" in md_section
