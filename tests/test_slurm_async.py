"""Tests for asynchronous (sbatch) SLURM execution, with SLURM commands mocked."""
import os
import stat
import threading
import time
from pathlib import Path

import pytest

from fz import slurm_async
from fz.runners import run_slurm_calculation


def test_split_resources():
    uri, res = slurm_async.split_slurm_resources("slurm://:cpu/run.sh?cores=4&mem=2G&time=01:00:00")
    assert uri == "slurm://:cpu/run.sh"
    assert res == {"cores": "4", "mem": "2G", "time": "01:00:00"}
    assert slurm_async.split_slurm_resources("slurm://:cpu/run.sh") == ("slurm://:cpu/run.sh", {})


def test_split_resources_rejects_unknown_and_injection():
    with pytest.raises(ValueError):
        slurm_async.split_slurm_resources("slurm://:cpu/run.sh?bogus=1")
    with pytest.raises(ValueError):
        slurm_async.split_slurm_resources("slurm://:cpu/run.sh?mem=1G;rm -rf x")


def test_build_sbatch_command_uses_arg_list():
    cmd = slurm_async.build_sbatch_command("cpu", "run.sh in.txt", Path("/w"), {"cores": "4", "mem": "2G"})
    assert cmd[0] == "sbatch" and "--partition=cpu" in cmd
    assert "--cpus-per-task=4" in cmd and "--mem=2G" in cmd
    assert cmd[-1].startswith("--wrap=")


def test_uri_with_resources_validates():
    from fz.runners import resolve_calculators
    assert resolve_calculators("slurm://:cpu/run.sh?cores=2")


def _fake_slurm(tmp_path, monkeypatch):
    """Install fake sbatch/sacct/scancel that run the job synchronously; count sacct calls."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    counter = tmp_path / "sacct_calls"
    (bindir / "sbatch").write_text(
        "#!/bin/bash\n"
        'for a in "$@"; do case $a in --chdir=*) d=${a#--chdir=};; --wrap=*) w=${a#--wrap=};; esac; done\n'
        'cd "$d" && bash -c "$w" > out.txt 2> err.txt\n'
        f'echo $((RANDOM+1000))\n'
    )
    (bindir / "sacct").write_text(
        "#!/bin/bash\n"
        f'echo x >> {counter}\n'
        'IFS=, read -ra ids <<< "${@: -3:1}"\n'
        'for i in "${ids[@]}"; do echo "$i|COMPLETED|0:0"; done\n'
    )
    (bindir / "scancel").write_text("#!/bin/bash\n")
    for f in bindir.iterdir():
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FZ_SLURM_POLL_INTERVAL", "0.2")
    monkeypatch.setattr(slurm_async, "_monitor", None)
    return counter


def test_sbatch_runs_cases_with_shared_polling(tmp_path, monkeypatch):
    counter = _fake_slurm(tmp_path, monkeypatch)
    monkeypatch.setenv("FZ_SLURM_MODE", "sbatch")
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/bash\necho 42 > result.txt\n")
    model = {"output": {"r": "cat result.txt"}}
    results = {}

    def one(i):
        wd = tmp_path / f"case{i}"
        wd.mkdir()
        results[i] = run_slurm_calculation(wd, f"slurm://:cpu/bash {script}?cores=1", model, 30, ["."])

    threads = [threading.Thread(target=one, args=(i,)) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    for i in range(4):
        assert results[i]["status"] == "done", results[i]
        assert int(results[i]["r"]) == 42
    # 4 cases, far fewer sacct queries than one poll per case per interval
    assert len(counter.read_text().splitlines()) <= 6


def test_sbatch_failure_reports_exit_code(tmp_path, monkeypatch):
    _fake_slurm(tmp_path, monkeypatch)
    monkeypatch.setenv("FZ_SLURM_MODE", "sbatch")
    wd = tmp_path / "c"
    wd.mkdir()
    script = tmp_path / "fail.sh"
    script.write_text("#!/bin/bash\nexit 3\n")
    res = run_slurm_calculation(wd, f"slurm://:cpu/bash {script}", {"output": {}}, 30, ["."])
    assert res["status"] == "failed"
    assert res["exit_code"] == 3


def test_srun_mode_selected_without_sbatch(monkeypatch):
    monkeypatch.setenv("FZ_SLURM_MODE", "auto")
    monkeypatch.setenv("PATH", "/nonexistent")
    assert slurm_async.resolve_mode() == "srun"
