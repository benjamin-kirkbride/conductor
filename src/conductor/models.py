"""Shared data types for Conductor."""

import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class TestCase:
    """A single test case identified by pytest collection."""

    name: str
    file_path: str
