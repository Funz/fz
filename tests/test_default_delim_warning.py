"""
Warning for models without "delim" whose templates contain ${...} text (issue #101).

A model with neither "delim" nor "var_delim" reads both $(x) and ${x} as variables
(fz.interpreter.DEFAULT_VAR_DELIM), so shell text such as ${HOME} next to $(x)
variables is silently listed as a variable. fzi() now warns about it (stderr, once
per input and set of names), and the "input_variables is required" error of
fzc()/fzr() explains ${...}-only names.
"""
import json
import os
import subprocess
import sys

import pytest

import fz
from fz import interpreter
from fz.logging import get_log_level, set_log_level

MODEL = {"output": {"o": "echo 1"}}


@pytest.fixture(autouse=True)
def _warnings_visible():
    old = get_log_level()
    set_log_level("WARNING")  # log_warning() is a no-op below WARNING (default: ERROR)
    interpreter._default_delim_warned.clear()
    yield
    set_log_level(old)
    interpreter._default_delim_warned.clear()


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_mixed_forms_warn_once(tmp_path, capsys):
    inp = _write(tmp_path, "in.sh", "x=$(x)\necho ${HOME}\n")
    assert fz.fzi(str(inp), MODEL) == {"HOME": None, "x": None}  # behavior unchanged
    err = capsys.readouterr().err
    assert "${HOME}" in err and 'set "delim": "()"' in err
    fz.fzi(str(inp), MODEL)
    assert "${HOME}" not in capsys.readouterr().err  # once per input and set of names


def test_results_unchanged_with_warning(tmp_path, capsys):
    inp = _write(tmp_path, "in.sh", "x=$(x)\necho ${HOME}\n")
    out = tmp_path / "c"
    fz.fzc(str(inp), {"x": 1}, MODEL, output_dir=str(out))
    compiled = next(out.rglob("in.sh")).read_text()
    assert compiled == "x=1\necho ${HOME}\n"
    assert "${HOME}" in capsys.readouterr().err


@pytest.mark.parametrize("model", [
    dict(MODEL, delim="()"),
    dict(MODEL, delim="{}"),
    dict(MODEL, var_delim="(){}"),
])
def test_explicit_delim_never_warns(tmp_path, capsys, model):
    inp = _write(tmp_path, "in.sh", "x=$(x)\necho ${HOME}\n")
    fz.fzi(str(inp), model)
    assert "delim" not in capsys.readouterr().err


def test_brace_only_template_does_not_warn(tmp_path, capsys):
    """${x} used on purpose (no $(...) at all) is the CLI's 1.2 convention: no warning."""
    inp = _write(tmp_path, "in.txt", "a=${a}\nb=${b}\n")
    assert set(fz.fzi(str(inp), MODEL)) == {"a", "b"}
    assert "delim" not in capsys.readouterr().err


def test_same_name_in_both_forms_does_not_warn(tmp_path, capsys):
    inp = _write(tmp_path, "in.txt", "a=$(a)\nagain=${a}\n")
    fz.fzi(str(inp), MODEL)
    assert "delim" not in capsys.readouterr().err


def test_required_error_explains_brace_only_names(tmp_path):
    inp = _write(tmp_path, "only.sh", "echo ${HOME}\n")
    with pytest.raises(ValueError) as exc:
        fz.fzr(str(inp), None, MODEL, calculators="sh://bash only.sh",
               results_dir=str(tmp_path / "r"))
    msg = str(exc.value)
    assert "input_variables is required" in msg
    assert '${HOME} counted as variable(s) because the model sets no "delim"' in msg


def test_required_error_without_hint_when_delim_set(tmp_path):
    inp = _write(tmp_path, "in.txt", "a=${a}\n")
    with pytest.raises(ValueError) as exc:
        fz.fzc(str(inp), None, dict(MODEL, delim="{}"), output_dir=str(tmp_path / "c"))
    assert "sets no" not in str(exc.value)


def test_cli_stdout_stays_json(tmp_path):
    inp = _write(tmp_path, "in.sh", "x=$(x)\necho ${HOME}\n")
    # The warning contains a non-ASCII emoji: decode as UTF-8 explicitly (the
    # Windows default, cp1252, cannot decode it) and make the child write UTF-8
    proc = subprocess.run(
        [sys.executable, "-m", "fz.cli", "input", str(inp), "--format", "json"],
        capture_output=True, encoding="utf-8", errors="replace",
        env={**os.environ, "FZ_LOG_LEVEL": "WARNING", "PYTHONIOENCODING": "utf-8"},
    )
    if proc.returncode != 0 and "No module named" in proc.stderr:
        pytest.skip("fz.cli not runnable as a module")
    assert json.loads(proc.stdout) == {"HOME": None, "x": None}
    assert "${HOME}" in proc.stderr
