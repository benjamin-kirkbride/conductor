"""Semaphore-bounded parallel orchestration of agent evaluations."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from conductor.agent import evaluate_test
from conductor.models import AgentResult, AgentState, AgentStatus, TokenUsage
from conductor.templating import render_prompt

if TYPE_CHECKING:
    from pathlib import Path

    import jinja2

    from conductor.models import ConductorConfig, TestCase


@runtime_checkable
class TuiProtocol(Protocol):
    """Protocol for TUI update callbacks."""

    def update(self, state: AgentState) -> None:
        """Update the TUI with the current agent state."""
        ...


async def orchestrate(  # noqa: PLR0913
    tests: list[TestCase],
    repo_dir: Path,
    config: ConductorConfig,
    template: jinja2.Template,
    directory_tree: str,
    tui: TuiProtocol | None = None,
) -> list[AgentResult]:
    """Run agent evaluations for all tests with bounded concurrency.

    Args:
        tests: List of test cases to evaluate.
        repo_dir: Path to the cloned repository.
        config: Conductor configuration.
        template: Jinja2 prompt template.
        directory_tree: String representation of the repo tree.
        tui: Optional TUI to receive state updates.

    Returns:
        List of AgentResults in the same order as the input tests.
    """
    semaphore = asyncio.Semaphore(config.parallel)

    async def run_one(test: TestCase) -> AgentResult:
        state = AgentState(test=test)
        if tui is not None:
            tui.update(state)

        async with semaphore:
            state.status = AgentStatus.RUNNING
            state.start_time = time.monotonic()
            if tui is not None:
                tui.update(state)

            try:
                prompt = render_prompt(template, test, directory_tree)
                result = await evaluate_test(test, prompt, repo_dir)
            except Exception as exc:  # noqa: BLE001
                state.status = AgentStatus.FAILED
                state.end_time = time.monotonic()
                if tui is not None:
                    tui.update(state)
                return AgentResult(
                    test=test,
                    is_tautology=False,
                    reason=str(exc),
                    status=AgentStatus.FAILED,
                    usage=TokenUsage(
                        input_tokens=0,
                        output_tokens=0,
                        total_cost_usd=0.0,
                    ),
                )

            state.status = AgentStatus.DONE
            state.result = result
            state.end_time = time.monotonic()
            if tui is not None:
                tui.update(state)
            return result

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(run_one(test)) for test in tests]

    return [task.result() for task in tasks]
