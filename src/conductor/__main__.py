"""CLI entry point for Conductor."""

import logging
import sys

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the Conductor CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("conductor starting")
    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover — CLI entry point guard
    main()
