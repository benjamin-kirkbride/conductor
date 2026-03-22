"""Test discovery: clone repos and collect pytest tests."""

import re
import subprocess
import tempfile
from pathlib import Path

from conductor.models import TestCase


def consolidate_tests(raw_lines: list[str]) -> list[TestCase]:
    """Strip parameterized suffixes and deduplicate, preserving order."""
    seen: dict[str, None] = {}
    for line in raw_lines:
        nodeid = re.sub(r"\[.*\]$", "", line)
        seen.setdefault(nodeid, None)
    return [
        TestCase(name=nodeid, file_path=nodeid.split("::")[0])
        for nodeid in seen
    ]


def discover_tests(repo_dir: Path) -> list[TestCase]:
    """Run pytest --collect-only and return consolidated test cases."""
    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    raw_lines = [
        line for line in result.stdout.splitlines()
        if "::" in line and line.strip()
    ]
    return consolidate_tests(raw_lines)


def clone_repo(url: str) -> Path:
    """Clone a git repo (shallow) into a temp directory and return its path."""
    dest = Path(tempfile.mkdtemp(prefix="conductor-"))
    subprocess.run(
        ["git", "clone", "--depth=1", url, str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )
    return dest
