"""CLI argument parsing for Conductor."""

from __future__ import annotations

import argparse
from pathlib import Path

from conductor.models import ConductorConfig


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for Conductor."""
    parser = argparse.ArgumentParser(
        prog="conductor",
        description="AI agent orchestration via the Claude Agent SDK",
    )
    parser.add_argument(
        "repo_url",
        help="GitHub repository URL to analyze",
    )
    parser.add_argument(
        "--template",
        required=True,
        type=Path,
        dest="template_path",
        help="Path to Jinja2 prompt template",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        dest="output_path",
        help="Path to CSV output file",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=5,
        help="Max concurrent agents (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show tests and rendered prompts without running agents",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit output in dry-run mode",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> ConductorConfig:
    """Parse CLI arguments and return a ConductorConfig."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return ConductorConfig(
        repo_url=args.repo_url,
        template_path=args.template_path,
        output_path=args.output_path,
        parallel=args.parallel,
        dry_run=args.dry_run,
        limit=args.limit,
    )
