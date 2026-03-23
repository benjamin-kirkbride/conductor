"""Agent execution: evaluate a single test case via Claude Agent SDK."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import claude_agent_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    ToolUseBlock,
)

from conductor.models import AgentResult, AgentStatus, TokenUsage

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from claude_agent_sdk import Message

    from conductor.models import TestCase


class AgentError(Exception):
    """Raised when agent execution fails."""


_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "is_tautology": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["is_tautology", "reason"],
    },
}


async def evaluate_test(
    test: TestCase,
    prompt: str,
    repo_dir: Path,
    model: str = "sonnet",
    on_tool_use: Callable[[str], None] | None = None,
) -> AgentResult:
    """Evaluate a single test case for tautology via the Claude Agent SDK.

    Args:
        test: The test case to evaluate.
        prompt: The rendered prompt to send to the agent.
        repo_dir: Path to the cloned repository.
        model: Claude model to use (default: sonnet).
        on_tool_use: Optional callback invoked with the tool name for each tool use.

    Returns:
        An AgentResult with the evaluation outcome.

    Raises:
        AgentError: If the agent fails or returns unparseable output.
    """
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Glob"],
        cwd=str(repo_dir),
        permission_mode="bypassPermissions",
        output_format=_OUTPUT_SCHEMA,
        model=model,
    )

    result_message: ResultMessage | None = None
    total_input = 0
    total_output = 0

    async for message in claude_agent_sdk.query(prompt=prompt, options=options):
        total_input, total_output = _accumulate_usage(
            message, total_input, total_output
        )
        if isinstance(message, ResultMessage):
            result_message = message
        elif on_tool_use is not None and isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    on_tool_use(block.name)

    if result_message is None:
        msg = f"No ResultMessage received for test {test.name}"
        raise AgentError(msg)

    if result_message.is_error:
        error_text = result_message.result or "Unknown agent error"
        msg = f"Agent error for test {test.name}: {error_text}"
        raise AgentError(msg)

    parsed = _parse_output(result_message, test)
    usage = TokenUsage(
        input_tokens=total_input,
        output_tokens=total_output,
        total_cost_usd=result_message.total_cost_usd or 0.0,
    )

    return AgentResult(
        test=test,
        is_tautology=parsed["is_tautology"],
        reason=parsed["reason"],
        status=AgentStatus.DONE,
        usage=usage,
    )


def _parse_output(result_message: ResultMessage, test: TestCase) -> dict[str, Any]:
    """Parse the agent's structured output or JSON result."""
    if result_message.structured_output is not None:
        return cast("dict[str, Any]", result_message.structured_output)
    if result_message.result is not None:
        try:
            return cast("dict[str, Any]", json.loads(result_message.result))
        except json.JSONDecodeError as e:
            msg = f"Failed to parse result JSON for test {test.name}: {e}"
            raise AgentError(msg) from e
    msg = f"No output from agent for test {test.name}"
    raise AgentError(msg)


def _accumulate_usage(
    message: Message, total_input: int, total_output: int
) -> tuple[int, int]:
    """Accumulate token usage from any message that carries a usage dict."""
    usage = getattr(message, "usage", None)
    if isinstance(usage, dict):
        total_input += usage.get("input_tokens", 0)
        total_output += usage.get("output_tokens", 0)
    return total_input, total_output
