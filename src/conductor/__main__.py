"""CLI entry point for Conductor."""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
from typing import TYPE_CHECKING

from conductor.cli import parse_args
from conductor.discovery import clone_repo, discover_tests
from conductor.orchestrator import orchestrate
from conductor.output import write_csv
from conductor.templating import build_directory_tree, load_template, render_prompt
from conductor.tui import TuiTracker

if TYPE_CHECKING:
    import jinja2

    from conductor.models import ConductorConfig, TestCase

logger = logging.getLogger(__name__)


def _run_dry_run(
    tests: list[TestCase],
    template: jinja2.Template,
    directory_tree: str,
) -> None:
    """Render and print prompts without running agents."""
    for test in tests:
        prompt = render_prompt(template, test, directory_tree)
        print(f"--- {test.name} ---")
        print(prompt)
        print()


def _run(config: ConductorConfig) -> None:
    """Execute the conductor pipeline."""
    tmp_dir = clone_repo(config.repo_url)
    try:
        tests = discover_tests(tmp_dir)
        if config.limit is not None:
            tests = tests[: config.limit]
        template = load_template(config.template_path)
        directory_tree = build_directory_tree(tmp_dir)

        if config.dry_run:
            _run_dry_run(tests, template, directory_tree)
        else:
            tui = TuiTracker(total=len(tests))
            tui.start()
            try:
                results = asyncio.run(
                    orchestrate(
                        tests, tmp_dir, config, template, directory_tree, tui=tui
                    )
                )
            finally:
                tui.stop()
            write_csv(results, config.output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    """Run the Conductor CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = parse_args()
    logger.info("conductor starting with config: %s", config)

    try:
        _run(config)
    except Exception:
        logger.exception("conductor failed")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover -- CLI entry point guard
    main()
