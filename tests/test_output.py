from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from conductor.models import AgentResult, AgentStatus, TestCase, TokenUsage
from conductor.output import write_csv

if TYPE_CHECKING:
    from pathlib import Path


def _make_result(
    name: str = "tests/test_foo.py::test_bar",
    *,
    is_tautology: bool = True,
    reason: str = "Test always passes",
) -> AgentResult:
    return AgentResult(
        test=TestCase(name=name, file_path="tests/test_foo.py"),
        is_tautology=is_tautology,
        reason=reason,
        status=AgentStatus.DONE,
        usage=TokenUsage(input_tokens=100, output_tokens=50, total_cost_usd=0.005),
    )


def _read_csv(path: Path) -> list[list[str]]:
    with path.open(newline="") as f:
        return list(csv.reader(f))


class TestWriteCsv:
    def test_new_file_gets_header_and_data(self, tmp_path: Path):
        output = tmp_path / "results.csv"
        results = [_make_result()]
        write_csv(results, output)
        rows = _read_csv(output)
        assert rows[0] == ["test", "reason"]
        assert rows[1] == ["tests/test_foo.py::test_bar", "Test always passes"]
        assert len(rows) == 2

    def test_only_tautological_results_written(self, tmp_path: Path):
        output = tmp_path / "results.csv"
        results = [
            _make_result("test_a", is_tautology=True, reason="taut"),
            _make_result("test_b", is_tautology=False, reason="not taut"),
            _make_result("test_c", is_tautology=True, reason="also taut"),
        ]
        write_csv(results, output)
        rows = _read_csv(output)
        assert len(rows) == 3  # header + 2 tautological
        assert rows[1][0] == "test_a"
        assert rows[2][0] == "test_c"

    def test_append_to_existing_file_skips_header(self, tmp_path: Path):
        output = tmp_path / "results.csv"
        write_csv([_make_result("test_first")], output)
        write_csv([_make_result("test_second")], output)
        rows = _read_csv(output)
        # One header, two data rows
        assert rows[0] == ["test", "reason"]
        assert len(rows) == 3
        assert rows[1][0] == "test_first"
        assert rows[2][0] == "test_second"

    def test_append_to_empty_existing_file_writes_header(self, tmp_path: Path):
        output = tmp_path / "results.csv"
        output.touch()  # empty file exists
        write_csv([_make_result()], output)
        rows = _read_csv(output)
        assert rows[0] == ["test", "reason"]
        assert len(rows) == 2

    def test_empty_results_new_file_writes_header_only(self, tmp_path: Path):
        output = tmp_path / "results.csv"
        write_csv([], output)
        rows = _read_csv(output)
        assert rows == [["test", "reason"]]

    def test_csv_escaping(self, tmp_path: Path):
        output = tmp_path / "results.csv"
        results = [_make_result(reason='reason with "quotes" and, commas')]
        write_csv(results, output)
        rows = _read_csv(output)
        assert rows[1][1] == 'reason with "quotes" and, commas'
