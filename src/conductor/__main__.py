"""CLI entry point for Conductor."""

import logging
import sys

from conductor.cli import parse_args

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the Conductor CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = parse_args()
    logger.info("conductor starting with config: %s", config)
    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover — CLI entry point guard
    main()
