"""Agent execution: evaluate a single test case via Claude Agent SDK."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import claude_agent_sdk
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from conductor.models import AgentResult, AgentStatus, TokenUsage

if TYPE_CHECKING:
    from pathlib import Path

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


async def evaluate_test(test: TestCase, prompt: str, repo_dir: Path) -> AgentResult:
    """Evaluate a single test case for tautology via the Claude Agent SDK.

    Args:
        test: The test case to evaluate.
        prompt: The rendered prompt to send to the agent.
        repo_dir: Path to the cloned repository.

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
    )

    result_message: ResultMessage | None = None
    async for message in claude_agent_sdk.query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_message = message

    if result_message is None:
        msg = f"No ResultMessage received for test {test.name}"
        raise AgentError(msg)

    if result_message.is_error:
        error_text = result_message.result or "Unknown agent error"
        msg = f"Agent error for test {test.name}: {error_text}"
        raise AgentError(msg)

    parsed = _parse_output(result_message, test)
    usage = _extract_usage(result_message)

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
        return cast(dict[str, Any], result_message.structured_output)
    if result_message.result is not None:
        try:
            return cast(dict[str, Any], json.loads(result_message.result))
        except json.JSONDecodeError as e:
            msg = f"Failed to parse result JSON for test {test.name}: {e}"
            raise AgentError(msg) from e
    msg = f"No output from agent for test {test.name}"
    raise AgentError(msg)


def _extract_usage(result_message: ResultMessage) -> TokenUsage:
    """Extract token usage from a ResultMessage."""
    usage = result_message.usage or {}
    return TokenUsage(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        total_cost_usd=result_message.total_cost_usd or 0.0,
    )
