"""Jinja2 template loading and rendering for agent prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import jinja2

if TYPE_CHECKING:
    from pathlib import Path

    from conductor.models import TestCase


def load_template(path: Path) -> jinja2.Template:
    """Load a Jinja2 template from a file path.

    Args:
        path: Path to the template file.

    Returns:
        A compiled Jinja2 template.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    if not path.exists():
        msg = f"Template not found: {path}"
        raise FileNotFoundError(msg)
    return jinja2.Template(path.read_text())


def render_prompt(template: jinja2.Template, test: TestCase, directory_tree: str) -> str:
    """Render a prompt template with test case variables.

    Args:
        template: A compiled Jinja2 template.
        test: The test case to render the prompt for.
        directory_tree: A string representation of the repository tree.

    Returns:
        The rendered prompt string.
    """
    return template.render(
        test_name=test.name,
        file_path=test.file_path,
        directory_tree=directory_tree,
    )


def build_directory_tree(repo_dir: Path) -> str:
    """Build a directory tree string for a repository.

    Walks the directory recursively, skipping .git directories,
    and produces an indented tree of filenames (no file contents).

    Args:
        repo_dir: Root directory to walk.

    Returns:
        An indented tree string with the directory name as root.
    """
    lines: list[str] = [repo_dir.name + "/"]
    _walk_tree(repo_dir, "", lines)
    return "\n".join(lines)


def _walk_tree(directory: Path, prefix: str, lines: list[str]) -> None:
    """Recursively walk a directory and append tree lines.

    Args:
        directory: Current directory to list.
        prefix: Indentation prefix for the current level.
        lines: Accumulator for tree lines.
    """
    entries = sorted(directory.iterdir(), key=lambda p: p.name)
    for entry_path in entries:
        if entry_path.name == ".git":
            continue
        if entry_path.is_dir():
            lines.append(f"{prefix}{entry_path.name}/")
            _walk_tree(entry_path, prefix + "  ", lines)
        else:
            lines.append(f"{prefix}{entry_path.name}")
