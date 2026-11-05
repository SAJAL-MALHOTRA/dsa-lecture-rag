"""
Unit tests for the Whisper DSA glossary and prompt generation module.
"""

from ytrag.whisper_glossary import (
    get_whisper_dsa_prompt,
    get_whisper_glossary_dict,
    DSA_GLOSSARY_TOKENS,
    HINGLISH_CUE_PHRASES,
)


def test_get_whisper_dsa_prompt_structure():
    prompt = get_whisper_dsa_prompt(include_hinglish=True)
    assert isinstance(prompt, str)
    assert "Data Structures and Algorithms" in prompt
    assert "Striver" in prompt
    assert "Kadane" in prompt
    assert "two pointers" in prompt
    assert "nums[i]" in prompt


def test_get_whisper_dsa_prompt_without_hinglish():
    prompt_no_hinglish = get_whisper_dsa_prompt(include_hinglish=False)
    assert "samajhte hain" not in prompt_no_hinglish
    assert "Kadane" in prompt_no_hinglish


def test_whisper_glossary_dict_mappings():
    glossary = get_whisper_glossary_dict()
    assert isinstance(glossary, dict)
    assert glossary["can dance"] == "Kadane's"
    assert glossary["dry wine"] == "dry run"
    assert glossary["numbers of eye"] == "nums[i]"
    assert glossary["deep table"] == "DP table"
    assert glossary["breath first search"] == "breadth first search"
