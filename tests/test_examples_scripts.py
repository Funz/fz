#!/usr/bin/env python3
"""
Test examples/*.py scripts and validate Python code blocks in examples/*.md files.

- Imports and runs examples/*.py scripts
- Extracts and validates Python code blocks from examples/*.md files
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _extract_python_blocks(md_path):
    """Extract all ```python code blocks from a markdown file.

    Returns list of (index, code) tuples.
    """
    text = md_path.read_text(encoding="utf-8")
    all_blocks = re.findall(r"```(\w+)\n(.*?)\n```", text, re.DOTALL)
    python_blocks = []
    for i, (lang, code) in enumerate(all_blocks):
        if lang.lower() == "python":
            python_blocks.append((i, code))
    return python_blocks


class TestExampleScripts:
    """Run examples/*.py scripts as subprocesses."""

    def test_fzi_formulas_example(self):
        script = EXAMPLES_DIR / "fzi_formulas_example.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"fzi_formulas_example.py failed:\n{result.stderr}"
        )

    def test_fzi_static_objects_example(self):
        script = EXAMPLES_DIR / "fzi_static_objects_example.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"fzi_static_objects_example.py failed:\n{result.stderr}"
        )

    def test_java_funz_syntax_example(self):
        script = EXAMPLES_DIR / "java_funz_syntax_example.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"java_funz_syntax_example.py failed:\n{result.stderr}"
        )


class TestExampleMarkdownSyntax:
    """Validate Python syntax in examples/*.md code blocks."""

    def _check_md_syntax(self, md_file):
        md_path = EXAMPLES_DIR / md_file
        if not md_path.exists():
            pytest.skip(f"{md_file} not found")
        blocks = _extract_python_blocks(md_path)
        if not blocks:
            pytest.skip(f"No Python blocks in {md_file}")
        errors = []
        for idx, code in blocks:
            try:
                ast.parse(code)
            except SyntaxError as e:
                errors.append(f"Block {idx}: {e}")
        assert not errors, (
            f"Syntax errors in {md_file}:\n" + "\n".join(errors)
        )

    def test_examples_md_python_blocks_valid_syntax(self):
        self._check_md_syntax("examples.md")

    def test_fzd_example_md_python_blocks_valid_syntax(self):
        self._check_md_syntax("fzd_example.md")

    def test_dataframe_input_md_python_blocks_valid_syntax(self):
        self._check_md_syntax("dataframe_input.md")

    def test_algorithm_options_md_python_blocks_valid_syntax(self):
        self._check_md_syntax("algorithm_options_example.md")

    def test_r_interpreter_example_md_python_blocks_valid_syntax(self):
        self._check_md_syntax("r_interpreter_example.md")

    def test_shell_path_example_md_python_blocks_valid_syntax(self):
        self._check_md_syntax("shell_path_example.md")
