"""Tests for the conductor CLI entry point."""

import pytest

from conductor.__main__ import main


def test_main_exits_cleanly() -> None:
    """Verify main() exits with code 0."""
    with pytest.raises(SystemExit, match="0"):
        main()
