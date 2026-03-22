"""Tests for the discovery module."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from conductor.discovery import clone_repo, consolidate_tests, discover_tests
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


# --- discover_tests ---


@patch("conductor.discovery.subprocess.run")
def test_discover_tests_parses_output(mock_run: patch) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=(
            "tests/test_a.py::test_one\n"
            "tests/test_a.py::test_two[1]\n"
            "tests/test_a.py::test_two[2]\n"
            "\n"
            "3 tests collected in 0.05s\n"
        ),
        stderr="",
    )
    result = discover_tests(Path("/fake/repo"))
    assert result == [
        TestCase(name="tests/test_a.py::test_one", file_path="tests/test_a.py"),
        TestCase(name="tests/test_a.py::test_two", file_path="tests/test_a.py"),
    ]
    mock_run.assert_called_once_with(
        ["pytest", "--collect-only", "-q"],
        cwd=Path("/fake/repo"),
        capture_output=True,
        text=True,
        check=True,
    )


@patch("conductor.discovery.subprocess.run")
def test_discover_tests_empty_collection(mock_run: patch) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="\nno tests ran in 0.01s\n",
        stderr="",
    )
    result = discover_tests(Path("/fake/repo"))
    assert result == []


@patch("conductor.discovery.subprocess.run")
def test_discover_tests_filters_non_nodeid_lines(mock_run: patch) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=(
            "WARNING: some warning\n"
            "tests/test_a.py::test_one\n"
            "  some indented junk\n"
            "\n"
            "1 test collected in 0.02s\n"
        ),
        stderr="",
    )
    result = discover_tests(Path("/fake/repo"))
    assert result == [
        TestCase(name="tests/test_a.py::test_one", file_path="tests/test_a.py"),
    ]


@patch("conductor.discovery.subprocess.run")
def test_discover_tests_propagates_subprocess_error(mock_run: patch) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["pytest"]
    )
    with pytest.raises(subprocess.CalledProcessError):
        discover_tests(Path("/fake/repo"))


# --- clone_repo ---


@patch("conductor.discovery.subprocess.run")
def test_clone_repo_calls_git_correctly(mock_run: patch) -> None:
    result = clone_repo("https://github.com/example/repo.git")
    assert isinstance(result, Path)
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert cmd[:3] == ["git", "clone", "--depth=1"]
    assert cmd[3] == "https://github.com/example/repo.git"
    assert call_args[1]["check"] is True
    assert call_args[1]["capture_output"] is True


@patch("conductor.discovery.subprocess.run")
def test_clone_repo_returns_path(mock_run: patch) -> None:
    path = clone_repo("https://github.com/example/repo.git")
    assert isinstance(path, Path)
    assert path.exists()


@patch("conductor.discovery.subprocess.run")
def test_clone_repo_propagates_subprocess_error(mock_run: patch) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=128, cmd=["git"]
    )
    with pytest.raises(subprocess.CalledProcessError):
        clone_repo("https://github.com/example/repo.git")
