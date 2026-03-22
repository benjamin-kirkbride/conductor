"""Rich TUI monitoring dashboard for agent execution."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.live import Live
from rich.table import Table
from rich.text import Text

from conductor.models import AgentStatus, TokenUsage

if TYPE_CHECKING:
    from rich.console import RenderableType

    from conductor.models import AgentState

_STATUS_STYLE: dict[AgentStatus, str] = {
    AgentStatus.QUEUED: "dim",
    AgentStatus.RUNNING: "yellow",
    AgentStatus.DONE: "green",
    AgentStatus.FAILED: "red",
}

_COMPLETED_STATUSES = frozenset({AgentStatus.DONE, AgentStatus.FAILED})


class TuiTracker:
    """Tracks and displays agent execution progress."""

    def __init__(self, total: int) -> None:
        """Initialize tracker with the total number of tests to evaluate."""
        self._total = total
        self._states: dict[str, AgentState] = {}
        self._is_tty: bool = sys.stdout.isatty()
        self._live: Live | None = None

    def start(self) -> None:
        """Start the live display (no-op if not a TTY)."""
        if self._is_tty:
            self._live = Live(self._build_display(), refresh_per_second=4)
            self._live.start()

    def stop(self) -> None:
        """Stop the live display and print final summary if non-TTY."""
        if self._live is not None:
            self._live.stop()
            self._live = None
        elif not self._is_tty:
            usage = self.cumulative_usage
            print(
                f"Completed {self.completed_count}/{self._total} | "
                f"Tokens: {usage.input_tokens} in / {usage.output_tokens} out | "
                f"Cost: ${usage.total_cost_usd:.4f}"
            )

    def update(self, state: AgentState) -> None:
        """Update the tracked state for an agent."""
        self._states[state.test.name] = state

        if self._live is not None:
            self._live.update(self._build_display())
        elif not self._is_tty and state.status in _COMPLETED_STATUSES:
            print(
                f"[{self.completed_count}/{self._total}] "
                f"{state.test.name} {state.status.value.upper()}"
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

    def _build_display(self) -> RenderableType:
        """Build the Rich renderable for the live display."""
        table = Table(title="Conductor Agent Monitor")
        table.add_column("Test", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Tokens", justify="right")

        for name, state in self._states.items():
            style = _STATUS_STYLE.get(state.status, "white")
            status_text = Text(state.status.value.upper(), style=style)
            tokens = ""
            if state.result is not None:
                u = state.result.usage
                tokens = f"{u.input_tokens + u.output_tokens:,}"
            table.add_row(name, status_text, tokens)

        usage = self.cumulative_usage
        table.add_section()
        table.add_row(
            f"Progress: {self.completed_count}/{self._total}",
            "",
            f"${usage.total_cost_usd:.4f}",
        )
        table.add_row(
            "",
            "",
            f"{usage.input_tokens:,} in / {usage.output_tokens:,} out",
        )

        return table
