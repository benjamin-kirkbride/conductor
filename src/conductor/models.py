"""Data models for Conductor."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class AgentStatus(enum.Enum):
    """Status of an agent execution."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TestCase:
    """A single test case to evaluate."""

    name: str
    file_path: str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage and cost for an agent run."""

    input_tokens: int
    output_tokens: int
    total_cost_usd: float


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Result of an agent evaluating a test case."""

    test: TestCase
    is_tautology: bool
    reason: str
    status: AgentStatus
    usage: TokenUsage


@dataclass(slots=True)
class AgentState:
    """Mutable state tracking for a single agent in the TUI."""

    test: TestCase
    status: AgentStatus = AgentStatus.QUEUED
    result: AgentResult | None = None
    start_time: float | None = None
    end_time: float | None = None
    last_tool: str | None = None


@dataclass(frozen=True, slots=True)
class ConductorConfig:
    """Configuration for a Conductor run."""

    repo_url: str
    template_path: Path
    output_path: Path
    parallel: int = 5
    dry_run: bool = False
    limit: int | None = None
    model: str = "sonnet"
