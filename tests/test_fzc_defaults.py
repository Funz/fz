"""
Regression tests: pre-evaluation of inline variable defaults in formulas.

Bug (fixed)
-----------
Given an input file that declares a variable default AND a formula that uses it::

    x = $(x~3)
    y = @{x * 2}

``fzi`` already pre-evaluated both (``{'x': 3, 'x * 2': 6}``), but ``fzc`` /
``fzr`` only substituted the variable and left the formula uncompiled::

    x = 3
    y = @{x * 2}          # <-- should have been "y = 6"

Cause: ``compile_to_result_directories`` passed only the caller-supplied
``input_variables`` to ``evaluate_formulas`` and never looked at the
``$(var~default)`` defaults embedded in the file.

Fix: the default extraction used by ``fzi`` was factored into
``fz.interpreter.parse_variable_defaults_from_content`` and is now also used
during compilation to seed the substitution/formula context. Explicitly passed
``input_variables`` still take precedence over inline defaults.
"""
import os

import pytest

from fz import fzc, fzi, fzr
from fz.interpreter import parse_variable_defaults_from_content

MODEL = {
    "var_prefix": "$",
    "var_delim": "()",
    "formula_prefix": "@",
    "formula_delim": "{}",
    "commentline": "#",
    "interpreter": "python",
}

# input file used by most tests: one default, one formula that depends on it
CONTENT = "x = $(x~3)\ny = @{x * 2}\n"


def _write(name, content):
    # tests run in a per-test temp cwd (see tests/conftest.py)
    with open(name, "w", newline="\n") as f:
        f.write(content)
    return name


def _fzc_compile(content, input_variables, out="output"):
    _write("in.txt", content)
    fzc("in.txt", input_variables, MODEL, output_dir=out)
    compiled = [
        os.path.join(root, "in.txt")
        for root, _, files in os.walk(out)
        if "in.txt" in files
    ]
    assert len(compiled) == 1, compiled
    with open(compiled[0]) as f:
        return f.read()


# --------------------------------------------------------------------------- #
# reference behaviour: fzi already did this (guards against an fzi regression)
# --------------------------------------------------------------------------- #

def test_fzi_preevaluates_default_and_formula():
    _write("in.txt", CONTENT)
    result = fzi("in.txt", model=MODEL)
    assert result["x"] == 3
    assert result["x * 2"] == 6


# --------------------------------------------------------------------------- #
# fzc
# --------------------------------------------------------------------------- #

def test_fzc_preevaluates_formula_from_inline_default():
    # Regression: previously produced "y = @{x * 2}"
    compiled = _fzc_compile(CONTENT, {})
    assert "x = 3" in compiled
    assert "y = 6" in compiled
    assert "@{" not in compiled


def test_fzc_matches_fzi_preevaluation():
    _write("in.txt", CONTENT)
    pre = fzi("in.txt", model=MODEL)
    compiled = _fzc_compile(CONTENT, {})
    assert f"y = {pre['x * 2']}" in compiled


def test_fzc_explicit_value_overrides_inline_default():
    compiled = _fzc_compile(CONTENT, {"x": 10})
    assert "x = 10" in compiled
    assert "y = 20" in compiled


def test_fzc_formula_left_unevaluated_when_a_needed_var_has_no_default():
    # y has no default and is not provided -> the formula that needs it cannot
    # be evaluated and is left unevaluated (same as fzi returning None); the
    # formula that only needs the defaulted x is still evaluated.
    content = (
        "a = $(x~10)\n"
        "b = $(y)\n"
        "area = @{$x * $y}\n"
        "double = @{$x * 2}\n"
    )
    compiled = _fzc_compile(content, {})
    assert "double = 20" in compiled
    # x still gets substituted from its default, but the formula is not resolved
    assert "@{" in compiled
    assert "$y" in compiled


def test_fzc_default_still_used_when_partial_vars_given():
    content = (
        "a = $(x~10)\n"
        "b = $(y)\n"
        "area = @{$x * $y}\n"
        "double = @{$x * 2}\n"
    )
    compiled = _fzc_compile(content, {"y": 4})
    assert "area = 40" in compiled   # x from default, y provided
    assert "double = 20" in compiled


def test_fzc_float_default_in_formula():
    compiled = _fzc_compile("r = $(r~2.5)\narea = @{3.14 * r * r}\n", {})
    assert "r = 2.5" in compiled
    assert "area = 19.625" in compiled


# --------------------------------------------------------------------------- #
# fzr (goes through the same compile path -> must behave like fzc)
# --------------------------------------------------------------------------- #

def test_fzr_preevaluates_formula_from_inline_default():
    _write("in.txt", CONTENT)
    model = dict(MODEL, output={"y": "sed -n 's/^y = //p' in.txt"})
    df = fzr("in.txt", {}, model, calculators=["sh://echo done"], results_dir="res")

    # formula evaluated from the inline default and parsed back from output
    assert list(df["y"]) == [6]

    # and the compiled input file kept in the results dir shows it too
    with open(os.path.join("res", "in.txt")) as f:
        compiled = f.read()
    assert "x = 3" in compiled
    assert "y = 6" in compiled


def test_fzr_explicit_value_overrides_inline_default():
    _write("in.txt", CONTENT)
    model = dict(MODEL, output={"y": "sed -n 's/^y = //p' in.txt"})
    df = fzr("in.txt", {"x": [4, 7]}, model,
             calculators=["sh://echo done"], results_dir="res")
    assert sorted(df["y"]) == [8, 14]


# --------------------------------------------------------------------------- #
# the shared helper that both paths now use
# --------------------------------------------------------------------------- #

def test_parse_variable_defaults_from_content():
    content = (
        "$(i~42) $(f~3.5) $(s~hello) $(q~\"quoted\") $(sci~1e3) "
        "$(nodefault) $(lst~[0,1]) $(truncated~[0,1) $(withmeta~7;a comment;[0,10])"
    )
    got = parse_variable_defaults_from_content(content, "$", "()")
    assert got == {
        "i": 42,
        "f": 3.5,
        "s": "hello",
        "q": "quoted",
        "sci": 1000.0,
        "lst": [0, 1],       # valid list literal -> kept as-is
        "truncated": None,   # starts with '[' but does not parse -> None
        "withmeta": 7,       # metadata after ';' is ignored
    }
    assert "nodefault" not in got


def test_parse_variable_defaults_empty_without_delim():
    assert parse_variable_defaults_from_content("$x $y", "$", "") == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
