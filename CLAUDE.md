# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Conductor is a CLI tool that evaluates pytest test suites for tautologies using parallel Claude agents (via the Claude Agent SDK). It clones a GitHub repo, discovers tests via `pytest --collect-only`, renders a Jinja2 prompt template per test, spawns bounded-concurrency agents to evaluate each test, and writes tautologies to a CSV. A Rich TUI monitors agent status, token usage, and progress.

### CLI usage
```
conductor <github-repo-url> \
  --template PATH       # Jinja2 prompt template
  --output PATH         # CSV output file
  --parallel N          # Max concurrent agents (default: 5)
  --dry-run             # Show tests + rendered prompts, don't run agents
  --limit N             # Limit output in dry-run mode
```

### Architecture
See epic issue #7 for the dependency graph. Key modules:
- `models.py` — shared types (TestCase, AgentResult, AgentState, ConductorConfig, etc.)
- `discovery.py` — git clone + pytest collection + parameterized test consolidation
- `templating.py` — Jinja2 template loading/rendering + directory tree builder
- `agent.py` — single agent evaluation via `claude_agent_sdk.query()`
- `orchestrator.py` — `asyncio.Semaphore` + `TaskGroup` bounded parallel execution
- `output.py` — CSV writer (append mode)
- `tui.py` — Rich Live monitoring dashboard
- `cli.py` — argparse → ConductorConfig

## Don't
- ever use `—` (use - instead)
- NEVER commit directly to main. Always work on a feature branch and merge via PR or explicit user-requested merge.
- Never update `.meta/pragma_no_count`. If the pragma check fails, stop and alert the user - do not adjust the count to make it pass.
- Never update `.meta/flaky_count`. If the flaky check fails, stop and alert the user - do not adjust the count to make it pass.
- Never use `gh pr merge --admin` to bypass branch protection. When asked to merge a PR, wait for CI to pass, watch for failures, and fix any issues. Only merge once all checks are green.

## Refactoring
- For multi-file renames and refactoring (functions, variables, classes, modules), use `rope` instead of sed/text-based find-replace. Rope understands Python's AST and scoping, so it won't silently rename unrelated matches.

## Do
- Always write tests first, verify they fail, then write the code to make them pass.
- 100% test coverage is enforced. `# pragma: no cover` is acceptable in rare cases (e.g. `if __name__ == "__main__"` guards) but must have an inline comment explaining why testing is impractical. Never use `# pragma: no cover` on code that is merely "impossible" to reach - if it's truly impossible, delete it; if it's reachable, test it.
- Commit early and often when making changes. Pre-commit hooks run the full test suite, so there's no need to run it yourself right before committing - though running relevant tests earlier can save time by catching failures sooner.
- Close relevant GitHub issues when creating/merging PRs that complete them

## Testing philosophy
- **Prefer integration tests over unit tests.** Tests should exercise real code paths, not just verify that mocks were called.
- **Never mock the thing you're testing.** If you're testing a function, actually call it with real inputs, don't mock out its internals.
- **Mocking is acceptable only for true external boundaries**: network I/O, the Claude Agent SDK's API calls, and system calls. If you find yourself mocking a module to make a test pass, that's a sign the test should be an integration test instead.
- **A test that passes when the code is broken is worse than no test.** Every test should be able to catch at least one real bug.
- **Watch out for tautological tests.** When planning tests, ask: "does this test assert something about the *behavior* of the code, or does it just re-state what the code does?"

## Coverage failures
- **Coverage failures are always real.** Never assume a coverage miss is a tooling bug, flaky merging, or non-deterministic artifact. Every time coverage reports a missing line or branch, investigate the specific line/branch and write a test that hits it.

## Development Commands

```
uv run pytest                          # run all tests
uv run pytest -m "not slow"            # skip slow tests
uv run ruff check src/ tests/          # lint
uv run ruff format src/ tests/         # format
uv run mypy src/conductor              # type check
uv run pre-commit run --all-files      # run all pre-commit hooks
```
