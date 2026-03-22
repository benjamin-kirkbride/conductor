"""Tests for conductor CLI argument parsing."""

from pathlib import Path

import pytest

from conductor.cli import parse_args

BASE_ARGV = [
    "https://github.com/foo/bar",
    "--template",
    "prompt.j2",
    "--output",
    "results.csv",
]


class TestParseArgs:
    def test_repo_url(self) -> None:
        config = parse_args(BASE_ARGV)
        assert config.repo_url == "https://github.com/foo/bar"

    def test_template_path(self) -> None:
        config = parse_args(BASE_ARGV)
        assert config.template_path == Path("prompt.j2")

    def test_output_path(self) -> None:
        config = parse_args(BASE_ARGV)
        assert config.output_path == Path("results.csv")

    def test_parallel_default(self) -> None:
        config = parse_args(BASE_ARGV)
        assert config.parallel == 5

    def test_parallel_custom(self) -> None:
        config = parse_args([*BASE_ARGV, "--parallel", "10"])
        assert config.parallel == 10

    def test_dry_run_default(self) -> None:
        config = parse_args(BASE_ARGV)
        assert config.dry_run is False

    def test_dry_run_flag(self) -> None:
        config = parse_args([*BASE_ARGV, "--dry-run"])
        assert config.dry_run is True

    def test_limit_default(self) -> None:
        config = parse_args(BASE_ARGV)
        assert config.limit is None

    def test_limit_custom(self) -> None:
        config = parse_args([*BASE_ARGV, "--limit", "3"])
        assert config.limit == 3

    def test_all_flags(self) -> None:
        argv = [
            "https://github.com/a/b",
            "--template",
            "t.j2",
            "--output",
            "o.csv",
            "--parallel",
            "8",
            "--dry-run",
            "--limit",
            "5",
        ]
        config = parse_args(argv)
        assert config.repo_url == "https://github.com/a/b"
        assert config.template_path == Path("t.j2")
        assert config.output_path == Path("o.csv")
        assert config.parallel == 8
        assert config.dry_run is True
        assert config.limit == 5

    def test_missing_repo_url(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--template", "t.j2", "--output", "o.csv"])

    def test_missing_template(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["https://github.com/a/b", "--output", "o.csv"])

    def test_missing_output(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["https://github.com/a/b", "--template", "t.j2"])
