"""Tests for conductor data models."""

import dataclasses

import pytest

from conductor.models import TestCase


def test_testcase_construction() -> None:
    tc = TestCase(name="tests/test_foo.py::test_bar", file_path="tests/test_foo.py")
    assert tc.name == "tests/test_foo.py::test_bar"
    assert tc.file_path == "tests/test_foo.py"


def test_testcase_is_frozen() -> None:
    tc = TestCase(name="tests/test_foo.py::test_bar", file_path="tests/test_foo.py")
    with pytest.raises(dataclasses.FrozenInstanceError):
        tc.name = "other"  # type: ignore[misc]


def test_testcase_equality() -> None:
    a = TestCase(name="tests/test_a.py::test_one", file_path="tests/test_a.py")
    b = TestCase(name="tests/test_a.py::test_one", file_path="tests/test_a.py")
    c = TestCase(name="tests/test_a.py::test_two", file_path="tests/test_a.py")
    assert a == b
    assert a != c


def test_testcase_hashable() -> None:
    a = TestCase(name="tests/test_a.py::test_one", file_path="tests/test_a.py")
    b = TestCase(name="tests/test_a.py::test_one", file_path="tests/test_a.py")
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
