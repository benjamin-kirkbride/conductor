"""Rich TUI monitoring dashboard for agent execution."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.table import Table

from conductor.models import AgentStatus, TokenUsage

if TYPE_CHECKING:
    from rich.console import RenderableType

    from conductor.models import AgentState

_COMPLETED_STATUSES = frozenset({AgentStatus.DONE, AgentStatus.FAILED})


class TuiTracker:
    """Tracks and displays agent execution progress."""

    def __init__(self, total: int) -> None:
        """Initialize tracker with the total number of tests to evaluate."""
        self._total = total
        self._states: dict[str, AgentState] = {}
        self._is_tty: bool = sys.stdout.isatty()
        self._live: Live | None = None
        self._previous_log_level: int | None = None

    def start(self) -> None:
        """Start the live display (no-op if not a TTY)."""
        if self._is_tty:
            root_logger = logging.getLogger()
            self._previous_log_level = root_logger.level
            root_logger.setLevel(logging.CRITICAL)
            Console().clear()
            self._live = Live(self._build_display(), refresh_per_second=4)
            self._live.start()

    def stop(self) -> None:
        """Stop the live display and print final summary if non-TTY."""
        if self._live is not None:
            self._live.stop()
            self._live = None
            if self._previous_log_level is not None:
                logging.getLogger().setLevel(self._previous_log_level)
                self._previous_log_level = None
        elif not self._is_tty:
            usage = self.cumulative_usage
            print(
                f"Completed {self.completed_count}/{self._total} | "
                f"Tautologies: {self.tautology_count} | "
                f"Not tautologies: {self.non_tautology_count} | "
                f"Tokens: {usage.input_tokens} in / {usage.output_tokens} out | "
                f"Cost: ${usage.total_cost_usd:.4f}"
            )

    def update(self, state: AgentState) -> None:
        """Update the tracked state for an agent."""
        self._states[state.test.name] = state

        if self._live is not None:
            self._live.update(self._build_display())
        elif not self._is_tty and state.status in _COMPLETED_STATUSES:
            result_label = ""
            if state.result is not None:
                result_label = (
                    " (tautology)"
                    if state.result.is_tautology
                    else " (not tautological)"
                )
            print(
                f"[{self.completed_count}/{self._total}] "
                f"{state.test.name} {state.status.value.upper()}{result_label}"
            )

    @property
    def cumulative_usage(self) -> TokenUsage:
        """Sum token usage across all agents with results."""
        input_tokens = 0
        output_tokens = 0
        total_cost = 0.0
        for s in self._states.values():
            if s.result is not None:
                input_tokens += s.result.usage.input_tokens
                output_tokens += s.result.usage.output_tokens
                total_cost += s.result.usage.total_cost_usd
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=total_cost,
        )

    @property
    def completed_count(self) -> int:
        """Count of agents in DONE or FAILED status."""
        return sum(1 for s in self._states.values() if s.status in _COMPLETED_STATUSES)

    @property
    def tautology_count(self) -> int:
        """Count of completed agents whose result is a tautology."""
        return sum(
            1
            for s in self._states.values()
            if s.result is not None and s.result.is_tautology
        )

    @property
    def non_tautology_count(self) -> int:
        """Count of completed agents whose result is not a tautology."""
        return sum(
            1
            for s in self._states.values()
            if s.result is not None
            and s.result.status == AgentStatus.DONE
            and not s.result.is_tautology
        )

    def _build_display(self) -> RenderableType:
        """Build the Rich renderable for the live display."""
        table = Table(title="Conductor Agent Monitor")
        table.add_column("Test", style="cyan", no_wrap=True)
        table.add_column("Tool", style="yellow", justify="right")

        for name, state in self._states.items():
            if state.status == AgentStatus.RUNNING:
                tool_text = state.last_tool or "..."
                table.add_row(name, tool_text)

        usage = self.cumulative_usage
        table.add_section()
        table.add_row(
            f"Progress: {self.completed_count}/{self._total}    "
            f"Tautologies: {self.tautology_count}    "
            f"Not tautologies: {self.non_tautology_count}",
            f"${usage.total_cost_usd:.4f}",
        )
        table.add_row(
            "",
            f"{usage.input_tokens:,} in / {usage.output_tokens:,} out",
        )

        return table
