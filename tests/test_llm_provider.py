"""Unit tests for LLM provider orchestration and key validation."""

import pytest
from ytrag.llm_provider import get_provider_details, validate_api_key, generate_llm_answer


def test_get_provider_details_defaults():
    # Grok
    url, model = get_provider_details("grok")
    assert "api.x.ai" in url
    assert "grok" in model.lower()

    # Groq
    url, model = get_provider_details("groq")
    assert "api.groq.com" in url
    assert "llama" in model.lower()

    # OpenAI
    url, model = get_provider_details("openai")
    assert "api.openai.com" in url
    assert "gpt-4o" in model.lower()

    # Custom override
    url, model = get_provider_details("custom", custom_base_url="http://localhost:11434/v1", custom_model="qwen2.5:3b")
    assert url == "http://localhost:11434/v1"
    assert model == "qwen2.5:3b"


def test_validate_api_key_empty():
    res = validate_api_key("groq", "")
    assert res["valid"] is False
    assert "empty" in res["error"].lower()


def test_validate_api_key_invalid_auth():
    # An intentionally bogus key should fail gracefully with invalid key error, not crash
    res = validate_api_key("groq", "gsk_invalid_test_key_12345", timeout=4.0)
    assert res["valid"] is False
    assert "error" in res
    assert ("401" in res["error"] or "authentication" in res["error"].lower() or "connection" in res["error"].lower())
