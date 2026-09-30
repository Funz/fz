"""version_cmd over ssh://: exit status handling (paramiko client mocked).

Covers the ssh:// branch of fz.runners.resolve._run_version_cmd_ssh without a
real SSH server: a non-zero exit must not yield the error text as code_id.
"""
import pytest

paramiko = pytest.importorskip("paramiko")

from fz.runners import resolve


class _Channel:
    def __init__(self, status):
        self._status = status

    def recv_exit_status(self):
        return self._status


class _Stream:
    def __init__(self, text, status=0):
        self._text = text
        self.channel = _Channel(status)

    def read(self):
        return self._text.encode()


class _FakeClient:
    status = 0
    out = ""
    err = ""

    def set_missing_host_key_policy(self, policy):
        pass

    def connect(self, *args, **kwargs):
        pass

    def exec_command(self, cmd, timeout=None):
        return None, _Stream(self.out, self.status), _Stream(self.err, self.status)

    def close(self):
        pass


def _run(monkeypatch, status, out="", err=""):
    _FakeClient.status, _FakeClient.out, _FakeClient.err = status, out, err
    monkeypatch.setattr(paramiko, "SSHClient", _FakeClient)
    return resolve._run_version_cmd("ssh://user@host/bash run.sh", "run.sh --version")


def test_ssh_version_cmd_success_returns_stdout(monkeypatch):
    assert _run(monkeypatch, 0, out="v8p5\n") == "v8p5"


def test_ssh_version_cmd_zero_exit_stderr_fallback(monkeypatch):
    assert _run(monkeypatch, 0, err="openjdk 17\n") == "openjdk 17"


def test_ssh_version_cmd_nonzero_exit_yields_no_identity(monkeypatch):
    assert _run(monkeypatch, 127, err="run.sh: command not found\n") is None
    assert _run(monkeypatch, 1, out="partial output\n") is None
