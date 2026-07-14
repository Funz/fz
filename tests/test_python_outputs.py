"""
Tests for native Python output extraction (fz/outparsers.py).

These tests are fully shell-free: they must pass on any platform without
bash, grep, awk or FZ_SHELL_PATH being available.
"""
import json
from pathlib import Path

import pytest

from fz import fzo
from fz.outparsers import (
    evaluate_python_output,
    is_python_expression,
    make_helpers,
    strip_python_prefix,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def output_dir(tmp_path):
    """A fake case output directory with typical result files."""
    d = tmp_path / "case_output"
    d.mkdir()
    (d / "output.txt").write_text(
        "iteration 1\n"
        "pressure = 101.325 kPa\n"
        "temperature = 293.15\n"
        "pressure = 99.9 kPa\n"
        "done\n"
    )
    (d / "result.json").write_text(json.dumps({"energy": 42.5, "steps": 10}))
    (d / "data.csv").write_text("t,T\n0,90\n300,55\n600,40\n")
    return d


# ---------------------------------------------------------------------------
# Spec detection
# ---------------------------------------------------------------------------

def test_is_python_expression_detection():
    assert is_python_expression("python: grep(r'x=(\\d+)', 'f.txt')")
    assert is_python_expression("  PYTHON: read('f.txt')")  # case/space tolerant
    assert not is_python_expression("grep 'pressure' output.txt | awk '{print $3}'")
    assert not is_python_expression("cat output.txt")
    assert not is_python_expression(42)
    assert not is_python_expression(None)


def test_strip_python_prefix():
    assert strip_python_prefix("python: 1 + 1") == "1 + 1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_helper_read_and_lines(output_dir):
    h = make_helpers(output_dir)
    assert "pressure = 101.325 kPa" in h["read"]("output.txt")
    assert h["lines"]("output.txt")[0] == "iteration 1"
    assert h["line"]("output.txt", -1) == "done"


def test_helper_grep_first_match_with_cast(output_dir):
    h = make_helpers(output_dir)
    value = h["grep"](r"pressure = (\S+)", "output.txt")
    assert value == pytest.approx(101.325)
    assert isinstance(value, float)


def test_helper_grep_all_matches(output_dir):
    h = make_helpers(output_dir)
    values = h["grep"](r"pressure = (\S+)", "output.txt", all=True)
    assert values == [pytest.approx(101.325), pytest.approx(99.9)]


def test_helper_grep_no_match_returns_none(output_dir):
    h = make_helpers(output_dir)
    assert h["grep"](r"velocity = (\S+)", "output.txt") is None


def test_helper_grep_whole_match_without_groups(output_dir):
    h = make_helpers(output_dir)
    assert h["grep"](r"iteration \d+", "output.txt", cast=False) == "iteration 1"


def test_helper_json_file(output_dir):
    h = make_helpers(output_dir)
    assert h["json_file"]("result.json")["energy"] == 42.5


def test_helper_csv_file_column(output_dir):
    h = make_helpers(output_dir)
    assert h["csv_file"]("data.csv", column="T") == [90, 55, 40]


# ---------------------------------------------------------------------------
# Expression / callable evaluation
# ---------------------------------------------------------------------------

def test_evaluate_expression(output_dir):
    value = evaluate_python_output(
        "python: grep(r'temperature = (\\S+)', 'output.txt')", output_dir
    )
    assert value == pytest.approx(293.15)


def test_evaluate_expression_with_computation(output_dir):
    value = evaluate_python_output(
        "python: max(csv_file('data.csv', column='T'))", output_dir
    )
    assert value == 90


def test_evaluate_callable(output_dir):
    value = evaluate_python_output(
        lambda d: json.loads((d / "result.json").read_text())["steps"], output_dir
    )
    assert value == 10


def test_numpy_scalar_normalized(output_dir):
    np = pytest.importorskip("numpy")
    value = evaluate_python_output(
        "python: np.mean(np.array(csv_file('data.csv', column='T')))", output_dir
    )
    assert not isinstance(value, np.generic)
    assert value == pytest.approx((90 + 55 + 40) / 3)


# ---------------------------------------------------------------------------
# Integration with fzo (no shell involved)
# ---------------------------------------------------------------------------

def test_fzo_with_python_outputs(output_dir):
    model = {
        "output": {
            "pressure": "python: grep(r'pressure = (\\S+)', 'output.txt')",
            "energy": "python: json_file('result.json')['energy']",
            "T_final": lambda d: float((d / "data.csv").read_text().splitlines()[-1].split(",")[1]),
        }
    }
    result = fzo(str(output_dir), model)
    row = result.iloc[0]
    assert row["pressure"] == pytest.approx(101.325)
    assert row["energy"] == pytest.approx(42.5)
    assert row["T_final"] == pytest.approx(40.0)
    assert "_output_error" not in result.columns


def test_fzo_python_output_error_is_reported(output_dir):
    model = {"output": {"missing": "python: read('does_not_exist.txt')"}}
    result = fzo(str(output_dir), model)
    row = result.iloc[0]
    assert row["missing"] is None or (row["missing"] != row["missing"])  # None/NaN
    assert "_output_error" in result.columns
    assert "missing" in str(row["_output_error"])
