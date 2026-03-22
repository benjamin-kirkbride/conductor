"""Tests for the conductor CLI entry point."""

import pytest

from conductor.__main__ import main


def test_main_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify main() parses args and exits with code 0."""
    monkeypatch.setattr(
        "sys.argv",
        ["conductor", "https://github.com/foo/bar", "--template", "t.j2", "--output", "out.csv"],
    )
    with pytest.raises(SystemExit, match="0"):
        main()
