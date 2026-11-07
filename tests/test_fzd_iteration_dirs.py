"""fzd must not leave empty iterNNN_<timestamp> directories (issue #106).

fzd created analysis_dir/iterNNN/ before calling fzr() on it; fzr() renames an
existing results_dir with a timestamp, so every iteration left an empty
iterNNN_<timestamp>/ next to the real iterNNN/.
"""
import sys
from pathlib import Path

import pytest

import fz

REPO = Path(__file__).resolve().parent.parent
RANDOMSAMPLING = str(REPO / "examples" / "algorithms" / "randomsampling.py")
BFGS = str(REPO / "examples" / "algorithms" / "bfgs.py")


@pytest.fixture
def file_case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "input.txt").write_text("x = $x\n")
    (tmp_path / "calc.sh").write_text("cut -d= -f2 input.txt > out.txt\n")
    return {"varprefix": "$", "output": {"y": "cat out.txt"}}


def _iteration_entries(analysis_dir: Path):
    return sorted(p.name for p in analysis_dir.iterdir() if p.name.startswith("iter"))


@pytest.mark.skipif(sys.platform.startswith("win"), reason="sh:// needs bash (MSYS2 on Windows)")
def test_file_model_leaves_no_renamed_iteration_dirs(file_case, tmp_path):
    result = fz.fzd("input.txt", {"x": "[0;1]"}, file_case, output_expression="y",
                    algorithm=BFGS, calculators="sh://bash calc.sh",
                    algorithm_options={"max_iter": 2}, analysis_dir="an")
    assert result["iterations"] >= 2
    entries = _iteration_entries(tmp_path / "an")
    assert entries == [f"iter{i:03d}" for i in range(1, result["iterations"] + 1)], entries
    for name in entries:
        assert any((tmp_path / "an" / name).glob("case_*")), f"{name} has no case directory"


def test_function_model_still_writes_values_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = fz.fzd(None, {"a": "[0;1]"}, lambda a: (a - 0.3) ** 2, output_expression=None,
                    algorithm=RANDOMSAMPLING, algorithm_options={"nvalues": 3},
                    analysis_dir="an")
    entries = _iteration_entries(tmp_path / "an")
    assert entries == [f"iter{i:03d}" for i in range(1, result["iterations"] + 1)], entries
    assert (tmp_path / "an" / "iter001" / "values.csv").exists()
