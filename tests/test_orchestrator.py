import asyncio
from pathlib import Path
from unittest.mock import patch

import jinja2

from conductor.models import (
    AgentResult,
    AgentState,
    AgentStatus,
    ConductorConfig,
    TestCase,
    TokenUsage,
)
from conductor.orchestrator import TuiProtocol, orchestrate


def _make_config(parallel: int = 5) -> ConductorConfig:
    return ConductorConfig(
        repo_url="https://github.com/test/repo",
        template_path=Path("template.j2"),
        output_path=Path("output.csv"),
        parallel=parallel,
    )


def _make_test(name: str = "tests/test_foo.py::test_bar") -> TestCase:
    return TestCase(name=name, file_path=name.split("::", maxsplit=1)[0])


def _make_result(test: TestCase) -> AgentResult:
    return AgentResult(
        test=test,
        is_tautology=False,
        reason="not tautological",
        status=AgentStatus.DONE,
        usage=TokenUsage(input_tokens=10, output_tokens=5, total_cost_usd=0.001),
    )


_TEMPLATE = jinja2.Template("Evaluate {{ test_name }}")
_TREE = "repo/"


class MockTui:
    """Mock TUI that records update calls."""

    def __init__(self):
        self.updates: list[tuple[str, AgentStatus]] = []

    def update(self, state: AgentState) -> None:
        self.updates.append((state.test.name, state.status))


# Verify MockTui satisfies the protocol
_: type[TuiProtocol] = MockTui


class TestOrchestrateSingleTest:
    async def test_single_test_succeeds(self):
        test = _make_test()
        expected = _make_result(test)

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            return expected

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            results = await orchestrate(
                [test], Path("/repo"), _make_config(), _TEMPLATE, _TREE
            )

        assert len(results) == 1
        assert results[0] == expected


class TestOrchestrateMultipleTests:
    async def test_all_results_returned_in_order(self):
        tests = [_make_test(f"tests/test_{i}.py::test_{i}") for i in range(4)]

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            return _make_result(t)

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            results = await orchestrate(
                tests, Path("/repo"), _make_config(), _TEMPLATE, _TREE
            )

        assert len(results) == 4
        for i, result in enumerate(results):
            assert result.test == tests[i]


class TestOrchestrateFailedTestContinuesOthers:
    async def test_failed_test_does_not_stop_others(self):
        tests = [_make_test(f"tests/test_{i}.py::test_{i}") for i in range(3)]

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            if t == tests[1]:
                msg = "agent crashed"
                raise RuntimeError(msg)
            return _make_result(t)

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            results = await orchestrate(
                tests, Path("/repo"), _make_config(), _TEMPLATE, _TREE
            )

        assert len(results) == 3
        assert results[0].status == AgentStatus.DONE
        assert results[1].status == AgentStatus.FAILED
        assert "agent crashed" in results[1].reason
        assert results[2].status == AgentStatus.DONE


class TestOrchestrateSemaphoreLimitsConcurrency:
    async def test_max_concurrent_respects_parallel(self):
        tests = [_make_test(f"tests/test_{i}.py::test_{i}") for i in range(4)]
        peak_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            nonlocal peak_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                peak_concurrent = max(peak_concurrent, current_concurrent)
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return _make_result(t)

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            results = await orchestrate(
                tests, Path("/repo"), _make_config(parallel=2), _TEMPLATE, _TREE
            )

        assert len(results) == 4
        assert peak_concurrent <= 2


class TestOrchestrateTuiUpdates:
    async def test_tui_receives_state_transitions(self):
        test = _make_test()
        tui = MockTui()

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            return _make_result(t)

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            await orchestrate(
                [test], Path("/repo"), _make_config(), _TEMPLATE, _TREE, tui=tui
            )

        statuses = [s for name, s in tui.updates]
        assert AgentStatus.QUEUED in statuses
        assert AgentStatus.RUNNING in statuses
        assert AgentStatus.DONE in statuses


class TestOrchestrateTuiNone:
    async def test_no_error_without_tui(self):
        test = _make_test()

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            return _make_result(t)

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            results = await orchestrate(
                [test], Path("/repo"), _make_config(), _TEMPLATE, _TREE
            )

        assert len(results) == 1


class TestOrchestrateEmptyTests:
    async def test_returns_empty_list(self):
        results = await orchestrate([], Path("/repo"), _make_config(), _TEMPLATE, _TREE)
        assert results == []


class TestOrchestrateTuiFailureTransitions:
    async def test_tui_sees_queued_running_failed(self):
        test = _make_test()
        tui = MockTui()

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            msg = "boom"
            raise RuntimeError(msg)

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            await orchestrate(
                [test], Path("/repo"), _make_config(), _TEMPLATE, _TREE, tui=tui
            )

        statuses = [s for name, s in tui.updates]
        assert AgentStatus.QUEUED in statuses
        assert AgentStatus.RUNNING in statuses
        assert AgentStatus.FAILED in statuses
        assert AgentStatus.DONE not in statuses


class TestOrchestratePreservesOrder:
    async def test_results_match_input_order(self):
        tests = [_make_test(f"tests/test_{i}.py::test_{i}") for i in range(5)]

        async def mock_evaluate(t, prompt, repo_dir, **kwargs):
            # Vary delay to test ordering isn't dependent on completion time
            idx = int(t.name.split("_")[-1].split(".")[0])
            await asyncio.sleep(0.01 * (5 - idx))
            return _make_result(t)

        with patch("conductor.orchestrator.evaluate_test", side_effect=mock_evaluate):
            results = await orchestrate(
                tests, Path("/repo"), _make_config(), _TEMPLATE, _TREE
            )

        for i, result in enumerate(results):
            assert result.test == tests[i]
