"""Unit tests for Striver DSA sheet adapter and search index."""

import pytest
from pathlib import Path
from ytrag.dsa_sheet import DSASheetIndex, parse_solution_file, DSASolution


def test_dsa_sheet_index_loading():
    idx = DSASheetIndex(Path("data/strivers_a2z_sheet"))
    assert len(idx.solutions) > 300, "Should load all 360+ problems from sheet"


def test_dsa_sheet_search_exact_and_synonyms():
    idx = DSASheetIndex(Path("data/strivers_a2z_sheet"))

    # Two sum / 2 sum
    sol1, _ = idx.get_best_match("two sum")
    assert sol1 is not None
    assert "2 Sum" in sol1.title or "Two Sum" in sol1.title

    sol2, _ = idx.get_best_match("2 sum")
    assert sol2 is not None
    assert "2 Sum" in sol2.title

    # Kadane's algorithm
    sol_kadane, _ = idx.get_best_match("kadane")
    assert sol_kadane is not None
    assert "Kadane" in sol_kadane.title
    assert "O(N)" in sol_kadane.time_complexity

    # Detect cycle in linked list
    sol_cycle, _ = idx.get_best_match("detect cycle in linked list")
    assert sol_cycle is not None
    assert "Loop" in sol_cycle.title or "Cycle" in sol_cycle.title


def test_dsa_sheet_multi_language_code():
    idx = DSASheetIndex(Path("data/strivers_a2z_sheet"))
    sol, _ = idx.get_best_match("two sum")
    assert sol is not None
    assert sol.code_cpp != ""
    assert sol.code_python != ""
    assert sol.code_java != ""
    assert "def " in sol.code_python or "twoSum" in sol.code_python
    assert "public class Solution" in sol.code_java
