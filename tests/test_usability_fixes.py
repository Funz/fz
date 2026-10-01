"""
Regression tests for usability defects found while reviewing the documentation:

1. timeout=0 / FZ_RUN_TIMEOUT=0 mean "no timeout" (they timed every case out at once);
2. a model without "delim" recognizes both $(x) and ${x} (${x} was silently ignored),
   and the CLI without --model uses the same default;
3. fzl lists calculator aliases by name and checks the commands of their "models" map
   (installed-wrapper aliases {"uri": "sh://", "models": {...}} were reported failed);
4. ".fz/..." paths of a calculator alias are anchored to the .fz/ it was loaded from
   (aliases installed with --global only worked from the home directory);
5. fzr() refuses a results_dir that looks like a calculator URI (4th positional slot);
6. empty .fz/tmp/fz_temp_* directories are removed after a run.

A case whose outputs are all missing deliberately stays "done" (the calculation ran;
see test_examples_advanced.test_non_numeric_variables); the reason is in "error".

Each test runs in a fresh temporary directory (autouse fixture in conftest.py).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import fz
from fz.runners.manager import resolve_timeout
from fz.helpers import _anchor_fz_paths

MODEL = {
    "delim": "{}",
    "output": {"p": "python://grep(r'p = (\\S+)', 'output.txt')"},
}


def _write_case_files():
    Path("input.txt").write_text("x=${x}\n")
    Path("calc.sh").write_text('source "$1"\necho "p = $x" > output.txt\n')


# 1. timeouts ---------------------------------------------------------------

def test_zero_timeout_means_unlimited():
    assert resolve_timeout({}, 0) is None
    assert resolve_timeout({"timeout": 0}) is None
    assert resolve_timeout({"timeout": None}) is None
    assert resolve_timeout({}, 5) == 5


def test_zero_run_timeout_env_means_unlimited(monkeypatch):
    monkeypatch.setenv("FZ_RUN_TIMEOUT", "0")
    fz.reload_config()
    try:
        assert resolve_timeout({}) is None
        assert resolve_timeout({}, scheme="ssh") is None
    finally:
        monkeypatch.delenv("FZ_RUN_TIMEOUT")
        fz.reload_config()


def test_negative_timeout_rejected():
    _write_case_files()
    with pytest.raises(ValueError, match="timeout"):
        fz.fzr("input.txt", {"x": [1]}, MODEL, calculators="sh://bash calc.sh", timeout=-1)


def test_fzr_with_zero_timeout_runs():
    _write_case_files()
    results = fz.fzr("input.txt", {"x": [1, 2]}, MODEL,
                     calculators="sh://bash calc.sh", results_dir="results", timeout=0)
    assert list(results["status"]) == ["done", "done"]
    assert list(results["p"]) == [1, 2]


# 2. default delimiters ------------------------------------------------------

def test_default_delimiters_accept_both_forms():
    Path("t.txt").write_text("a=$(a)\nb=${b}\nc=${c~7}\nd=$(d~2)\ne=$e\nf=@{$a + ${b}}\n")
    found = fz.fzi("t.txt", {})
    assert {"a", "b", "c", "d", "e"} <= set(found)
    assert found["c"] == 7 and found["d"] == 2

    fz.fzc("t.txt", {"a": 1, "b": 2, "e": 5}, {}, "compiled")
    (case_dir,) = [p for p in Path("compiled").iterdir() if p.is_dir()]
    assert (case_dir / "t.txt").read_text() == "a=1\nb=2\nc=7\nd=2\ne=5\nf=3\n"


def test_explicit_delim_still_restricts():
    Path("t.txt").write_text("a=$(a)\nb=${b}\n")
    assert set(fz.fzi("t.txt", {"delim": "{}"})) == {"b"}
    assert set(fz.fzi("t.txt", {"delim": "()"})) == {"a"}
    assert set(fz.fzi("t.txt", {"var_delim": "()"})) == {"a"}


def test_cli_default_matches_python_default():
    Path("t.txt").write_text("a=$(a)\nb=${b}\n")
    for extra in ([], ["--model", '{"output": {}}']):
        out = subprocess.run(
            [sys.executable, "-m", "fz.cli", "input", "t.txt", "--format", "json", *extra],
            capture_output=True, text=True, check=True,
        ).stdout
        assert set(json.loads(out)) == {"a", "b"}, extra


# 3. fzl -----------------------------------------------------------------------

def _install_alias(root: Path, name="pg", script="run.sh"):
    (root / ".fz" / "models").mkdir(parents=True, exist_ok=True)
    (root / ".fz" / "calculators").mkdir(parents=True, exist_ok=True)
    (root / ".fz" / "models" / f"{name}.json").write_text(json.dumps({"id": name, **MODEL}))
    (root / ".fz" / "calculators" / script).write_text('source "$1"\necho "p = $x" > output.txt\n')
    (root / ".fz" / "calculators" / f"localhost_{name}.json").write_text(json.dumps(
        {"uri": "sh://", "models": {name: f"bash .fz/calculators/{script}"}}))


def test_fzl_lists_aliases_by_name_and_checks_model_commands():
    _install_alias(Path.cwd())
    result = fz.fzl(check=True)
    assert result["models"]["pg"]["supported_calculators"] == ["localhost_pg"]
    calc = result["calculators"]["localhost_pg"]
    assert calc["uri"] == "sh://"
    assert calc["supports_models"] == ["pg"]
    assert calc["check_status"] == "passed", calc.get("check_error")


def test_fzl_default_calculator_when_no_alias():
    result = fz.fzl()
    assert list(result["calculators"]) == ["sh://"]


# 4. .fz/ paths anchored to the alias location ---------------------------------

def test_anchor_fz_paths(tmp_path):
    _install_alias(tmp_path)
    alias_file = tmp_path / ".fz" / "calculators" / "localhost_pg.json"
    data = json.loads(alias_file.read_text())
    anchored = _anchor_fz_paths(data, alias_file)
    script = (tmp_path / ".fz" / "calculators" / "run.sh").as_posix()
    assert anchored["models"]["pg"] == f"bash {script}"
    # Missing targets and files outside a .fz/calculators directory are left alone
    data["models"]["pg"] = "bash .fz/calculators/missing.sh"
    assert _anchor_fz_paths(data, alias_file)["models"]["pg"] == "bash .fz/calculators/missing.sh"
    assert _anchor_fz_paths(data, tmp_path / "other.json") == data


def test_alias_found_in_home_runs_from_elsewhere(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    _install_alias(home)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    _write_case_files()
    model = json.loads((home / ".fz" / "models" / "pg.json").read_text())
    results = fz.fzr("input.txt", {"x": [3]}, model, results_dir="results")
    assert list(results["status"]) == ["done"], list(results["error"])
    assert list(results["p"]) == [3]


# 5. results_dir that looks like a URI -----------------------------------------

def test_calculator_passed_positionally_is_rejected():
    _write_case_files()
    with pytest.raises(ValueError, match="calculators="):
        fz.fzr("input.txt", {"x": [1]}, MODEL, "sh://bash calc.sh")
    assert not any(p.name.startswith("sh:") for p in Path.cwd().iterdir())


# Missing outputs are reported in "error" (status stays "done") -------------------

def test_case_without_any_output_reports_missing_output():
    _write_case_files()
    Path("noop.sh").write_text("true\n")
    results = fz.fzr("input.txt", {"x": [1]}, MODEL,
                     calculators="sh://bash noop.sh", results_dir="results")
    assert list(results["status"]) == ["done"]
    assert "Missing output" in results["error"][0]


# 6. temporary directories ---------------------------------------------------------

def test_no_empty_temp_directories_left():
    _write_case_files()
    fz.fzr("input.txt", {"x": [1, 2]}, MODEL, calculators="sh://bash calc.sh", results_dir="results")
    fz.fzc("input.txt", {"x": 1}, MODEL, "compiled")
    tmp = Path(".fz") / "tmp"
    leftovers = [p for p in tmp.iterdir()] if tmp.exists() else []
    assert leftovers == []


# Unexpected exception inside a case ------------------------------------------------

@pytest.mark.parametrize("calculators", [["sh://bash calc.sh"], ["sh://bash calc.sh"] * 2])
def test_case_exception_is_reported_in_error_column(monkeypatch, calculators):
    """An exception raised while running one case gives that case status "error" with
    the message in the "error" column, without aborting the other cases (sequential and
    parallel paths)."""
    import fz.helpers as helpers

    _write_case_files()
    real_run_single_case = helpers.run_single_case

    def flaky(case_info):
        if case_info["var_combo"]["x"] == 2:
            raise RuntimeError("boom")
        return real_run_single_case(case_info)

    monkeypatch.setattr(helpers, "run_single_case", flaky)
    results = fz.fzr("input.txt", {"x": [1, 2]}, MODEL,
                     calculators=calculators, results_dir="results")
    by_x = {row["x"]: row for _, row in results.iterrows()}
    assert by_x[1]["status"] == "done"
    assert by_x[2]["status"] == "error"
    assert "boom" in by_x[2]["error"]
