from pathlib import Path
from unittest.mock import patch

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from conductor.agent import AgentError, _accumulate_usage, _parse_output, evaluate_test
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
        result_msg = _make_result_message(is_error=True, result="something went wrong")

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
            await evaluate_test(test, "my prompt", Path("/my/repo"), model="opus")

        assert captured_kwargs["prompt"] == "my prompt"

        options = captured_kwargs["options"]
        assert isinstance(options, ClaudeAgentOptions)
        assert options.allowed_tools == ["Read", "Grep", "Glob"]
        assert str(options.cwd) == "/my/repo"
        assert options.permission_mode == "bypassPermissions"
        assert options.output_format is not None
        assert options.output_format["type"] == "json_schema"
        assert options.model == "opus"


class TestEvaluateTestDefaultModel:
    async def test_defaults_to_sonnet(self):
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
            await evaluate_test(test, "prompt", Path("/repo"))

        options = captured_kwargs["options"]
        assert options.model == "sonnet"


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


class TestEvaluateTestAccumulatesTokenUsage:
    async def test_sums_usage_across_all_messages(self):
        test = _make_test()
        assistant_msg1 = AssistantMessage(
            content=[TextBlock(text="thinking...")],
            model="claude-sonnet-4-6",
            usage={"input_tokens": 200, "output_tokens": 100},
        )
        assistant_msg2 = AssistantMessage(
            content=[TextBlock(text="more thinking...")],
            model="claude-sonnet-4-6",
            usage={"input_tokens": 150, "output_tokens": 80},
        )
        result_msg = _make_result_message(
            structured_output={"is_tautology": False, "reason": "ok"},
            usage={"input_tokens": 50, "output_tokens": 20},
            total_cost_usd=0.05,
        )

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(assistant_msg1, assistant_msg2, result_msg),
        ):
            result = await evaluate_test(test, "prompt", Path("/repo"))

        assert result.usage == TokenUsage(
            input_tokens=400, output_tokens=200, total_cost_usd=0.05
        )


class TestParseOutput:
    def test_structured_output(self):
        msg = _make_result_message(
            structured_output={"is_tautology": True, "reason": "yes"}
        )
        test = _make_test()
        assert _parse_output(msg, test) == {"is_tautology": True, "reason": "yes"}

    def test_json_fallback(self):
        msg = _make_result_message(result='{"is_tautology": false, "reason": "no"}')
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


class TestAccumulateUsage:
    def test_with_usage_dict(self):
        msg = _make_result_message(
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        assert _accumulate_usage(msg, 0, 0) == (100, 50)

    def test_accumulates_onto_existing_totals(self):
        msg = _make_result_message(
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        assert _accumulate_usage(msg, 200, 80) == (300, 130)

    def test_no_usage_attribute(self):
        msg = AssistantMessage(
            content=[TextBlock(text="hello")], model="claude-sonnet-4-6"
        )
        assert _accumulate_usage(msg, 10, 5) == (10, 5)

    def test_null_usage(self):
        msg = _make_result_message()
        assert _accumulate_usage(msg, 10, 5) == (10, 5)


class TestOnToolUseCallback:
    async def test_callback_called_for_tool_use_block(self):
        test = _make_test()
        assistant_msg = AssistantMessage(
            content=[ToolUseBlock(id="tu_1", name="Read", input={"file_path": "/f"})],
            model="claude-sonnet-4-6",
        )
        result_msg = _make_result_message(
            structured_output={"is_tautology": False, "reason": "ok"},
            usage={"input_tokens": 10, "output_tokens": 5},
            total_cost_usd=0.001,
        )
        calls: list[str] = []

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(assistant_msg, result_msg),
        ):
            await evaluate_test(
                test, "prompt", Path("/repo"), on_tool_use=calls.append
            )

        assert calls == ["Read"]

    async def test_callback_called_multiple_times(self):
        test = _make_test()
        msg1 = AssistantMessage(
            content=[ToolUseBlock(id="tu_1", name="Read", input={})],
            model="claude-sonnet-4-6",
        )
        msg2 = AssistantMessage(
            content=[ToolUseBlock(id="tu_2", name="Grep", input={})],
            model="claude-sonnet-4-6",
        )
        result_msg = _make_result_message(
            structured_output={"is_tautology": False, "reason": "ok"},
            usage={"input_tokens": 10, "output_tokens": 5},
            total_cost_usd=0.001,
        )
        calls: list[str] = []

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(msg1, msg2, result_msg),
        ):
            await evaluate_test(
                test, "prompt", Path("/repo"), on_tool_use=calls.append
            )

        assert calls == ["Read", "Grep"]

    async def test_none_callback_does_not_error(self):
        test = _make_test()
        assistant_msg = AssistantMessage(
            content=[ToolUseBlock(id="tu_1", name="Read", input={})],
            model="claude-sonnet-4-6",
        )
        result_msg = _make_result_message(
            structured_output={"is_tautology": False, "reason": "ok"},
            usage={"input_tokens": 10, "output_tokens": 5},
            total_cost_usd=0.001,
        )

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(assistant_msg, result_msg),
        ):
            result = await evaluate_test(test, "prompt", Path("/repo"))

        assert result.status == AgentStatus.DONE

    async def test_callback_not_called_for_text_only(self):
        test = _make_test()
        assistant_msg = AssistantMessage(
            content=[TextBlock(text="thinking...")],
            model="claude-sonnet-4-6",
        )
        result_msg = _make_result_message(
            structured_output={"is_tautology": False, "reason": "ok"},
            usage={"input_tokens": 10, "output_tokens": 5},
            total_cost_usd=0.001,
        )
        calls: list[str] = []

        with patch(
            "conductor.agent.claude_agent_sdk.query",
            return_value=_fake_query(assistant_msg, result_msg),
        ):
            await evaluate_test(
                test, "prompt", Path("/repo"), on_tool_use=calls.append
            )

        assert calls == []
