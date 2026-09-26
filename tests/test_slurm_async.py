"""Tests for slurm-array:// (sbatch job arrays), with SLURM commands mocked."""
import os
import stat
import threading
from pathlib import Path

import pytest

from fz import slurm_async
from fz.runners import run_slurm_calculation, resolve_calculators, run_calculation


posix_only = pytest.mark.skipif(os.name == "nt", reason="fake sbatch/sacct are bash scripts")


def test_split_resources():
    uri, res = slurm_async.split_slurm_resources("slurm-array://:cpu/run.sh?cores=4&mem=2G&maxrunning=8")
    assert uri == "slurm-array://:cpu/run.sh"
    assert res == {"cores": "4", "mem": "2G", "maxrunning": "8"}
    assert slurm_async.split_slurm_resources("slurm://:cpu/run.sh") == ("slurm://:cpu/run.sh", {})


def test_split_resources_rejects_unknown_and_injection():
    with pytest.raises(ValueError):
        slurm_async.split_slurm_resources("slurm://:cpu/run.sh?bogus=1")
    with pytest.raises(ValueError):
        slurm_async.split_slurm_resources("slurm://:cpu/run.sh?mem=1G;rm -rf x")


def test_build_array_command_uses_arg_list():
    cmd = slurm_async.build_array_command(
        "cpu", "run.sh", "in.txt", Path("/w/.m"), 5, {"cores": "4", "mem": "2G", "maxrunning": "2"})
    assert cmd[0] == "sbatch" and "--partition=cpu" in cmd
    assert "--array=0-4%2" in cmd
    assert "--cpus-per-task=4" in cmd and "--mem=2G" in cmd
    assert "maxrunning" not in " ".join(cmd)
    assert "SLURM_ARRAY_TASK_ID" in cmd[-1]


def test_uri_validation_and_removed_env_var():
    assert resolve_calculators("slurm-array://:cpu/run.sh?cores=2")
    assert resolve_calculators("slurm://:cpu/run.sh?cores=2")
    assert not hasattr(slurm_async, "resolve_mode")
    assert slurm_async.srun_options({"cores": "2", "maxrunning": "3"}) == "--cpus-per-task=2"


def test_remote_array_rejected(tmp_path):
    res = run_slurm_calculation(tmp_path, "slurm-array://u@host:cpu/run.sh", {"output": {}}, 5, ["."], array=True)
    assert res["status"] == "error" and "local SLURM only" in res["error"]


def _fake_slurm(tmp_path, monkeypatch):
    """Fake sbatch/sacct/scancel: sbatch runs every array task synchronously."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = tmp_path / "sbatch_calls"
    (bindir / "sbatch").write_text(
        "#!/bin/bash\n"
        'for a in "$@"; do case $a in --chdir=*) d=${a#--chdir=};; --wrap=*) w=${a#--wrap=};;'
        ' --array=*) r=${a#--array=}; r=${r%%%*}; n=${r#0-};; esac; done\n'
        f'echo "$n" >> {calls}\n'
        'cd "$d"; for i in $(seq 0 $n); do SLURM_ARRAY_TASK_ID=$i bash -c "$w"; done\n'
        f'echo "$n" > {tmp_path}/last_n\n'
        'echo 4242\n'
    )
    (bindir / "sacct").write_text(
        "#!/bin/bash\n"
        f'n=$(cat {tmp_path}/last_n)\n'
        'for i in $(seq 0 $n); do echo "4242_$i|COMPLETED|0:0"; done\n'
    )
    (bindir / "scancel").write_text("#!/bin/bash\n")
    for f in bindir.iterdir():
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FZ_SLURM_POLL_INTERVAL", "0.2")
    monkeypatch.setenv("FZ_SLURM_ARRAY_WINDOW", "0.5")
    monkeypatch.setattr(slurm_async, "_monitor", None)
    monkeypatch.setattr(slurm_async, "_batcher", None)
    return calls


@posix_only
def test_cases_are_batched_into_one_array(tmp_path, monkeypatch):
    calls = _fake_slurm(tmp_path, monkeypatch)
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/bash\npwd | xargs basename > result.txt\n")
    model = {"output": {"r": "cat result.txt"}}
    results = {}

    def one(i):
        wd = tmp_path / f"case{i}"
        wd.mkdir()
        results[i] = run_slurm_calculation(
            wd, f"slurm-array://:cpu/bash {script}?cores=1", model, 30, ["."], array=True)

    threads = [threading.Thread(target=one, args=(i,)) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    for i in range(4):
        assert results[i]["status"] == "done", results[i]
        assert results[i]["r"] == f"case{i}"  # each task ran in its own case dir
    assert calls.read_text().split() == ["3"]  # ONE sbatch call, array 0-3


@posix_only
def test_array_failure_reports_exit_code(tmp_path, monkeypatch):
    _fake_slurm(tmp_path, monkeypatch)
    wd = tmp_path / "c"
    wd.mkdir()
    script = tmp_path / "fail.sh"
    script.write_text("#!/bin/bash\nexit 3\n")
    res = run_slurm_calculation(wd, f"slurm-array://:cpu/bash {script}", {"output": {}}, 30, ["."], array=True)
    assert res["status"] == "failed" and res["exit_code"] == 3


@posix_only
def test_run_calculation_dispatches_slurm_array(tmp_path, monkeypatch):
    _fake_slurm(tmp_path, monkeypatch)
    wd = tmp_path / "d"
    wd.mkdir()
    script = tmp_path / "ok.sh"
    script.write_text("#!/bin/bash\necho 7 > result.txt\n")
    res = run_calculation(wd, f"slurm-array://:cpu/bash {script}", {"output": {"r": "cat result.txt"}}, 30)
    assert res["status"] == "done" and int(res["r"]) == 7


@posix_only
def test_fzr_single_array_calculator_batches_all_cases(tmp_path, monkeypatch):
    """One slurm-array:// calculator must run N cases in ONE array (no exclusive lock)."""
    import fz
    calls = _fake_slurm(tmp_path, monkeypatch)
    inp = tmp_path / "input.txt"
    inp.write_text("x=$x\n")
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/bash\nsed 's/x=//' input.txt > out_x.txt\n")
    model = {"varprefix": "$", "output": {"y": "cat out_x.txt"}}
    df = fz.fzr(str(inp), {"x": [1, 2, 3, 4, 5]}, model,
                calculators=f"slurm-array://:cpu/bash {script}",
                results_dir=str(tmp_path / "res"))
    assert [int(v) for v in df["y"]] == [1, 2, 3, 4, 5]
    assert calls.read_text().split() == ["4"]
