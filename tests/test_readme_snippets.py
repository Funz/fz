#!/usr/bin/env python3
"""
Test README.md code snippets: syntax validation and end-to-end execution.

Extracts Python code blocks from README.md and:
- Validates syntax of ALL Python blocks with ast.parse()
- Runs key executable examples (Quick Start, fzi, fzc) in tmp dirs
"""

import ast
import os
import re
import subprocess
from pathlib import Path

import pytest

import fz

# Path to README.md at the repo root
README_PATH = Path(__file__).parent.parent / "README.md"


def _extract_python_blocks(readme_path):
    """Extract all ```python code blocks from a markdown file.

    Returns list of (index, code) tuples where index is the 0-based
    position among all fenced code blocks.
    """
    text = readme_path.read_text(encoding="utf-8")
    # Match fenced code blocks with language tag
    all_blocks = re.findall(r"```(\w+)\n(.*?)\n```", text, re.DOTALL)
    python_blocks = []
    for i, (lang, code) in enumerate(all_blocks):
        if lang.lower() == "python":
            python_blocks.append((i, code))
    return python_blocks


class TestReadmeSyntax:
    """Validate that every Python code block in README.md has valid syntax."""

    def test_all_python_blocks_have_valid_syntax(self):
        blocks = _extract_python_blocks(README_PATH)
        assert len(blocks) > 0, "No Python code blocks found in README.md"

        errors = []
        for idx, code in blocks:
            try:
                ast.parse(code)
            except SyntaxError as e:
                errors.append(f"Block {idx}: {e}")

        assert not errors, "Syntax errors in README Python blocks:\n" + "\n".join(
            errors
        )


class TestReadmeExamples:
    """Run key README examples end-to-end."""

    def test_quick_start_example(self, tmp_path):
        """Run the Quick Start PerfectGaz example from README."""
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            # Create input.txt
            (tmp_path / "input.txt").write_text(
                "# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L\n"
                "n_mol=$n_mol\n"
                "T_kelvin=@{$T_celsius + 273.15}\n"
                "#@ def L_to_m3(L):\n"
                "#@     return(L / 1000)\n"
                "V_m3=@{L_to_m3($V_L)}\n"
            )

            # Create PerfectGazPressure.sh
            calc_script = tmp_path / "PerfectGazPressure.sh"
            calc_script.write_text(
                "#!/bin/bash\n"
                "\n"
                "# read input file\n"
                "source $1\n"
                "\n"
                "sleep 1 # simulate a calculation time\n"
                "\n"
                "echo 'pressure = '`echo \"scale=4;$n_mol*8.314*$T_kelvin/$V_m3\" | bc` > output.txt\n"
                "\n"
                "echo 'Done'\n"
            )
            calc_script.chmod(0o755)

            model = {
                "varprefix": "$",
                "formulaprefix": "@",
                "delim": "{}",
                "commentline": "#",
                "output": {
                    "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
                },
            }

            input_variables = {
                "T_celsius": [10, 20],
                "V_L": [1, 2],
                "n_mol": 1.0,
            }

            results = fz.fzr(
                "input.txt",
                input_variables,
                model,
                calculators="sh://bash PerfectGazPressure.sh",
                results_dir="results",
            )

            assert len(results) == 4, f"Expected 4 results, got {len(results)}"
        finally:
            os.chdir(original_dir)

    def test_fzi_example(self, tmp_path):
        """Run the fzi example from README."""
        input_file = tmp_path / "input.txt"
        input_file.write_text(
            "# input file\n"
            "T_celsius=$T_celsius\n"
            "V_L=$V_L\n"
            "n_mol=$n_mol\n"
        )

        model = {"varprefix": "$", "delim": "{}"}

        variables = fz.fzi(str(input_file), model)

        expected = {"T_celsius": None, "V_L": None, "n_mol": None}
        assert variables == expected, f"Expected {expected}, got {variables}"

    def test_fzc_example(self, tmp_path):
        """Run the fzc example from README."""
        input_file = tmp_path / "input.txt"
        input_file.write_text(
            "# input file\n"
            "T_celsius=$T_celsius\n"
            "V_L=$V_L\n"
            "n_mol=$n_mol\n"
        )

        model = {
            "varprefix": "$",
            "formulaprefix": "@",
            "delim": "{}",
            "commentline": "#",
        }

        input_variables = {"T_celsius": 25, "V_L": 10, "n_mol": 2}

        output_dir = tmp_path / "compiled"
        fz.fzc(
            str(input_file),
            input_variables,
            model,
            output_dir=str(output_dir),
        )

        assert output_dir.exists(), "Output directory not created"
        compiled_files = list(output_dir.rglob("input.txt"))
        assert len(compiled_files) > 0, "No compiled input.txt found"
