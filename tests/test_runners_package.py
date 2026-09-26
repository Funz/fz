"""Layout and interface checks for the fz.runners package."""
import importlib
from pathlib import Path

import pytest

import fz.runners as runners
from fz.runners.base import Calculator

PKG = Path(runners.__file__).parent


def test_no_module_over_1000_lines():
    for py in PKG.glob("*.py"):
        assert len(py.read_text().splitlines()) <= 1000, py.name


def test_backend_modules_exist():
    for name in ("sh", "ssh", "slurm", "funz", "cache"):
        importlib.import_module(f"fz.runners.{name}")


def test_legacy_names_reexported():
    for name in ("run_calculation", "run_local_calculation", "run_ssh_calculation",
                 "run_slurm_calculation", "run_funz_calculation", "resolve_calculators",
                 "resolve_timeout", "classify_error", "parse_ssh_uri", "parse_slurm_uri",
                 "select_calculator_for_case", "run_single_case_calculation",
                 "_calculator_manager", "_validate_calculator_uri"):
        assert hasattr(runners, name), name


def test_calculator_is_abstract():
    with pytest.raises(TypeError):
        Calculator()


def test_submit_poll_fetch_default():
    class Echo(Calculator):
        def run(self, working_dir, calculator_uri, model, **kw):
            return {"status": "done", "uri": calculator_uri}

    calc = Echo()
    handle = calc.submit(Path("."), "sh://x", {})
    assert calc.fetch(handle, timeout=5) == {"status": "done", "uri": "sh://x"}
    assert calc.poll(handle) == "done"


def test_cache_backend_reports_miss():
    from fz.runners.cache import CacheCalculator
    assert CacheCalculator().run(Path("."), "cache://_", {}) == {"status": "cache_miss"}


def test_sh_backend_runs_command(tmp_path):
    from fz.runners.sh import ShCalculator
    (tmp_path / "in.txt").write_text("x")
    res = ShCalculator().run(tmp_path, "sh://echo hi", {}, timeout=30,
                             original_cwd=str(tmp_path), input_files_list=["in.txt"])
    assert res["status"] == "done"


@pytest.mark.parametrize("uri,cls", [
    ("cache://_", "CacheCalculator"),
    ("sh://echo hi", "ShCalculator"),
    ("sh:", "ShCalculator"),
    ("ssh://user@host/cmd", "SshCalculator"),
    ("slurm://:part/script", "SlurmCalculator"),
    ("funz://:5555/Code", "FunzCalculator"),
    ("bash run.sh", "ShCalculator"),
    ("echo a://b", "ShCalculator"),
    ("unknown://x", "ShCalculator"),
])
def test_get_calculator_by_scheme(uri, cls):
    assert type(runners.dispatch.get_calculator(uri)).__name__ == cls


@pytest.mark.parametrize("uri,expected", [
    ("sh://echo hi", "echo hi"),
    ("sh:", ""),
    ("bash run.sh", "bash run.sh"),
    ("unknown://x", "unknown://x"),
])
def test_dispatch_passes_same_command_as_before(monkeypatch, tmp_path, uri, expected):
    seen = {}
    monkeypatch.setattr(
        "fz.runners.sh.run_local_calculation",
        lambda wd, command, *a, **k: seen.setdefault("command", command) and {"status": "done"},
    )
    runners.run_calculation(tmp_path, uri, {})
    assert seen["command"] == expected
