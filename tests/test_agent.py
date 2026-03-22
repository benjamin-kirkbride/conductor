from pathlib import Path
from unittest.mock import patch

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
)

from conductor.agent import AgentError, _extract_usage, _parse_output, evaluate_test
from conductor.models import AgentStatus, TestCase, TokenUsage


def _make_test() -> TestCase:
    return TestCase(name="tests/test_foo.py::test_bar", file_path="tests/test_foo.py")


def _make_result_message(
    *,
    structured_output=None,
    result=None,
    is_error=False,
    usage=None,
    total_cost_usd=None,
) -> ResultMessage:
    return ResultMessage(
        subtype="result",
        duration_ms=1000,
        duration_api_ms=900,
        is_error=is_error,
        num_turns=1,
        session_id="test-session",
        result=result,
        structured_output=structured_output,
        usage=usage,
        total_cost_usd=total_cost_usd,
    )


async def _fake_query(*messages):
    for msg in messages:
        yield msg


class TestEvaluateTestStructuredOutput:
    async def test_returns_correct_agent_result(self):
        test = _make_test()
        result_msg = _make_result_message(
            structured_output={"is_tautology": True, "reason": "test is tautological"},
            usage={"input_tokens": 100, "output_tokens": 50},
            total_cost_usd=0.01,
        )

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(result_msg),
        ):
            result = await evaluate_test(test, "prompt", Path("/repo"))

        assert result.test == test
        assert result.is_tautology is True
        assert result.reason == "test is tautological"
        assert result.status == AgentStatus.DONE
        assert result.usage == TokenUsage(
            input_tokens=100, output_tokens=50, total_cost_usd=0.01
        )


class TestEvaluateTestJsonFallback:
    async def test_parses_result_as_json(self):
        test = _make_test()
        result_msg = _make_result_message(
            result='{"is_tautology": false, "reason": "not tautological"}',
            usage={"input_tokens": 10, "output_tokens": 5},
            total_cost_usd=0.001,
        )

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(result_msg),
        ):
            result = await evaluate_test(test, "prompt", Path("/repo"))

        assert result.is_tautology is False
        assert result.reason == "not tautological"


class TestEvaluateTestNoResultMessage:
    async def test_raises_agent_error(self):
        test = _make_test()
        assistant_msg = AssistantMessage(
            content=[TextBlock(text="hello")], model="claude-sonnet-4-6"
        )

        with (
            patch(
                "conductor.agent.claude_agent_sdk.query",
                return_value=_fake_query(assistant_msg),
            ),
            pytest.raises(AgentError, match="No ResultMessage received"),
        ):
            await evaluate_test(test, "prompt", Path("/repo"))


class TestEvaluateTestIsError:
    async def test_raises_agent_error_with_message(self):
        test = _make_test()
        result_msg = _make_result_message(
            is_error=True, result="something went wrong"
        )

        with (
            patch(
                "conductor.agent.claude_agent_sdk.query",
                return_value=_fake_query(result_msg),
            ),
            pytest.raises(AgentError, match="something went wrong"),
        ):
            await evaluate_test(test, "prompt", Path("/repo"))


class TestEvaluateTestUnparseableJson:
    async def test_raises_agent_error(self):
        test = _make_test()
        result_msg = _make_result_message(result="not valid json{{")

        with (
            patch(
                "conductor.agent.claude_agent_sdk.query",
                return_value=_fake_query(result_msg),
            ),
            pytest.raises(AgentError, match="Failed to parse result JSON"),
        ):
            await evaluate_test(test, "prompt", Path("/repo"))


class TestEvaluateTestNoOutput:
    async def test_raises_agent_error(self):
        test = _make_test()
        result_msg = _make_result_message()

        with (
            patch(
                "conductor.agent.claude_agent_sdk.query",
                return_value=_fake_query(result_msg),
            ),
            pytest.raises(AgentError, match="No output from agent"),
        ):
            await evaluate_test(test, "prompt", Path("/repo"))


class TestEvaluateTestNullUsageDefaults:
    async def test_defaults_to_zero(self):
        test = _make_test()
        result_msg = _make_result_message(
            structured_output={"is_tautology": False, "reason": "ok"},
        )

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(result_msg),
        ):
            result = await evaluate_test(test, "prompt", Path("/repo"))

        assert result.usage == TokenUsage(
            input_tokens=0, output_tokens=0, total_cost_usd=0.0
        )


class TestEvaluateTestPassesCorrectOptions:
    async def test_query_called_with_correct_options(self):
        test = _make_test()
        result_msg = _make_result_message(
            structured_output={"is_tautology": False, "reason": "ok"},
            usage={"input_tokens": 0, "output_tokens": 0},
            total_cost_usd=0.0,
        )

        captured_kwargs: dict = {}

        def mock_query(**kwargs):
            captured_kwargs.update(kwargs)
            return _fake_query(result_msg)

        with patch("conductor.agent.claude_agent_sdk.query", side_effect=mock_query):
            await evaluate_test(test, "my prompt", Path("/my/repo"))

        assert captured_kwargs["prompt"] == "my prompt"

        options = captured_kwargs["options"]
        assert isinstance(options, ClaudeAgentOptions)
        assert options.allowed_tools == ["Read", "Grep", "Glob"]
        assert str(options.cwd) == "/my/repo"
        assert options.permission_mode == "bypassPermissions"
        assert options.output_format is not None
        assert options.output_format["type"] == "json_schema"


class TestEvaluateTestIgnoresNonResultMessages:
    async def test_uses_only_result_message(self):
        test = _make_test()
        assistant_msg = AssistantMessage(
            content=[TextBlock(text="thinking...")], model="claude-sonnet-4-6"
        )
        result_msg = _make_result_message(
            structured_output={"is_tautology": True, "reason": "tautological"},
            usage={"input_tokens": 50, "output_tokens": 25},
            total_cost_usd=0.005,
        )

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(assistant_msg, result_msg),
        ):
            result = await evaluate_test(test, "prompt", Path("/repo"))

        assert result.is_tautology is True
        assert result.status == AgentStatus.DONE


class TestParseOutput:
    def test_structured_output(self):
        msg = _make_result_message(
            structured_output={"is_tautology": True, "reason": "yes"}
        )
        test = _make_test()
        assert _parse_output(msg, test) == {"is_tautology": True, "reason": "yes"}

    def test_json_fallback(self):
        msg = _make_result_message(
            result='{"is_tautology": false, "reason": "no"}'
        )
        test = _make_test()
        assert _parse_output(msg, test) == {"is_tautology": False, "reason": "no"}

    def test_invalid_json_raises(self):
        msg = _make_result_message(result="bad json")
        test = _make_test()
        with pytest.raises(AgentError, match="Failed to parse"):
            _parse_output(msg, test)

    def test_no_output_raises(self):
        msg = _make_result_message()
        test = _make_test()
        with pytest.raises(AgentError, match="No output"):
            _parse_output(msg, test)


class TestExtractUsage:
    def test_with_usage(self):
        msg = _make_result_message(
            usage={"input_tokens": 100, "output_tokens": 50},
            total_cost_usd=0.01,
        )
        assert _extract_usage(msg) == TokenUsage(
            input_tokens=100, output_tokens=50, total_cost_usd=0.01
        )

    def test_null_usage(self):
        msg = _make_result_message()
        assert _extract_usage(msg) == TokenUsage(
            input_tokens=0, output_tokens=0, total_cost_usd=0.0
        )
