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
