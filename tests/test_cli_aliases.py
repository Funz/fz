"""
Tests for the CLI argument aliases documented in the README:

- positional input/output paths (fzi input.txt ... instead of -i input.txt)
- --variables (= --input_variables), --calculator (= --calculators, repeatable),
  --results (= --results_dir), --output (= --output_dir)
- inline model definition without --model: --varprefix, --formulaprefix,
  --delim, --commentline, --interpreter, --output-cmd NAME=COMMAND
"""
import json
from pathlib import Path

from test_cli_commands import run_fz_cli_function


def _write_file(path, content):
    # Path.write_text(newline=...) needs Python 3.10+; open() works on 3.9
    with Path(path).open("w", newline="\n") as f:
        f.write(content)


def _write_input(content="x=$x\n"):
    _write_file("input.txt", content)


class TestPositionalPaths:
    def test_fzi_positional_input(self):
        _write_input()
        result = run_fz_cli_function("fzi_main", [
            "input.txt", "--model", '{"varprefix": "$"}', "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        assert "x" in json.loads(result.stdout)

    def test_fzo_positional_output(self):
        Path("odir").mkdir()
        _write_file(Path("odir") / "output.txt", "42\n")
        result = run_fz_cli_function("fzo_main", [
            "odir", "--output-cmd", "y=cat output.txt", "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        assert "42" in result.stdout

    def test_positional_and_flag_conflict_is_an_error(self):
        _write_input()
        result = run_fz_cli_function("fzi_main", [
            "input.txt", "--input_path", "other.txt", "--format", "json",
        ])
        assert result.returncode != 0
        assert "twice" in result.stderr

    def test_missing_path_is_an_error(self):
        result = run_fz_cli_function("fzi_main", ["--format", "json"])
        assert result.returncode != 0
        assert "required" in result.stderr.lower()


class TestFlagAliases:
    def test_fzc_variables_and_output_aliases(self):
        _write_input()
        result = run_fz_cli_function("fzc_main", [
            "input.txt", "--model", '{"varprefix": "$"}',
            "--variables", '{"x": 5}', "--output", "compiled",
        ])
        assert result.returncode == 0, result.stderr
        compiled = Path("compiled/x=5/input.txt")
        assert compiled.exists()
        assert "x=5" in compiled.read_text()

    def test_fzr_repeatable_calculator_and_results_alias(self):
        _write_input()
        _write_file("calc.sh", "#!/bin/bash\necho 42 > output.txt\n")
        result = run_fz_cli_function("fzr_main", [
            "input.txt",
            "--model", '{"varprefix": "$", "output": {"y": "cat output.txt"}}',
            "--variables", '{"x": [1, 2]}',
            "--calculator", "cache://_no_such_dir_",
            "--calculator", "sh://bash calc.sh",
            "--results", "myresults",
            "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        records = json.loads(result.stdout)
        assert len(records) == 2
        assert all(r["status"] == "done" for r in records)
        assert Path("myresults").exists()

    def test_calculators_accepts_bare_alias(self):
        """--calculators <alias> resolves .fz/calculators/<alias>.json"""
        _write_input()
        _write_file("calc.sh", "#!/bin/bash\necho 42 > output.txt\n")
        Path(".fz/models").mkdir(parents=True)
        _write_file(".fz/models/pg.json", json.dumps({
            "id": "pg", "varprefix": "$", "output": {"y": "cat output.txt"},
        }))
        Path(".fz/calculators").mkdir(parents=True)
        _write_file(".fz/calculators/loc.json", json.dumps({
            "uri": "sh://", "models": {"pg": "bash calc.sh"},
        }))
        result = run_fz_cli_function("fzr_main", [
            "input.txt", "--model", "pg",
            "--variables", '{"x": [1]}',
            "--calculators", "loc",
            "--results", "res_alias",
            "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        records = json.loads(result.stdout)
        assert records[0]["status"] == "done"
        assert records[0]["y"] == 42

    def test_canonical_flags_still_work(self):
        _write_input()
        result = run_fz_cli_function("fzc_main", [
            "-i", "input.txt", "-m", '{"varprefix": "$"}',
            "-v", '{"x": 9}', "-o", "compiled_canonical",
        ])
        assert result.returncode == 0, result.stderr
        assert Path("compiled_canonical/x=9/input.txt").exists()


class TestSimpleVariablesSyntax:
    """--input_variables also accepts 'a=1,b=[4,5,6],c=[0;1]' besides JSON"""

    def test_fzc_simple_scalar(self):
        _write_input()
        result = run_fz_cli_function("fzc_main", [
            "input.txt", "--model", '{"varprefix": "$"}',
            "--variables", "x=5", "--output", "compiled",
        ])
        assert result.returncode == 0, result.stderr
        assert Path("compiled/x=5/input.txt").exists()

    def test_fzr_simple_grid_and_fixed(self):
        _write_input("a=$a\nb=$b\n")
        _write_file("calc.sh", "#!/bin/bash\necho 42 > output.txt\n")
        result = run_fz_cli_function("fzr_main", [
            "input.txt",
            "--model", '{"varprefix": "$", "output": {"y": "cat output.txt"}}',
            "--variables", "a=1,b=[4,5,6]",
            "--calculators", "sh://bash calc.sh",
            "--results", "results_grid",
            "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        records = json.loads(result.stdout)
        assert len(records) == 3
        assert all(r["a"] == 1 for r in records)
        assert sorted(r["b"] for r in records) == [4, 5, 6]

    def test_semicolon_bracket_becomes_two_element_list(self):
        _write_input("c=$c\n")
        result = run_fz_cli_function("fzc_main", [
            "input.txt", "--model", '{"varprefix": "$"}',
            "--variables", "c=[0;1]", "--output", "compiled_range",
        ])
        assert result.returncode == 0, result.stderr
        # c is a 2-value grid [0, 1] -> one subdirectory per value
        assert Path("compiled_range/c=0/input.txt").exists()
        assert Path("compiled_range/c=1/input.txt").exists()

    def test_invalid_simple_syntax_is_reported(self):
        _write_input()
        result = run_fz_cli_function("fzc_main", [
            "input.txt", "--model", '{"varprefix": "$"}',
            "--variables", "not_an_assignment", "--output", "compiled_bad",
        ])
        assert result.returncode != 0

    def test_fzd_keeps_range_as_string(self):
        """fzd's simplified --input_vars values stay strings (algorithms.py parses them)"""
        from fz.cli import parse_variables
        assert parse_variables("x=[0;1],z=0.5", as_strings=True) == {"x": "[0;1]", "z": "0.5"}


class TestInlineModel:
    def test_fzi_inline_model_without_model_flag(self):
        _write_input()
        result = run_fz_cli_function("fzi_main", [
            "input.txt", "--varprefix", "$", "--delim", "{}", "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        assert "x" in json.loads(result.stdout)

    def test_inline_flags_override_model(self):
        # File uses $x; the model says varprefix %, the inline flag overrides to $
        _write_input()
        result = run_fz_cli_function("fzi_main", [
            "input.txt", "--model", '{"varprefix": "%"}',
            "--varprefix", "$", "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        assert "x" in json.loads(result.stdout)

    def test_output_cmd_merges_into_model(self):
        Path("odir").mkdir()
        _write_file(Path("odir") / "output.txt", "7\n")
        _write_file(Path("odir") / "other.txt", "8\n")
        result = run_fz_cli_function("fzo_main", [
            "odir", "--model", '{"output": {"a": "cat output.txt"}}',
            "--output-cmd", "b=cat other.txt", "--format", "json",
        ])
        assert result.returncode == 0, result.stderr
        record = json.loads(result.stdout)[0]
        assert record["a"] == 7
        assert record["b"] == 8

    def test_malformed_output_cmd_is_an_error(self):
        Path("odir").mkdir()
        result = run_fz_cli_function("fzo_main", [
            "odir", "--output-cmd", "no_equals_sign", "--format", "json",
        ])
        assert result.returncode != 0
        assert "NAME=COMMAND" in result.stderr
