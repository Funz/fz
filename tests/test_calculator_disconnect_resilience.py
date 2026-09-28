#!/usr/bin/env python3
"""
End-to-end resilience tests: an fzr() campaign with several cases and multiple
calculators must run to completion even when some calculators "disconnect" or
die mid-calculation for a subset of their assigned cases.

"Disconnection" is emulated cheaply and deterministically with plain bash
scripts (no real network drops needed):
  - a script that kills its own process (SIGKILL) partway through, simulating
    a calculator process dying mid-calculation;
  - a script that hangs past a short timeout, simulating a calculator that
    stopped responding;
  - a script that always exits non-zero, simulating a calculator that is
    simply down for the whole campaign.

These feed fz.helpers.try_calculators_with_retry() (via fzr()) exactly as a
real disconnected calculator would: the in-flight case's subprocess just
fails/times out, there is no separate "disconnection" detection path — a
hard failure (non-zero exit, timeout, or exception) increments the retry
counter and the case is retried on a different calculator id
(fz/helpers.py::try_calculators_with_retry, capped by FZ_MAX_RETRIES,
default 5 -- fz/config.py).

All tests in this module use ``sh://`` calculators only, so they always run
in the main CI matrix. The SSH scenario at the bottom additionally exercises
a real ``ssh://localhost`` calculator (gated behind requires_ssh /
requires_paramiko, matching tests/test_ssh_many_cases.py) to check that a
remote-side hard failure also fails over correctly.
"""

import getpass
import os
import subprocess
import time
from pathlib import Path

import pytest

from fz import fzr
from fz.config import reload_config

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def is_none_or_nan(value):
    if value is None:
        return True
    if PANDAS_AVAILABLE:
        return pd.isna(value)
    return False


MODEL = {
    "varprefix": "$",
    "delim": "{}",
    "commentline": "#",
    "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"},
}


def _write_input():
    Path("input.txt").write_text(
        "#!/bin/bash\n# idx: ${idx}\necho 'idx=${idx}'\n"
    )


def _write_script(name: str, body: str):
    path = Path(name)
    path.write_text("#!/bin/bash\n" + body)
    os.chmod(path, 0o755)
    return path


@pytest.fixture(autouse=True)
def _restore_config():
    """Ensure FZ_MAX_RETRIES overrides made by a test don't leak into others."""
    yield
    reload_config()


# ===========================================================================
# 1. A calculator dies mid-calculation (process killed) -> failover
# ===========================================================================

def test_disconnect_process_killed_failover_completes_campaign():
    """One of two sh:// calculators dies (SIGKILLs its own process) on
    every case it is assigned; the campaign must still complete every case,
    either via failover to the healthy calculator or with a clear error --
    never a hang or an unhandled exception out of fzr()."""
    _write_input()
    # Simulates a calculator whose process is killed mid-calculation (e.g. the
    # remote host died, OOM-killer, operator killed the job): the process
    # disappears via SIGKILL instead of a normal non-zero exit.
    _write_script(
        "DyingCalculator.sh",
        "echo 'about to die' > partial.log\n"
        "kill -9 $$\n",
    )
    _write_script(
        "ReliableCalculator.sh",
        "echo 'result = 42' > output.txt\nexit 0\n",
    )

    n_cases = 6
    start = time.time()
    result = fzr(
        "input.txt",
        {"idx": list(range(n_cases))},
        MODEL,
        calculators=[
            "sh://bash ./DyingCalculator.sh",
            "sh://bash ./ReliableCalculator.sh",
        ],
        results_dir="results",
    )
    elapsed = time.time() - start

    # Never hangs: this should complete in a handful of seconds.
    assert elapsed < 60, f"Campaign took too long ({elapsed:.1f}s), looks hung"

    total = len(result["status"])
    assert total == n_cases, "Every case must get a result row, none dropped"

    # No case should be silently missing an output/status.
    assert all(s is not None for s in result["status"])

    # All cases must eventually succeed via failover to the reliable calculator.
    assert all(s == "done" for s in result["status"]), (
        f"Expected all cases to succeed via failover, got: {list(result['status'])}"
    )
    assert all(not is_none_or_nan(r) for r in result["result"])

    # The dying calculator must never be recorded as the *successful* calculator.
    assert all("DyingCalculator" not in c for c in result["calculator"]), (
        f"A case reported success from the dying calculator: {list(result['calculator'])}"
    )

    # Confirm failover actually happened (not just "always used the reliable
    # calculator from the start"): round-robin assigns even case indices to
    # the dying calculator first, so their history.txt must show a failed
    # attempt there before succeeding elsewhere.
    results_dir = Path("results")
    history_files = sorted(results_dir.rglob("history.txt"))
    assert history_files, "Expected per-case history.txt files"

    saw_dying_attempt_then_recovery = False
    for hf in history_files:
        content = hf.read_text()
        if "DyingCalculator" in content and "failed" in content.lower():
            saw_dying_attempt_then_recovery = True
            assert "ReliableCalculator" in content, (
                f"Case retried after dying calculator failure, but never tried "
                f"the reliable one: {content}"
            )
    assert saw_dying_attempt_then_recovery, (
        "Expected at least one case's history.txt to record a failed attempt "
        "on the dying calculator followed by a retry"
    )


# ===========================================================================
# 2. A calculator hangs past its timeout -> failover
# ===========================================================================

def test_disconnect_hang_past_timeout_failover_completes_campaign():
    """One calculator stops responding (hangs) on every case; with a short
    timeout configured, fzr() must time it out and fail over to the other
    calculator for every case, completing the whole campaign."""
    _write_input()
    _write_script("HangingCalculator.sh", "sleep 5\necho 'result = 1' > output.txt\n")
    _write_script(
        "ReliableCalculator.sh",
        "echo 'result = 99' > output.txt\nexit 0\n",
    )

    n_cases = 4
    model = dict(MODEL, timeout=2)  # short timeout so the hang is detected quickly
    start = time.time()
    result = fzr(
        "input.txt",
        {"idx": list(range(n_cases))},
        model,
        calculators=[
            "sh://bash ./HangingCalculator.sh",
            "sh://bash ./ReliableCalculator.sh",
        ],
        results_dir="results",
    )
    elapsed = time.time() - start

    assert elapsed < 60, f"Campaign took too long ({elapsed:.1f}s), looks hung"
    assert len(result["status"]) == n_cases
    assert all(s == "done" for s in result["status"]), (
        f"Expected all cases to succeed via failover after timeout, got: {list(result['status'])}"
    )
    assert all(int(r) == 99 for r in result["result"])
    assert all("HangingCalculator" not in c for c in result["calculator"])


# ===========================================================================
# 3. Every calculator fails for a case -> well-formed error row, no crash
# ===========================================================================

def test_all_calculators_exhausted_returns_error_row_not_crash():
    """When every calculator fails for a case, fzr() must return a
    well-formed status='error' row (with a message) instead of hanging,
    crashing, or letting an exception escape fzr()."""
    _write_input()
    _write_script("AlwaysFailsA.sh", "echo 'A is down' >&2\nexit 1\n")
    _write_script("AlwaysFailsB.sh", "kill -9 $$\n")

    # Keep the retry cap small so the exhaustion path is reached quickly.
    try:
        os.environ["FZ_MAX_RETRIES"] = "2"
        reload_config()
        start = time.time()
        result = fzr(
            "input.txt",
            {"idx": [0, 1]},
            MODEL,
            calculators=[
                "sh://bash ./AlwaysFailsA.sh",
                "sh://bash ./AlwaysFailsB.sh",
            ],
            results_dir="results",
        )
        elapsed = time.time() - start
    finally:
        os.environ.pop("FZ_MAX_RETRIES", None)
        reload_config()

    assert elapsed < 60, f"Exhaustion path took too long ({elapsed:.1f}s), looks hung"
    assert len(result["status"]) == 2, "No case should be dropped even when all calculators fail"
    assert all(s in ("error", "failed") for s in result["status"])
    assert all(is_none_or_nan(r) for r in result["result"])
    assert "error" in result
    assert all(e is not None and len(str(e)) > 0 for e in result["error"]), (
        "Expected a descriptive error message for every exhausted case"
    )


# ===========================================================================
# 4. Mixed campaign: several cases, 3 differently-behaved sh:// calculators
# ===========================================================================

def test_mixed_calculators_no_case_silently_dropped():
    """N cases spread across three sh:// calculators with different natures
    (reliable, dies mid-calculation, hangs past timeout): the full campaign
    must return one row per case, and every case is either 'done' (it failed
    over successfully) or a clean 'error' -- never missing."""
    _write_input()
    _write_script(
        "ReliableCalculator.sh",
        "echo 'result = 7' > output.txt\nexit 0\n",
    )
    _write_script("DyingCalculator.sh", "kill -9 $$\n")
    _write_script("HangingCalculator.sh", "sleep 5\necho 'result = 7' > output.txt\n")

    n_cases = 9
    model = dict(MODEL, timeout=2)
    start = time.time()
    result = fzr(
        "input.txt",
        {"idx": list(range(n_cases))},
        model,
        calculators=[
            "sh://bash ./ReliableCalculator.sh",
            "sh://bash ./DyingCalculator.sh",
            "sh://bash ./HangingCalculator.sh",
        ],
        results_dir="results",
    )
    elapsed = time.time() - start

    assert elapsed < 90, f"Mixed campaign took too long ({elapsed:.1f}s), looks hung"
    assert len(result["status"]) == n_cases, "Every case must get a result row"
    assert all(s is not None for s in result["status"])

    # Every case must resolve to a well-formed terminal state.
    assert all(s in ("done", "error", "failed") for s in result["status"]), (
        f"Unexpected status values: {list(result['status'])}"
    )
    # With a healthy calculator in the pool and default FZ_MAX_RETRIES (5),
    # every case should in fact succeed via failover.
    assert all(s == "done" for s in result["status"]), (
        f"Expected all cases to succeed via failover, got: {list(result['status'])}"
    )
    assert all(int(r) == 7 for r in result["result"])


# ===========================================================================
# 5. ssh:// calculator dies mid-calculation -> failover to sh://
# ===========================================================================

def _paramiko_available():
    try:
        import paramiko  # noqa: F401
        return True
    except ImportError:
        return False


from conftest import SSH_AVAILABLE  # noqa: E402 (shared with test_ssh_many_cases.py etc.)

PARAMIKO_AVAILABLE = _paramiko_available()


@pytest.mark.requires_ssh
@pytest.mark.requires_paramiko
@pytest.mark.skipif(not SSH_AVAILABLE, reason="SSH server not available on localhost")
@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko library not installed")
def test_ssh_disconnect_failover_to_sh_completes_campaign():
    """A remote ssh://localhost calculator dies mid-calculation (its shell is
    SIGKILLed on the remote side, exercising the paramiko exec_command /
    exit-status path with a hard remote failure) for every case it is
    assigned; the campaign must still complete via failover to a local sh://
    calculator."""
    test_dir = Path.cwd()
    ssh_dir = test_dir / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    key_path = ssh_dir / "test_key"
    pub_key_path = ssh_dir / "test_key.pub"

    result = subprocess.run(
        ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", str(key_path),
         "-N", "", "-C", "fz-disconnect-test"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Could not generate SSH key: {result.stderr}")
    key_path.chmod(0o600)
    pub_key_path.chmod(0o644)

    home_ssh_dir = Path.home() / ".ssh"
    home_ssh_dir.mkdir(mode=0o700, exist_ok=True)
    authorized_keys_path = home_ssh_dir / "authorized_keys"
    pub_key_content = pub_key_path.read_text().strip()
    key_marker = f"# FZ-DISCONNECT-TEST-{os.getpid()}"
    key_entry = f"{key_marker}\n{pub_key_content}\n"
    original_authorized_keys = (
        authorized_keys_path.read_text() if authorized_keys_path.exists() else None
    )

    # fzr()'s own paramiko connect() (fz/runners/ssh.py) takes no -i / key_filename:
    # it only relies on look_for_keys (default-named keys under ~/.ssh) or an
    # ssh-agent identity. Our preflight `ssh -i key_path` check below would pass
    # regardless, so without this step the test could silently stop exercising
    # DyingRemote.sh (falling back on some ambient identity) or fail outright in
    # an environment with no ambient identity at all. Mirrors test_ssh_many_cases.py.
    added_to_agent = False
    std_key_path = None
    std_key_pub_path = None
    try:
        with open(authorized_keys_path, "a") as f:
            f.write(key_entry)
        authorized_keys_path.chmod(0o600)
        time.sleep(0.5)

        agent_result = subprocess.run(["ssh-add", str(key_path)], capture_output=True, text=True)
        if agent_result.returncode == 0:
            added_to_agent = True
        else:
            # No agent running (or it refused the key): fall back to a
            # default-named key so paramiko's look_for_keys finds it.
            std_key_path = home_ssh_dir / "id_rsa"
            std_key_pub_path = home_ssh_dir / "id_rsa.pub"
            if std_key_path.exists():
                pytest.skip(
                    "No SSH agent available and ~/.ssh/id_rsa already exists; "
                    "refusing to overwrite it for this test"
                )
            std_key_path.write_bytes(key_path.read_bytes())
            std_key_path.chmod(0o600)
            std_key_pub_path.write_bytes(pub_key_path.read_bytes())
            std_key_pub_path.chmod(0o644)

        known_hosts = ssh_dir / "known_hosts"
        scan = subprocess.run(["ssh-keyscan", "-H", "localhost"], capture_output=True, text=True)
        if scan.returncode != 0:
            pytest.skip(f"ssh-keyscan failed: {scan.stderr}")
        known_hosts.write_text(scan.stdout)
        known_hosts.chmod(0o644)

        ssh_config_path = ssh_dir / "config"
        ssh_config_path.write_text(
            "Host localhost\n    StrictHostKeyChecking no\n    LogLevel ERROR\n"
        )
        ssh_config_path.chmod(0o600)

        check = subprocess.run(
            ["ssh", "-i", str(key_path), "-F", str(ssh_config_path),
             "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             f"{getpass.getuser()}@localhost", "echo ok"],
            capture_output=True, text=True, timeout=10,
        )
        if check.returncode != 0:
            pytest.skip(f"SSH connection to localhost not usable: {check.stderr}")

        _write_input()
        _write_script("DyingRemote.sh", "kill -9 $$\n")
        _write_script(
            "ReliableCalculator.sh",
            "echo 'result = 5' > output.txt\nexit 0\n",
        )

        user = getpass.getuser()
        ssh_calculator = f"ssh://{user}@localhost/bash {(test_dir / 'DyingRemote.sh').resolve()}"
        sh_calculator = "sh://bash ./ReliableCalculator.sh"

        n_cases = 4
        start = time.time()
        result = fzr(
            "input.txt",
            {"idx": list(range(n_cases))},
            MODEL,
            calculators=[ssh_calculator, sh_calculator],
            results_dir="results",
        )
        elapsed = time.time() - start

        assert elapsed < 90, f"SSH failover campaign took too long ({elapsed:.1f}s)"
        assert len(result["status"]) == n_cases
        assert all(s == "done" for s in result["status"]), (
            f"Expected failover to sh:// calculator for all cases, got: {list(result['status'])}"
        )
        assert all(int(r) == 5 for r in result["result"])
        assert all("DyingRemote" not in c for c in result["calculator"])
    finally:
        if added_to_agent:
            subprocess.run(["ssh-add", "-d", str(key_path)], capture_output=True, text=True)
        if std_key_path is not None:
            std_key_path.unlink(missing_ok=True)
        if std_key_pub_path is not None:
            std_key_pub_path.unlink(missing_ok=True)
        if authorized_keys_path.exists():
            content = authorized_keys_path.read_text()
            lines = content.split("\n")
            cleaned = []
            skip_next = False
            for line in lines:
                if key_marker in line:
                    skip_next = True
                    continue
                if skip_next and line.strip() == pub_key_content.strip():
                    skip_next = False
                    continue
                cleaned.append(line)
            if original_authorized_keys is not None:
                authorized_keys_path.write_text(original_authorized_keys)
            else:
                cleaned_content = "\n".join(cleaned)
                if cleaned_content.strip():
                    authorized_keys_path.write_text(cleaned_content)
                else:
                    authorized_keys_path.unlink()
