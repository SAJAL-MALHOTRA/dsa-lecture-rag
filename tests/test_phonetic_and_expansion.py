"""
Unit tests for Hinglish-to-DSA phonetic normalizer and query expansion.
"""

from ytrag.phonetic_normalizer import normalize_dsa_text
from ytrag.query_expander import expand_dsa_query


def test_phonetic_normalizer_slang_corrections():
    # Test Kadane corruption
    assert normalize_dsa_text("can dance algorithm") == "kadane algorithm"
    assert normalize_dsa_text("kadan algorithm") == "kadane algorithm"

    # Test Dry run corruption
    assert normalize_dsa_text("dry wine in binary search") == "dry run in binary search"
    assert normalize_dsa_text("try done for recursion tree") == "dry run for recursion tree"

    # Test Subarray and Two Pointers
    assert normalize_dsa_text("find maximum sab array sum") == "find maximum subarray sum"
    assert normalize_dsa_text("use to pointer approach") == "use two pointers approach"

    # Test spoken indexing
    assert normalize_dsa_text("numbers of eye") == "nums[i]"
    assert normalize_dsa_text("array of mid") == "arr[mid]"

    # Test DP and Graphs
    assert normalize_dsa_text("construct deep table for memoization") == "construct dp table for memoization"
    assert normalize_dsa_text("create adj list for undirected graph") == "create adjacency list for undirected graph"


def test_query_expander_syntax_to_speech():
    # Syntax duplicate skip
    query = "why nums[left] == nums[left-1]"
    expanded = expand_dsa_query(query)
    assert "duplicate" in expanded
    assert "pichla element same" in expanded

    # Binary search boundary
    bs_query = "while low <= high"
    bs_expanded = expand_dsa_query(bs_query)
    assert "binary search pointer cross" in bs_expanded

    # Floyd cycle detection
    cycle_query = "fast = fast->next->next"
    cycle_expanded = expand_dsa_query(cycle_query)
    assert "tortoise and hare" in cycle_expanded
    assert "distance reduces by one" in cycle_expanded


def test_query_expander_with_phonetic_query():
    # Query with phonetic corruption gets normalized and expanded
    raw_query = "can dance sum < 0"
    expanded = expand_dsa_query(raw_query)
    assert "kadane" in expanded
    assert "negative sum reset zero" in expanded
