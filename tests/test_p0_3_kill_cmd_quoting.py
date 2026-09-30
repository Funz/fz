"""P0-3 gap: the interrupt-time remote kill command must not interpolate
URI/command text as shell syntax (pgrep pattern is a single literal argument)."""
import shlex

import pytest

from fz.runners.ssh import build_kill_cmd

PAYLOADS = ["gpu", "x';touch PWNED;'", "a b", "$(touch PWNED)", "`touch PWNED`", "srun.*p;rm -rf ~"]


@pytest.mark.parametrize("pattern", PAYLOADS)
def test_pattern_is_one_literal_pgrep_argument(pattern):
    cmd = build_kill_cmd(pattern)
    assert cmd.startswith("pkill -P $(pgrep -f ")
    inner = cmd[len("pkill -P $(pgrep -f "):-1]   # text between "pgrep -f " and ")"
    assert shlex.split(inner) == [pattern]
    assert cmd.endswith(")")


def test_slurm_and_ssh_use_the_helper():
    import inspect
    from fz.runners import ssh, slurm
    assert "build_kill_cmd(" in inspect.getsource(ssh)
    assert "build_kill_cmd(" in inspect.getsource(slurm)
    for mod in (ssh, slurm):
        assert "pgrep -f '" not in inspect.getsource(mod)


# ---------------------------------------------------------------------------
# Behavioural tests: drive the real interrupt path with a mocked SSH client,
# capture the remote kill command, and execute it in a real bash (with fake
# pgrep/pkill) to prove a hostile partition/command cannot inject anything.
# ---------------------------------------------------------------------------
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

HOSTILE = "x';touch PWNED;'"


class _Channel:
    def __init__(self):
        self.sent = []

    def exit_status_ready(self):
        return False

    def send(self, data):
        self.sent.append(data)

    def close(self):
        pass

    def recv_exit_status(self):
        return -1


class _Stream:
    def __init__(self, channel):
        self.channel = channel

    def read(self):
        return b""


class _FakeSSH:
    def __init__(self):
        self.commands = []
        self.channel = _Channel()

    def exec_command(self, cmd, timeout=None):
        self.commands.append(cmd)
        return None, _Stream(self.channel), _Stream(self.channel)


def _interrupt_after_start(monkeypatch):
    """is_interrupted(): False for the pre-start check, True afterwards."""
    import fz.core
    calls = {"n": 0}

    def fake():
        calls["n"] += 1
        return calls["n"] > 1

    monkeypatch.setattr(fz.core, "is_interrupted", fake)
    monkeypatch.setattr("time.sleep", lambda s: None)


def _run_kill_in_bash(kill_cmd: str):
    """Execute kill_cmd with fake pgrep/pkill; return (argv seen by pgrep, PWNED exists)."""
    bindir = Path("fakebin")
    bindir.mkdir(exist_ok=True)
    (bindir / "pgrep").write_text('#!/bin/bash\nprintf "%s\\n" "$@" > pgrep_args.txt\necho 1\n')
    (bindir / "pkill").write_text("#!/bin/bash\nexit 0\n")
    for f in bindir.iterdir():
        f.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir.resolve()}{os.pathsep}{os.environ['PATH']}")
    subprocess.run(["bash", "-c", kill_cmd], env=env, check=False, cwd=Path.cwd())
    args = Path("pgrep_args.txt").read_text().splitlines()
    return args, Path("PWNED").exists()


_linux_bash = pytest.mark.skipif(platform.system() == "Windows", reason="fake pgrep/pkill need a POSIX PATH")


@_linux_bash
def test_ssh_interrupt_kill_command_is_injection_safe(monkeypatch):
    from fz.runners.ssh import _execute_remote_command
    _interrupt_after_start(monkeypatch)
    client = _FakeSSH()
    hostile_command = f"bash {HOSTILE}run.sh"  # first 50 chars reach pgrep
    result = _execute_remote_command(
        client, hostile_command, "/tmp/remote", Path("."), 60,
        start_time=datetime.now(), env_info={}, input_files_list=["input.txt"],
    )
    assert result["status"] == "interrupted"
    assert "\x03" in client.channel.sent
    kills = [c for c in client.commands if c.startswith("pkill")]
    assert len(kills) == 1
    args, pwned = _run_kill_in_bash(kills[0])
    assert not pwned, "remote kill command executed injected shell code"
    assert args == ["-f", hostile_command[:50]]


@_linux_bash
def test_slurm_interrupt_kill_command_is_injection_safe(monkeypatch):
    from fz.runners.slurm import _execute_remote_slurm_command
    _interrupt_after_start(monkeypatch)
    client = _FakeSSH()
    result = _execute_remote_slurm_command(
        client, HOSTILE, "bash run.sh", "/tmp/remote", Path("."), 60,
        start_time=datetime.now(), env_info={}, input_files_list=["input.txt"],
    )
    assert result["status"] == "interrupted"
    kills = [c for c in client.commands if c.startswith("pkill")]
    assert len(kills) == 1
    args, pwned = _run_kill_in_bash(kills[0])
    assert not pwned, "remote kill command executed injected shell code"
    assert args == ["-f", f"srun.*{HOSTILE}"]
