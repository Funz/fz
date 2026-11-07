"""A failed '#require:' auto-install reports pip's output (issue #110).

fz ran pip with subprocess.check_call(..., stderr=PIPE), which never reads the
pipe: the RuntimeError always ended with an empty "Error:".
"""
import subprocess

import pytest

from fz import algorithms

ALGO = """#title: needs a missing package
#require: fz_surely_missing_pkg_110

class A:
    def __init__(self, **options):
        pass
    def get_initial_design(self, input_vars, output_vars):
        return []
    def get_next_design(self, X, Y):
        return []
    def get_analysis(self, X, Y):
        return {"text": "", "data": {}}
"""


@pytest.fixture
def algo_file(tmp_path):
    p = tmp_path / "needs_missing.py"
    p.write_text(ALGO)
    return p


def _fake_pip(returncode, stdout="", stderr=""):
    def run(cmd, **kwargs):
        assert cmd[1:4] == ["-m", "pip", "install"], cmd
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)
    return run


def test_pip_stderr_is_reported(algo_file, monkeypatch):
    monkeypatch.setattr(algorithms.subprocess, "run",
                        _fake_pip(1, stderr="ERROR: No matching distribution found for fz_surely_missing_pkg_110"))
    with pytest.raises(RuntimeError) as exc:
        algorithms.load_algorithm(str(algo_file))
    msg = str(exc.value)
    assert "Failed to install required package 'fz_surely_missing_pkg_110'" in msg
    assert "No matching distribution found" in msg


def test_pip_stdout_used_when_stderr_empty(algo_file, monkeypatch):
    monkeypatch.setattr(algorithms.subprocess, "run",
                        _fake_pip(1, stdout="error: externally-managed-environment"))
    with pytest.raises(RuntimeError, match="externally-managed-environment"):
        algorithms.load_algorithm(str(algo_file))


def test_silent_pip_failure_states_exit_status(algo_file, monkeypatch):
    monkeypatch.setattr(algorithms.subprocess, "run", _fake_pip(2))
    with pytest.raises(RuntimeError, match="pip exited with status 2 and printed nothing"):
        algorithms.load_algorithm(str(algo_file))
