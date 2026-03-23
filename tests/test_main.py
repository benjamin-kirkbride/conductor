"""Tests for the conductor CLI entry point."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conductor.__main__ import main
from conductor.models import AgentResult, AgentStatus, TestCase, TokenUsage

_BASE_ARGV = [
    "conductor",
    "https://github.com/foo/bar",
    "--template",
    "t.j2",
    "--output",
    "out.csv",
]

_DRY_RUN_ARGV = [*_BASE_ARGV, "--dry-run"]


def _make_test(name: str = "tests/test_foo.py::test_it") -> TestCase:
    return TestCase(name=name, file_path=name.split("::", maxsplit=1)[0])


def _make_result(test: TestCase) -> AgentResult:
    return AgentResult(
        test=test,
        is_tautology=False,
        reason="ok",
        status=AgentStatus.DONE,
        usage=TokenUsage(input_tokens=10, output_tokens=5, total_cost_usd=0.01),
    )


_FAKE_TMP = Path("/tmp/conductor-abc")  # noqa: S108
_TESTS = [
    _make_test("tests/test_a.py::test_one"),
    _make_test("tests/test_b.py::test_two"),
]
_RESULTS = [_make_result(t) for t in _TESTS]
_TREE = "repo/\n  src/"
_TEMPLATE = MagicMock()


@contextlib.contextmanager
def _apply_patches(patches: dict[str, Any]):
    """Context manager that applies all patches simultaneously."""
    with contextlib.ExitStack() as stack:
        for target, mock_obj in patches.items():
            stack.enter_context(patch(target, mock_obj))
        yield


def _base_patches() -> dict[str, Any]:
    """Return a dict of common patches for main() tests."""
    return {
        "conductor.__main__.clone_repo": MagicMock(return_value=_FAKE_TMP),
        "conductor.__main__.discover_tests": MagicMock(return_value=_TESTS),
        "conductor.__main__.load_template": MagicMock(return_value=_TEMPLATE),
        "conductor.__main__.build_directory_tree": MagicMock(return_value=_TREE),
        "conductor.__main__.render_prompt": MagicMock(
            side_effect=lambda _t, tc, _dt: f"prompt:{tc.name}"
        ),
        "conductor.__main__.orchestrate": AsyncMock(return_value=_RESULTS),
        "conductor.__main__.write_csv": MagicMock(),
        "conductor.__main__.shutil": MagicMock(),
    }


class TestDryRun:
    """Tests for dry-run mode."""

    def test_prints_all_tests(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", _DRY_RUN_ARGV)
        patches = _base_patches()
        with _apply_patches(patches), pytest.raises(SystemExit, match="0"):
            main()

        out = capsys.readouterr().out
        assert "--- tests/test_a.py::test_one ---" in out
        assert "prompt:tests/test_a.py::test_one" in out
        assert "--- tests/test_b.py::test_two ---" in out
        assert "prompt:tests/test_b.py::test_two" in out
        patches["conductor.__main__.orchestrate"].assert_not_called()
        patches["conductor.__main__.write_csv"].assert_not_called()

    def test_with_limit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", [*_DRY_RUN_ARGV, "--limit", "1"])
        patches = _base_patches()
        with _apply_patches(patches), pytest.raises(SystemExit, match="0"):
            main()

        out = capsys.readouterr().out
        assert "--- tests/test_a.py::test_one ---" in out
        assert "tests/test_b.py::test_two" not in out


class TestNormalRun:
    """Tests for normal (non-dry-run) mode."""

    def test_orchestrates_and_writes_csv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", _BASE_ARGV)
        patches = _base_patches()
        mock_tui_instance = MagicMock()
        patches["conductor.__main__.TuiTracker"] = MagicMock(
            return_value=mock_tui_instance
        )
        with _apply_patches(patches), pytest.raises(SystemExit, match="0"):
            main()

        patches["conductor.__main__.orchestrate"].assert_called_once()
        call_kwargs = patches["conductor.__main__.orchestrate"].call_args
        assert call_kwargs[0][0] == _TESTS
        assert call_kwargs[0][1] == _FAKE_TMP
        assert call_kwargs[1]["tui"] is mock_tui_instance
        patches["conductor.__main__.write_csv"].assert_called_once_with(
            _RESULTS, Path("out.csv")
        )

    def test_with_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", [*_BASE_ARGV, "--limit", "1"])
        patches = _base_patches()
        mock_tui_instance = MagicMock()
        patches["conductor.__main__.TuiTracker"] = MagicMock(
            return_value=mock_tui_instance
        )
        with _apply_patches(patches), pytest.raises(SystemExit, match="0"):
            main()

        call_args = patches["conductor.__main__.orchestrate"].call_args
        assert call_args[0][0] == _TESTS[:1]
        patches["conductor.__main__.TuiTracker"].assert_called_once_with(total=1)

    def test_tui_start_and_stop_called(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", _BASE_ARGV)
        patches = _base_patches()
        mock_tui_instance = MagicMock()
        patches["conductor.__main__.TuiTracker"] = MagicMock(
            return_value=mock_tui_instance
        )
        with _apply_patches(patches), pytest.raises(SystemExit, match="0"):
            main()

        mock_tui_instance.start.assert_called_once()
        mock_tui_instance.stop.assert_called_once()

    def test_tui_stop_on_orchestrate_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.argv", _BASE_ARGV)
        patches = _base_patches()
        patches["conductor.__main__.orchestrate"] = AsyncMock(
            side_effect=RuntimeError("agent boom")
        )
        mock_tui_instance = MagicMock()
        patches["conductor.__main__.TuiTracker"] = MagicMock(
            return_value=mock_tui_instance
        )
        with _apply_patches(patches), pytest.raises(SystemExit, match="1"):
            main()

        mock_tui_instance.stop.assert_called_once()


class TestCleanup:
    """Tests for tmp_dir cleanup in the finally block."""

    def test_cleanup_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", [*_BASE_ARGV, "--dry-run"])
        patches = _base_patches()
        with _apply_patches(patches), pytest.raises(SystemExit, match="0"):
            main()

        patches["conductor.__main__.shutil"].rmtree.assert_called_once_with(
            _FAKE_TMP, ignore_errors=True
        )

    def test_cleanup_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", _BASE_ARGV)
        patches = _base_patches()
        patches["conductor.__main__.discover_tests"] = MagicMock(
            side_effect=RuntimeError("discover boom")
        )
        with _apply_patches(patches), pytest.raises(SystemExit, match="1"):
            main()

        patches["conductor.__main__.shutil"].rmtree.assert_called_once_with(
            _FAKE_TMP, ignore_errors=True
        )

    def test_cleanup_skipped_when_clone_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.argv", _BASE_ARGV)
        patches = _base_patches()
        patches["conductor.__main__.clone_repo"] = MagicMock(
            side_effect=RuntimeError("clone boom")
        )
        with _apply_patches(patches), pytest.raises(SystemExit, match="1"):
            main()

        patches["conductor.__main__.shutil"].rmtree.assert_not_called()
