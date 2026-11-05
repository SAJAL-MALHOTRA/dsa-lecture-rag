"""
Strict Pydantic schemas for multi-source DSA ingestion, topic resources,
curriculum graph, and pattern code chunks.
"""

from __future__ import annotations

from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field, field_validator, model_validator


class ResourceLink(BaseModel):
    """External link to a visualizer, cheat sheet, or article."""
    title: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    description: Optional[str] = ""
    category: Optional[str] = ""

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("URL cannot be empty")
        if not (clean.startswith("http://") or clean.startswith("https://")):
            raise ValueError(f"URL must start with http:// or https://: '{clean}'")
        return clean

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Title cannot be empty")
        return clean


class TopicResource(BaseModel):
    """Structured catalog entry for visualizers, cheat sheets, and learning tools."""
    canonical_topic: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    visualizers: List[ResourceLink] = Field(default_factory=list)
    cheat_sheets: List[ResourceLink] = Field(default_factory=list)
    learning_links: List[ResourceLink] = Field(default_factory=list)


class PracticeProblem(BaseModel):
    """A practice problem link for a specific DSA curriculum topic."""
    title: str = Field(..., min_length=1)
    platform: str = Field(..., min_length=1)  # "LeetCode", "GeeksforGeeks", "Codeforces", etc.
    url: str = Field(..., min_length=1)
    difficulty: Optional[str] = "Medium"
    tag: Optional[str] = ""

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("URL cannot be empty")
        if not (clean.startswith("http://") or clean.startswith("https://")):
            raise ValueError(f"URL must start with http:// or https://: '{clean}'")
        return clean


class CurriculumTopic(BaseModel):
    """Sequential course curriculum node with prerequisites and curated practice problems."""
    canonical_topic: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    module_order: int = Field(..., ge=1)
    prerequisites: List[str] = Field(default_factory=list)
    next_topics: List[str] = Field(default_factory=list)
    practice_problems: List[PracticeProblem] = Field(default_factory=list)


class CurriculumGraph(BaseModel):
    """Complete curriculum graph mapping canonical topics to their sequence and problems."""
    topics: Dict[str, CurriculumTopic] = Field(default_factory=dict)


class TopicResourcesCatalog(BaseModel):
    """Catalog of topic visualizers, cheat sheets, and learning links."""
    resources: Dict[str, TopicResource] = Field(default_factory=dict)


class PatternChunk(BaseModel):
    """A clean code template, pattern explanation, or core article excerpt."""
    chunk_id: str = Field(..., min_length=1)
    source: str = Field(default="awesome-leetcode-resources")
    content_type: Literal["pattern_code", "pattern_explanation", "article_template"]
    pattern_name: str = Field(..., min_length=1)
    language: str = Field(default="general")  # "cpp", "python", "java", "general"
    canonical_topic: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    url: Optional[str] = None
