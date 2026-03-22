from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from conductor.models import TestCase
from conductor.templating import build_directory_tree, load_template, render_prompt

if TYPE_CHECKING:
    from pathlib import Path


class TestLoadTemplate:
    def test_loads_valid_template(self, tmp_path: Path):
        template_file = tmp_path / "prompt.j2"
        template_file.write_text("Hello {{ test_name }}")
        template = load_template(template_file)
        assert template.render(test_name="foo") == "Hello foo"

    def test_raises_on_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_template(tmp_path / "nonexistent.j2")


class TestRenderPrompt:
    def test_renders_all_variables(self, tmp_path: Path):
        template_file = tmp_path / "prompt.j2"
        template_file.write_text(
            "Test: {{ test_name }}\nFile: {{ file_path }}\nTree:\n{{ directory_tree }}"
        )
        template = load_template(template_file)
        tc = TestCase(name="tests/test_foo.py::test_bar", file_path="tests/test_foo.py")
        result = render_prompt(template, tc, "src/\n  main.py")
        assert "tests/test_foo.py::test_bar" in result
        assert "tests/test_foo.py" in result
        assert "src/\n  main.py" in result

    def test_renders_with_subset_of_variables(self, tmp_path: Path):
        template_file = tmp_path / "simple.j2"
        template_file.write_text("Analyze: {{ test_name }}")
        template = load_template(template_file)
        tc = TestCase(name="test_something", file_path="test.py")
        result = render_prompt(template, tc, "tree")
        assert result == "Analyze: test_something"


class TestBuildDirectoryTree:
    def test_basic_structure(self, tmp_path: Path):
        (tmp_path / "README.md").touch()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").touch()
        tree = build_directory_tree(tmp_path)
        assert "README.md" in tree
        assert "src" in tree
        assert "main.py" in tree

    def test_skips_git_directory(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").touch()
        (tmp_path / "code.py").touch()
        tree = build_directory_tree(tmp_path)
        assert ".git" not in tree
        assert "config" not in tree
        assert "code.py" in tree

    def test_empty_directory(self, tmp_path: Path):
        tree = build_directory_tree(tmp_path)
        # Should contain just the root directory name
        assert tmp_path.name in tree

    def test_nested_directories(self, tmp_path: Path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "b").mkdir()
        (tmp_path / "a" / "b" / "c.py").touch()
        tree = build_directory_tree(tmp_path)
        assert "a" in tree
        assert "b" in tree
        assert "c.py" in tree

    def test_deterministic_ordering(self, tmp_path: Path):
        # Create files in non-alphabetical order
        (tmp_path / "zebra.py").touch()
        (tmp_path / "alpha.py").touch()
        (tmp_path / "middle.py").touch()
        tree = build_directory_tree(tmp_path)
        lines = tree.splitlines()
        # Find the file entries (skip root)
        file_lines = [line for line in lines if ".py" in line]
        # Should be sorted alphabetically
        assert file_lines[0].strip().startswith("alpha.py")
        assert file_lines[1].strip().startswith("middle.py")
        assert file_lines[2].strip().startswith("zebra.py")

    def test_does_not_include_file_contents(self, tmp_path: Path):
        (tmp_path / "secret.py").write_text("password = 'hunter2'")
        tree = build_directory_tree(tmp_path)
        assert "hunter2" not in tree
        assert "password" not in tree
        assert "secret.py" in tree
