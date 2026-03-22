from pathlib import Path

import pytest

from conductor.models import AgentResult, AgentStatus, TestCase, TokenUsage


class TestAgentStatus:
    def test_members(self):
        assert AgentStatus.QUEUED.value == "queued"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.DONE.value == "done"
        assert AgentStatus.FAILED.value == "failed"

    def test_member_count(self):
        assert len(AgentStatus) == 4


class TestTokenUsage:
    def test_construction(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_cost_usd=0.005)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_cost_usd == 0.005

    def test_frozen(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_cost_usd=0.005)
        with pytest.raises(AttributeError):
            usage.input_tokens = 200  # type: ignore[misc]


class TestTestCase:
    def test_construction(self):
        tc = TestCase(name="tests/test_foo.py::test_bar", file_path=Path("tests/test_foo.py"))
        assert tc.name == "tests/test_foo.py::test_bar"
        assert tc.file_path == Path("tests/test_foo.py")

    def test_frozen(self):
        tc = TestCase(name="test", file_path=Path("test.py"))
        with pytest.raises(AttributeError):
            tc.name = "other"  # type: ignore[misc]


class TestAgentResult:
    def test_construction(self):
        tc = TestCase(name="tests/test_foo.py::test_bar", file_path=Path("tests/test_foo.py"))
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_cost_usd=0.005)
        result = AgentResult(
            test=tc,
            is_tautology=True,
            reason="Test always passes",
            status=AgentStatus.DONE,
            usage=usage,
        )
        assert result.test is tc
        assert result.is_tautology is True
        assert result.reason == "Test always passes"
        assert result.status == AgentStatus.DONE
        assert result.usage is usage

    def test_frozen(self):
        tc = TestCase(name="test", file_path=Path("test.py"))
        usage = TokenUsage(input_tokens=0, output_tokens=0, total_cost_usd=0.0)
        result = AgentResult(
            test=tc,
            is_tautology=False,
            reason="",
            status=AgentStatus.QUEUED,
            usage=usage,
        )
        with pytest.raises(AttributeError):
            result.is_tautology = True  # type: ignore[misc]
