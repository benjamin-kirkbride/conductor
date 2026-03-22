"""Tests for the discovery module."""

from conductor.discovery import consolidate_tests
from conductor.models import TestCase


def test_consolidate_empty_list() -> None:
    assert consolidate_tests([]) == []


def test_consolidate_plain_nodeids() -> None:
    raw = [
        "tests/test_a.py::test_one",
        "tests/test_b.py::test_two",
    ]
    result = consolidate_tests(raw)
    assert result == [
        TestCase(name="tests/test_a.py::test_one", file_path="tests/test_a.py"),
        TestCase(name="tests/test_b.py::test_two", file_path="tests/test_b.py"),
    ]


def test_consolidate_parameterized_deduplication() -> None:
    raw = [
        "tests/test_a.py::test_foo[1]",
        "tests/test_a.py::test_foo[2]",
        "tests/test_a.py::test_foo[abc-xyz]",
    ]
    result = consolidate_tests(raw)
    assert result == [
        TestCase(name="tests/test_a.py::test_foo", file_path="tests/test_a.py"),
    ]


def test_consolidate_mixed_preserves_order() -> None:
    raw = [
        "tests/test_a.py::test_bar",
        "tests/test_a.py::test_foo[1]",
        "tests/test_a.py::test_foo[2]",
        "tests/test_b.py::test_baz",
    ]
    result = consolidate_tests(raw)
    assert result == [
        TestCase(name="tests/test_a.py::test_bar", file_path="tests/test_a.py"),
        TestCase(name="tests/test_a.py::test_foo", file_path="tests/test_a.py"),
        TestCase(name="tests/test_b.py::test_baz", file_path="tests/test_b.py"),
    ]


def test_consolidate_nested_brackets() -> None:
    raw = [
        "tests/test_a.py::test_foo[param[0]]",
        "tests/test_a.py::test_foo[param[1]]",
    ]
    result = consolidate_tests(raw)
    assert result == [
        TestCase(name="tests/test_a.py::test_foo", file_path="tests/test_a.py"),
    ]
