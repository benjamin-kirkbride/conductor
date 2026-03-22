"""Tests for conductor TUI monitoring dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from conductor.models import (
    AgentResult,
    AgentState,
    AgentStatus,
    TestCase,
    TokenUsage,
)
from conductor.tui import TuiTracker

if TYPE_CHECKING:
    import pytest


def _make_test(name: str = "tests/test_foo.py::test_bar") -> TestCase:
    return TestCase(name=name, file_path=name.split("::", maxsplit=1)[0])


def _make_usage(
    input_tokens: int = 100, output_tokens: int = 50, cost: float = 0.005
) -> TokenUsage:
    return TokenUsage(
        input_tokens=input_tokens, output_tokens=output_tokens, total_cost_usd=cost
    )


def _make_result(
    test: TestCase | None = None,
    *,
    status: AgentStatus = AgentStatus.DONE,
    usage: TokenUsage | None = None,
) -> AgentResult:
    t = test or _make_test()
    return AgentResult(
        test=t,
        is_tautology=False,
        reason="ok",
        status=status,
        usage=usage or _make_usage(),
    )


def _make_state(
    name: str = "tests/test_foo.py::test_bar",
    *,
    status: AgentStatus = AgentStatus.QUEUED,
    result: AgentResult | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
) -> AgentState:
    return AgentState(
        test=_make_test(name),
        status=status,
        result=result,
        start_time=start_time,
        end_time=end_time,
    )


def _make_tracker(total: int = 5) -> TuiTracker:
    """Create a TuiTracker with TTY disabled to avoid Rich Live in tests."""
    with patch("conductor.tui.sys.stdout") as mock_stdout:
        mock_stdout.isatty.return_value = False
        return TuiTracker(total=total)


class TestTuiTrackerStateManagement:
    def test_update_stores_state(self) -> None:
        tracker = _make_tracker()
        state = _make_state()
        tracker.update(state)
        assert tracker._states["tests/test_foo.py::test_bar"] is state

    def test_update_overwrites_previous_state(self) -> None:
        tracker = _make_tracker()
        state1 = _make_state(status=AgentStatus.QUEUED)
        state2 = _make_state(status=AgentStatus.RUNNING)
        tracker.update(state1)
        tracker.update(state2)
        assert (
            tracker._states["tests/test_foo.py::test_bar"].status is AgentStatus.RUNNING
        )

    def test_update_multiple_agents(self) -> None:
        tracker = _make_tracker()
        tracker.update(_make_state("test_a"))
        tracker.update(_make_state("test_b"))
        tracker.update(_make_state("test_c"))
        assert len(tracker._states) == 3
        assert "test_a" in tracker._states
        assert "test_b" in tracker._states
        assert "test_c" in tracker._states


class TestTuiTrackerCumulativeUsage:
    def test_no_results_returns_zero_usage(self) -> None:
        tracker = _make_tracker()
        usage = tracker.cumulative_usage
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_cost_usd == 0.0

    def test_single_completed_agent(self) -> None:
        tracker = _make_tracker()
        test = _make_test("test_a")
        result = _make_result(test, usage=_make_usage(200, 100, 0.01))
        tracker.update(_make_state("test_a", status=AgentStatus.DONE, result=result))
        usage = tracker.cumulative_usage
        assert usage.input_tokens == 200
        assert usage.output_tokens == 100
        assert usage.total_cost_usd == 0.01

    def test_multiple_completed_agents_summed(self) -> None:
        tracker = _make_tracker()
        for i, (inp, out, cost) in enumerate([(100, 50, 0.005), (200, 80, 0.01)]):
            name = f"test_{i}"
            test = _make_test(name)
            result = _make_result(test, usage=_make_usage(inp, out, cost))
            tracker.update(_make_state(name, status=AgentStatus.DONE, result=result))
        usage = tracker.cumulative_usage
        assert usage.input_tokens == 300
        assert usage.output_tokens == 130
        assert usage.total_cost_usd == 0.015

    def test_running_agent_excluded_from_cumulative(self) -> None:
        tracker = _make_tracker()
        tracker.update(_make_state("test_a", status=AgentStatus.RUNNING))
        usage = tracker.cumulative_usage
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_cost_usd == 0.0

    def test_failed_agent_with_result_included(self) -> None:
        tracker = _make_tracker()
        test = _make_test("test_a")
        result = _make_result(
            test, status=AgentStatus.FAILED, usage=_make_usage(50, 20, 0.002)
        )
        tracker.update(_make_state("test_a", status=AgentStatus.FAILED, result=result))
        usage = tracker.cumulative_usage
        assert usage.input_tokens == 50
        assert usage.output_tokens == 20
        assert usage.total_cost_usd == 0.002


class TestTuiTrackerProgress:
    def test_completed_count_initial(self) -> None:
        tracker = _make_tracker()
        assert tracker.completed_count == 0

    def test_completed_count_done(self) -> None:
        tracker = _make_tracker()
        tracker.update(_make_state("test_a", status=AgentStatus.DONE))
        assert tracker.completed_count == 1

    def test_completed_count_failed(self) -> None:
        tracker = _make_tracker()
        tracker.update(_make_state("test_a", status=AgentStatus.FAILED))
        assert tracker.completed_count == 1

    def test_completed_count_running_not_counted(self) -> None:
        tracker = _make_tracker()
        tracker.update(_make_state("test_a", status=AgentStatus.RUNNING))
        assert tracker.completed_count == 0

    def test_completed_count_queued_not_counted(self) -> None:
        tracker = _make_tracker()
        tracker.update(_make_state("test_a", status=AgentStatus.QUEUED))
        assert tracker.completed_count == 0

    def test_completed_count_mixed(self) -> None:
        tracker = _make_tracker(total=4)
        tracker.update(_make_state("test_a", status=AgentStatus.QUEUED))
        tracker.update(_make_state("test_b", status=AgentStatus.RUNNING))
        tracker.update(_make_state("test_c", status=AgentStatus.DONE))
        tracker.update(_make_state("test_d", status=AgentStatus.FAILED))
        assert tracker.completed_count == 2

    def test_total_stored(self) -> None:
        tracker = _make_tracker(total=42)
        assert tracker._total == 42


class TestTuiTrackerNonTty:
    def test_non_tty_start_does_not_create_live(self) -> None:
        tracker = _make_tracker()
        tracker.start()
        assert tracker._live is None

    def test_non_tty_update_prints_on_done(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tracker = _make_tracker(total=3)
        tracker.start()
        tracker.update(_make_state("test_a", status=AgentStatus.DONE))
        captured = capsys.readouterr()
        assert "test_a" in captured.out
        assert "DONE" in captured.out

    def test_non_tty_update_prints_on_failed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tracker = _make_tracker(total=3)
        tracker.start()
        tracker.update(_make_state("test_a", status=AgentStatus.FAILED))
        captured = capsys.readouterr()
        assert "test_a" in captured.out
        assert "FAILED" in captured.out

    def test_non_tty_update_silent_on_running(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tracker = _make_tracker(total=3)
        tracker.start()
        tracker.update(_make_state("test_a", status=AgentStatus.RUNNING))
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_non_tty_stop_prints_summary(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tracker = _make_tracker(total=2)
        tracker.start()
        test = _make_test("test_a")
        result = _make_result(test, usage=_make_usage(100, 50, 0.005))
        tracker.update(_make_state("test_a", status=AgentStatus.DONE, result=result))
        # Clear the DONE print
        capsys.readouterr()
        tracker.stop()
        captured = capsys.readouterr()
        assert "1/2" in captured.out
        assert "100" in captured.out  # input tokens


class TestTuiTrackerLifecycle:
    def test_start_creates_live_in_tty_mode(self) -> None:
        with patch("conductor.tui.sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            tracker = TuiTracker(total=5)
        with patch("conductor.tui.Live") as mock_live_cls:
            mock_live = MagicMock()
            mock_live_cls.return_value = mock_live
            tracker.start()
            assert tracker._live is mock_live
            mock_live.start.assert_called_once()

    def test_stop_stops_live_in_tty_mode(self) -> None:
        with patch("conductor.tui.sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            tracker = TuiTracker(total=5)
        mock_live = MagicMock()
        tracker._live = mock_live
        tracker.stop()
        mock_live.stop.assert_called_once()
        assert tracker._live is None

    def test_update_refreshes_live_display(self) -> None:
        with patch("conductor.tui.sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            tracker = TuiTracker(total=5)
        mock_live = MagicMock()
        tracker._live = mock_live
        tracker.update(_make_state("test_a", status=AgentStatus.RUNNING))
        mock_live.update.assert_called_once()
        assert "test_a" in tracker._states

    def test_stop_without_start_is_safe(self) -> None:
        tracker = _make_tracker()
        tracker.stop()  # should not raise

    def test_stop_without_start_tty_is_safe(self) -> None:
        with patch("conductor.tui.sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            tracker = TuiTracker(total=5)
        tracker.stop()  # _live is None, _is_tty is True: no-op


class TestBuildDisplay:
    def test_build_display_returns_renderable(self) -> None:
        tracker = _make_tracker(total=3)
        tracker.update(_make_state("test_a", status=AgentStatus.RUNNING))
        test = _make_test("test_b")
        result = _make_result(test, usage=_make_usage(100, 50, 0.005))
        tracker.update(_make_state("test_b", status=AgentStatus.DONE, result=result))
        display = tracker._build_display()
        # Smoke test: just verify it returns something renderable
        assert display is not None

    def test_build_display_empty_states(self) -> None:
        tracker = _make_tracker(total=0)
        display = tracker._build_display()
        assert display is not None
