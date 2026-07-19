"""
Tests for native output extraction (fz/outparsers.py): python://, jq://,
yq://, xpath:// and the implicit-default / explicit bash:// shell form.

The python://, jq://, yq:// and xpath:// tests are fully shell-free: they
must pass on any platform without bash, grep, awk or FZ_SHELL_PATH being
available (the jq/yq/xpath tests additionally require their respective
executable and are skipped otherwise).
"""
import json
import platform
import shutil
from pathlib import Path

import pytest

from fz import fzo
from fz.outparsers import (
    evaluate_python_output,
    evaluate_jq_output,
    evaluate_yq_output,
    evaluate_xpath_output,
    is_python_expression,
    is_jq_expression,
    is_yq_expression,
    is_xpath_expression,
    is_bash_expression,
    strip_bash_prefix,
    make_helpers,
    strip_python_prefix,
)

requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="jq executable not found on PATH"
)
requires_yq = pytest.mark.skipif(
    shutil.which("yq") is None, reason="yq executable not found on PATH"
)
requires_xmllint = pytest.mark.skipif(
    shutil.which("xmllint") is None, reason="xmllint executable not found on PATH"
)


def _bash_available() -> bool:
    if platform.system() != "Windows":
        # grep/head/etc. are assumed present on Unix-like CI runners
        return True
    from fz.shell import get_windows_bash_executable
    return get_windows_bash_executable() is not None


# Guards the one test below that exercises a real "bash://" (shell) output
# end-to-end. This file is otherwise deliberately shell-free (see the
# shell-free-outputs.yml CI workflow, which runs it without bash on
# Windows) — bash:// itself is not shell-free by design, so that single
# test is skipped rather than making the whole file require bash.
requires_bash = pytest.mark.skipif(
    not _bash_available(), reason="bash not available on this platform"
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
    (d / "config.yaml").write_text(
        "metadata:\n"
        "  version: 3\n"
        "results:\n"
        "  pressure: 101.325\n"
    )
    (d / "output.xml").write_text(
        "<results>"
        "<pressure>101.325</pressure>"
        "<label>converged</label>"
        "</results>"
    )
    return d


# ---------------------------------------------------------------------------
# Spec detection
# ---------------------------------------------------------------------------

def test_is_python_expression_detection():
    assert is_python_expression("python://grep(r'x=(\\d+)', 'f.txt')")
    assert is_python_expression("  PYTHON://read('f.txt')")  # case/space tolerant
    assert not is_python_expression("grep 'pressure' output.txt | awk '{print $3}'")
    assert not is_python_expression("cat output.txt")
    assert not is_python_expression(42)
    assert not is_python_expression(None)


def test_strip_python_prefix():
    assert strip_python_prefix("python://1 + 1") == "1 + 1"


def test_is_jq_expression_detection():
    assert is_jq_expression("jq://.energy result.json")
    assert is_jq_expression("  JQ://.energy result.json")  # case/space tolerant
    assert not is_jq_expression("python://json_file('result.json')")
    assert not is_jq_expression("grep 'pressure' output.txt")
    assert not is_jq_expression(42)


def test_is_yq_expression_detection():
    assert is_yq_expression("yq://.metadata.version config.yaml")
    assert is_yq_expression("  YQ://.a result.json")  # case/space tolerant
    assert not is_yq_expression("jq://.energy result.json")
    assert not is_yq_expression("grep 'pressure' output.txt")
    assert not is_yq_expression(42)


def test_is_xpath_expression_detection():
    assert is_xpath_expression("xpath://'//pressure/text()' out.xml")
    assert is_xpath_expression("  XPATH://'//a' out.xml")  # case/space tolerant
    assert not is_xpath_expression("yq://.a config.yaml")
    assert not is_xpath_expression("grep 'pressure' output.txt")
    assert not is_xpath_expression(42)


def test_is_bash_expression_detection():
    # implicit default: no recognized prefix -> bash
    assert is_bash_expression("grep 'pressure' output.txt | awk '{print $3}'")
    # explicit bash:// prefix
    assert is_bash_expression("bash://cat output.txt")
    assert is_bash_expression("BASH://cat output.txt")
    # python://, jq://, yq:// and xpath:// are not bash expressions
    assert not is_bash_expression("python://read('output.txt')")
    assert not is_bash_expression("jq://.energy result.json")
    assert not is_bash_expression("yq://.a config.yaml")
    assert not is_bash_expression("xpath://'//a' out.xml")
    assert not is_bash_expression(42)
    assert not is_bash_expression(None)


def test_strip_bash_prefix():
    assert strip_bash_prefix("bash://cat output.txt") == "cat output.txt"
    # no prefix -> returned unchanged (implicit default)
    assert strip_bash_prefix("cat output.txt") == "cat output.txt"


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


def test_helper_hdf5_file(output_dir):
    h5py = pytest.importorskip("h5py")
    np = pytest.importorskip("numpy")
    with h5py.File(output_dir / "res.h5", "w") as f:
        f["energy"] = 42.5
        f["results/T"] = np.array([90.0, 55.0, 40.0])
        f["label"] = b"converged"

    h = make_helpers(output_dir)
    # top-level keys when no dataset given
    assert sorted(h["hdf5_file"]("res.h5")) == ["energy", "label", "results"]
    # scalar dataset -> native float
    energy = h["hdf5_file"]("res.h5", "energy")
    assert energy == pytest.approx(42.5) and isinstance(energy, float)
    # array dataset (nested path) -> plain list
    assert h["hdf5_file"]("res.h5", "results/T") == [90.0, 55.0, 40.0]
    # bytes -> str
    assert h["hdf5_file"]("res.h5", "label") == "converged"


def test_evaluate_expression_with_hdf5(output_dir):
    h5py = pytest.importorskip("h5py")
    with h5py.File(output_dir / "res.h5", "w") as f:
        f["results/T"] = [90.0, 55.0, 40.0]
    value = evaluate_python_output(
        "python://min(hdf5_file('res.h5', 'results/T'))", output_dir
    )
    assert value == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# jq:// evaluation (requires the jq executable)
# ---------------------------------------------------------------------------

@requires_jq
def test_evaluate_jq_scalar(output_dir):
    value = evaluate_jq_output("jq://.energy result.json", output_dir)
    assert value == pytest.approx(42.5)


@requires_jq
def test_evaluate_jq_prefix_detection_and_stripping(output_dir):
    # bare spec (prefix already stripped) also works
    value = evaluate_jq_output(".steps result.json", output_dir)
    assert value == 10


@requires_jq
def test_evaluate_jq_quoted_filter(output_dir):
    (output_dir / "result.json").write_text(
        json.dumps({"a": {"b": [10, 20, 30]}})
    )
    value = evaluate_jq_output("jq://'.a.b[1]' result.json", output_dir)
    assert value == 20


@requires_jq
def test_jq_missing_filter_or_file_raises(output_dir):
    with pytest.raises(ValueError):
        evaluate_jq_output("jq://.energy", output_dir)


# ---------------------------------------------------------------------------
# yq:// evaluation (requires the mikefarah/yq executable)
# ---------------------------------------------------------------------------

@requires_yq
def test_evaluate_yq_scalar(output_dir):
    value = evaluate_yq_output("yq://.metadata.version config.yaml", output_dir)
    assert value == 3


@requires_yq
def test_evaluate_yq_prefix_detection_and_stripping(output_dir):
    # bare spec (prefix already stripped) also works
    value = evaluate_yq_output(".results.pressure config.yaml", output_dir)
    assert value == pytest.approx(101.325)


@requires_yq
def test_yq_missing_filter_or_file_raises(output_dir):
    with pytest.raises(ValueError):
        evaluate_yq_output("yq://.a", output_dir)


# ---------------------------------------------------------------------------
# xpath:// evaluation (requires the xmllint executable)
# ---------------------------------------------------------------------------

@requires_xmllint
def test_evaluate_xpath_numeric(output_dir):
    value = evaluate_xpath_output(
        "xpath://'//pressure/text()' output.xml", output_dir
    )
    assert value == pytest.approx(101.325)


@requires_xmllint
def test_evaluate_xpath_string(output_dir):
    value = evaluate_xpath_output(
        "xpath://'//label/text()' output.xml", output_dir
    )
    assert value == "converged"


@requires_xmllint
def test_xpath_missing_expression_or_file_raises(output_dir):
    with pytest.raises(ValueError):
        evaluate_xpath_output("xpath://'//pressure/text()'", output_dir)


# ---------------------------------------------------------------------------
# Expression / callable evaluation
# ---------------------------------------------------------------------------

def test_evaluate_expression(output_dir):
    value = evaluate_python_output(
        "python://grep(r'temperature = (\\S+)', 'output.txt')", output_dir
    )
    assert value == pytest.approx(293.15)


def test_evaluate_expression_with_computation(output_dir):
    value = evaluate_python_output(
        "python://max(csv_file('data.csv', column='T'))", output_dir
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
        "python://np.mean(np.array(csv_file('data.csv', column='T')))", output_dir
    )
    assert not isinstance(value, np.generic)
    assert value == pytest.approx((90 + 55 + 40) / 3)


# ---------------------------------------------------------------------------
# Integration with fzo (no shell involved)
# ---------------------------------------------------------------------------

def test_fzo_with_python_outputs(output_dir):
    model = {
        "output": {
            "pressure": "python://grep(r'pressure = (\\S+)', 'output.txt')",
            "energy": "python://json_file('result.json')['energy']",
            "T_final": lambda d: float((d / "data.csv").read_text().splitlines()[-1].split(",")[1]),
        }
    }
    result = fzo(str(output_dir), model)
    row = result.iloc[0]
    assert row["pressure"] == pytest.approx(101.325)
    assert row["energy"] == pytest.approx(42.5)
    assert row["T_final"] == pytest.approx(40.0)
    assert "_output_error" not in result.columns


@requires_jq
@requires_bash
def test_fzo_with_mixed_python_jq_bash_outputs(output_dir):
    model = {
        "output": {
            "pressure": "python://grep(r'pressure = (\\S+)', 'output.txt')",
            "energy": "jq://.energy result.json",
            "steps": "bash://grep -o steps result.json | head -1",
        }
    }
    result = fzo(str(output_dir), model)
    row = result.iloc[0]
    assert row["pressure"] == pytest.approx(101.325)
    assert row["energy"] == pytest.approx(42.5)
    assert row["steps"] == "steps"


def test_fzo_python_output_error_is_reported(output_dir):
    model = {"output": {"missing": "python://read('does_not_exist.txt')"}}
    result = fzo(str(output_dir), model)
    row = result.iloc[0]
    assert row["missing"] is None or (row["missing"] != row["missing"])  # None/NaN
    assert "_output_error" in result.columns
    assert "missing" in str(row["_output_error"])


# ---------------------------------------------------------------------------
# Windows-without-bash behavior (simulated on any platform)
# ---------------------------------------------------------------------------

def _simulate_windows_without_bash(monkeypatch):
    import platform
    import fz.shell
    import fz.core
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(fz.shell, "get_windows_bash_executable", lambda: None)
    monkeypatch.setattr(fz.core, "platform", platform)


def test_check_bash_non_strict_does_not_raise(monkeypatch):
    from fz.core import check_bash_availability_on_windows
    _simulate_windows_without_bash(monkeypatch)
    # strict (default) raises with installation instructions
    with pytest.raises(RuntimeError, match="bash is not available"):
        check_bash_availability_on_windows()
    # non-strict (import-time behavior) only warns
    check_bash_availability_on_windows(strict=False)


def test_fzo_python_only_model_works_without_bash(output_dir, monkeypatch):
    _simulate_windows_without_bash(monkeypatch)
    model = {"output": {"energy": "python://json_file('result.json')['energy']"}}
    result = fzo(str(output_dir), model)
    assert result.iloc[0]["energy"] == pytest.approx(42.5)


def test_fzo_shell_model_raises_helpfully_without_bash(output_dir, monkeypatch):
    _simulate_windows_without_bash(monkeypatch)
    model = {"output": {"anything": "cat output.txt"}}
    with pytest.raises(RuntimeError, match="bash is not available"):
        fzo(str(output_dir), model)
