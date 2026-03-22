"""Shared data types for Conductor."""

import enum
from dataclasses import dataclass
from pathlib import Path


class AgentStatus(enum.Enum):
    """Status of an agent processing a test case."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class TokenUsage:
    """Token usage and cost for a single agent run."""

    input_tokens: int
    output_tokens: int
    total_cost_usd: float


@dataclass(frozen=True)
class TestCase:
    """A test case to be analyzed."""

    __test__ = False

    name: str
    file_path: Path


@dataclass(frozen=True)
class AgentResult:
    """Result from an agent analyzing a test case."""

    test: TestCase
    is_tautology: bool
    reason: str
    status: AgentStatus
    usage: TokenUsage
