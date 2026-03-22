"""CSV output for tautology detection results."""

import csv
from pathlib import Path

from conductor.models import AgentResult


def write_csv(results: list[AgentResult], output_path: Path) -> None:
    """Write tautological test results to a CSV file.

    Only results where is_tautology is True are written. Appends to
    existing files without re-writing the header row.

    Args:
        results: List of agent results to filter and write.
        output_path: Path to the CSV output file.
    """
    tautologies = [r for r in results if r.is_tautology]
    write_header = not output_path.exists() or output_path.stat().st_size == 0
    with output_path.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["test", "reason"])
        for result in tautologies:
            writer.writerow([result.test.name, result.reason])
