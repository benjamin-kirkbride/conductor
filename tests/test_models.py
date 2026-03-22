"""Tests for conductor data models."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from conductor.models import (
    AgentResult,
    AgentState,
    AgentStatus,
    ConductorConfig,
    TestCase,
    TokenUsage,
)


class TestAgentStatus:
    def test_enum_members(self) -> None:
        assert AgentStatus.QUEUED.value == "queued"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.DONE.value == "done"
        assert AgentStatus.FAILED.value == "failed"

    def test_enum_count(self) -> None:
        assert len(AgentStatus) == 4


class TestTestCase:
    def test_construction(self) -> None:
        tc = TestCase(name="tests/test_foo.py::test_bar", file_path="tests/test_foo.py")
        assert tc.name == "tests/test_foo.py::test_bar"
        assert tc.file_path == "tests/test_foo.py"

    def test_frozen(self) -> None:
        tc = TestCase(name="t", file_path="f")
        with pytest.raises(FrozenInstanceError):
            tc.name = "other"  # type: ignore[misc]


class TestTokenUsage:
    def test_construction(self) -> None:
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_cost_usd=0.01)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_cost_usd == 0.01

    def test_frozen(self) -> None:
        usage = TokenUsage(input_tokens=1, output_tokens=2, total_cost_usd=0.0)
        with pytest.raises(FrozenInstanceError):
            usage.input_tokens = 99  # type: ignore[misc]


class TestAgentResult:
    def test_construction(self) -> None:
        tc = TestCase(name="test_a", file_path="a.py")
        usage = TokenUsage(input_tokens=10, output_tokens=5, total_cost_usd=0.001)
        result = AgentResult(
            test=tc,
            is_tautology=True,
            reason="just restates the code",
            status=AgentStatus.DONE,
            usage=usage,
        )
        assert result.test is tc
        assert result.is_tautology is True
        assert result.reason == "just restates the code"
        assert result.status is AgentStatus.DONE
        assert result.usage is usage

    def test_frozen(self) -> None:
        tc = TestCase(name="t", file_path="f")
        usage = TokenUsage(input_tokens=0, output_tokens=0, total_cost_usd=0.0)
        result = AgentResult(
            test=tc, is_tautology=False, reason="", status=AgentStatus.DONE, usage=usage
        )
        with pytest.raises(FrozenInstanceError):
            result.reason = "new"  # type: ignore[misc]


class TestAgentState:
    def test_defaults(self) -> None:
        tc = TestCase(name="t", file_path="f")
        state = AgentState(test=tc)
        assert state.test is tc
        assert state.status is AgentStatus.QUEUED
        assert state.result is None
        assert state.start_time is None
        assert state.end_time is None

    def test_mutable(self) -> None:
        tc = TestCase(name="t", file_path="f")
        usage = TokenUsage(input_tokens=0, output_tokens=0, total_cost_usd=0.0)
        result = AgentResult(
            test=tc,
            is_tautology=False,
            reason="ok",
            status=AgentStatus.DONE,
            usage=usage,
        )
        state = AgentState(test=tc)
        state.status = AgentStatus.RUNNING
        state.result = result
        state.start_time = 1.0
        state.end_time = 2.0
        assert state.status is AgentStatus.RUNNING
        assert state.result is result
        assert state.start_time == 1.0
        assert state.end_time == 2.0


class TestConductorConfig:
    def test_construction_all_fields(self) -> None:
        config = ConductorConfig(
            repo_url="https://github.com/foo/bar",
            template_path=Path("template.j2"),
            output_path=Path("out.csv"),
            parallel=10,
            dry_run=True,
            limit=3,
        )
        assert config.repo_url == "https://github.com/foo/bar"
        assert config.template_path == Path("template.j2")
        assert config.output_path == Path("out.csv")
        assert config.parallel == 10
        assert config.dry_run is True
        assert config.limit == 3

    def test_defaults(self) -> None:
        config = ConductorConfig(
            repo_url="https://github.com/foo/bar",
            template_path=Path("t.j2"),
            output_path=Path("o.csv"),
        )
        assert config.parallel == 5
        assert config.dry_run is False
        assert config.limit is None

    def test_frozen(self) -> None:
        config = ConductorConfig(
            repo_url="https://github.com/foo/bar",
            template_path=Path("t.j2"),
            output_path=Path("o.csv"),
        )
        with pytest.raises(FrozenInstanceError):
            config.parallel = 99  # type: ignore[misc]
