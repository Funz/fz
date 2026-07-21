"""
Tests for vector (array/list-valued) outputs in fzo and fzr.

fz already lets an output entry evaluate to a Python list through several
extraction forms (plain shell echoing a JSON array, python:// expressions
using grep(all=True)/csv_file(column=...)/hdf5_file(dataset), jq:// / yq://
filters selecting an array, and xpath:// expressions matching more than one
node). This suite locks down that vector outputs:

- come back as plain Python lists (not strings, not numpy arrays) from
  fzo(), for every extraction form;
- survive fzr()'s per-case aggregation unchanged, including across several
  cases with vectors of *different* lengths (a very common shape for
  simulation outputs: e.g. a time series that runs for a different number
  of steps per case);
- stay coherent between fzr() and a subsequent fzo() on the same results
  directory (mirrors tests/test_fzo_fzr_coherence.py, but for vectors);
- are distinguished from the legacy single-element-array-to-scalar
  simplification that plain shell (``bash://``) outputs still apply.

Also covers the xpath:// multi-node fix: xmllint concatenates the text of
every matched node with no reliable separator, so a naive implementation
returns one garbled string instead of a list when an expression matches
several nodes.
"""
import json
import os
import shutil
import time

import pandas as pd
import pytest

import fz

requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="jq executable not found on PATH"
)
requires_xmllint = pytest.mark.skipif(
    shutil.which("xmllint") is None, reason="xmllint executable not found on PATH"
)

def _get_value(result, key, index=0):
    """Return result[key] at index, for either a DataFrame or a dict of lists."""
    if isinstance(result, pd.DataFrame):
        return result[key].iloc[index]
    return result[key][index]


def _get_length(result, key):
    return len(result[key])


# ---------------------------------------------------------------------------
# fzo(): vector outputs from a single result directory, one extraction form
# at a time
# ---------------------------------------------------------------------------

def test_fzo_bash_json_array_output_is_a_list():
    """A plain shell output echoing a JSON array comes back as a Python list."""
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/dummy.txt", "w") as f:
        f.write("unused\n")

    model = {
        "output": {"series": "echo '[1, 2, 3, 4, 5]'"},
    }
    result = fz.fzo("case_output", model)
    value = _get_value(result, "series")
    assert isinstance(value, list)
    assert value == [1, 2, 3, 4, 5]


def test_fzo_python_grep_all_output_is_a_list():
    """python://grep(..., all=True) returns every match as a list."""
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/log.txt", "w") as f:
        f.write("step 0: T=90.0\nstep 1: T=55.0\nstep 2: T=40.0\n")

    model = {
        "output": {
            "T_series": "python://grep(r'T=(\\S+)', 'log.txt', all=True)",
        },
    }
    result = fz.fzo("case_output", model)
    value = _get_value(result, "T_series")
    assert isinstance(value, list)
    assert value == pytest.approx([90.0, 55.0, 40.0])


def test_fzo_python_csv_column_output_is_a_list():
    """python://csv_file(path, column=...) returns the column as a plain list."""
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/data.csv", "w") as f:
        f.write("t,T\n0,90\n300,55\n600,40\n")

    model = {
        "output": {"T_series": "python://csv_file('data.csv', column='T')"},
    }
    result = fz.fzo("case_output", model)
    value = _get_value(result, "T_series")
    assert isinstance(value, list)
    assert value == [90, 55, 40]


@requires_jq
def test_fzo_jq_array_output_is_a_list():
    """A jq:// filter selecting an array returns a native Python list."""
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/results.json", "w") as f:
        json.dump({"temperatures": [90.0, 55.0, 40.0]}, f)

    model = {
        "output": {"T_series": "jq://.temperatures results.json"},
    }
    result = fz.fzo("case_output", model)
    value = _get_value(result, "T_series")
    assert isinstance(value, list)
    assert value == pytest.approx([90.0, 55.0, 40.0])


@requires_xmllint
def test_fzo_xpath_multiple_nodes_output_is_a_list():
    """
    Regression test: xpath:// used to concatenate all matched node text
    with no separator, returning a single garbled string instead of a
    vector. It must now return a list, one (cast) element per node.
    """
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/output.xml", "w") as f:
        f.write(
            "<results>"
            "<value>1.5</value><value>2.5</value><value>3.5</value>"
            "</results>"
        )

    model = {
        "output": {"series": "xpath://'//value/text()' output.xml"},
    }
    result = fz.fzo("case_output", model)
    value = _get_value(result, "series")
    assert isinstance(value, list)
    assert value == pytest.approx([1.5, 2.5, 3.5])


@requires_xmllint
def test_fzo_xpath_single_node_output_stays_scalar():
    """A single-node xpath:// match is unaffected: still a plain scalar."""
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/output.xml", "w") as f:
        f.write("<results><pressure>101.325</pressure></results>")

    model = {
        "output": {"pressure": "xpath://'//pressure/text()' output.xml"},
    }
    result = fz.fzo("case_output", model)
    value = _get_value(result, "pressure")
    assert value == pytest.approx(101.325)
    assert not isinstance(value, list)


def test_fzo_bash_single_element_array_is_simplified_to_scalar():
    """
    Documents the existing (legacy) cast_output() behavior for plain shell
    outputs: a single-element JSON array is simplified to its scalar
    element. This is the opposite of the python://, jq:// and xpath://
    behaviors above, which never simplify a genuine vector output down to
    a scalar -- use one of those forms instead of a plain shell command
    when a length-1 result must still be preserved as a vector.
    """
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/dummy.txt", "w") as f:
        f.write("unused\n")

    model = {"output": {"series": "echo '[42]'"}}
    result = fz.fzo("case_output", model)
    value = _get_value(result, "series")
    assert value == 42
    assert not isinstance(value, list)


def test_fzo_python_single_element_list_is_not_simplified():
    """python:// output values are returned as-is: no scalar simplification."""
    os.makedirs("case_output", exist_ok=True)
    with open("case_output/log.txt", "w") as f:
        f.write("T=42.0\n")

    model = {
        "output": {"series": "python://grep(r'T=(\\S+)', 'log.txt', all=True)"},
    }
    result = fz.fzo("case_output", model)
    value = _get_value(result, "series")
    assert isinstance(value, list)
    assert value == pytest.approx([42.0])


# ---------------------------------------------------------------------------
# fzr(): vector outputs aggregated across several cases
# ---------------------------------------------------------------------------

def _write_perfectgaz_style_case_script(name="run_case.sh"):
    """A toy 'simulation' producing a fixed-length time series per case."""
    with open(name, "w", newline="\n") as f:
        f.write("#!/bin/bash\n")
        f.write("source input.txt\n")
        f.write(
            "python3 -c \"\n"
            "import json\n"
            "n = int($n_steps)\n"
            "T0 = float($T0)\n"
            "series = [round(T0 * (0.9 ** i), 3) for i in range(n)]\n"
            "print(json.dumps(series))\n"
            "\" > series.json\n"
        )
    os.chmod(name, 0o755)


def test_fzr_vector_output_single_case():
    """A single fzr() case with a vector output stores the full list."""
    with open("input.txt", "w") as f:
        f.write("n_steps=${n_steps}\nT0=${T0}\n")
    _write_perfectgaz_style_case_script()

    model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"T_series": "python://json_file('series.json')"},
    }
    result = fz.fzr(
        "input.txt",
        {"n_steps": 4, "T0": 100.0},
        model,
        calculators="sh://bash run_case.sh",
        results_dir="vec_results_single",
    )

    value = _get_value(result, "T_series", 0)
    assert isinstance(value, list)
    assert value == pytest.approx([100.0, 90.0, 81.0, 72.9])


def test_fzr_vector_output_multiple_cases_same_length():
    """Vector outputs aggregate correctly, one full list per row."""
    with open("input.txt", "w") as f:
        f.write("n_steps=${n_steps}\nT0=${T0}\n")
    _write_perfectgaz_style_case_script()

    model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"T_series": "python://json_file('series.json')"},
    }
    result = fz.fzr(
        "input.txt",
        {"n_steps": 3, "T0": [100.0, 200.0, 300.0]},
        model,
        calculators="sh://bash run_case.sh",
        results_dir="vec_results_multi",
    )

    assert _get_length(result, "T_series") == 3
    by_t0 = {}
    for i in range(3):
        t0 = _get_value(result, "T0", i)
        series = _get_value(result, "T_series", i)
        assert isinstance(series, list)
        assert len(series) == 3
        by_t0[t0] = series

    assert by_t0[100.0] == pytest.approx([100.0, 90.0, 81.0])
    assert by_t0[200.0] == pytest.approx([200.0, 180.0, 162.0])
    assert by_t0[300.0] == pytest.approx([300.0, 270.0, 243.0])


def test_fzr_vector_output_ragged_lengths_across_cases():
    """
    Cases whose vector outputs differ in length (e.g. an iterative solver
    that converges after a variable number of steps) must not be padded,
    truncated, or otherwise coerced -- each row keeps its own-length list.
    """
    with open("input.txt", "w") as f:
        f.write("n_steps=${n_steps}\nT0=${T0}\n")
    _write_perfectgaz_style_case_script()

    model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"T_series": "python://json_file('series.json')"},
    }
    result = fz.fzr(
        "input.txt",
        pd.DataFrame(
            [
                {"n_steps": 2, "T0": 100.0},
                {"n_steps": 5, "T0": 100.0},
            ]
        ),
        model,
        calculators="sh://bash run_case.sh",
        results_dir="vec_results_ragged",
    )

    assert _get_length(result, "T_series") == 2
    lengths = sorted(len(_get_value(result, "T_series", i)) for i in range(2))
    assert lengths == [2, 5]


def test_fzr_fzo_coherence_for_vector_output():
    """
    fzo() on the results directory produced by fzr() must return the same
    vectors as fzr() itself (mirrors test_fzo_fzr_coherence.py for scalars).
    """
    with open("input.txt", "w") as f:
        f.write("n_steps=${n_steps}\nT0=${T0}\n")
    _write_perfectgaz_style_case_script()

    model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"T_series": "python://json_file('series.json')"},
    }
    fzr_result = fz.fzr(
        "input.txt",
        {"n_steps": 4, "T0": [50.0, 100.0]},
        model,
        calculators="sh://bash run_case.sh",
        results_dir="vec_results_coherence",
    )

    time.sleep(0.2)  # let file writes settle, as in test_fzo_fzr_coherence.py

    fzo_result = fz.fzo("vec_results_coherence/*", model)

    assert _get_length(fzr_result, "T_series") == _get_length(fzo_result, "T_series") == 2

    fzr_by_t0 = {
        _get_value(fzr_result, "T0", i): _get_value(fzr_result, "T_series", i)
        for i in range(2)
    }
    fzo_by_t0 = {
        _get_value(fzo_result, "T0", i): _get_value(fzo_result, "T_series", i)
        for i in range(2)
    }
    assert set(fzr_by_t0) == set(fzo_by_t0)
    for t0 in fzr_by_t0:
        assert fzr_by_t0[t0] == pytest.approx(fzo_by_t0[t0])
