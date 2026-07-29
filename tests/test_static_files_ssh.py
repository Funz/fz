"""
Test model "static_files" (see tests/test_static_files.py) over a real ssh://
calculator connecting to localhost.

Unlike sh:// (same filesystem, symlinks just resolve), ssh:// exercises the
actual remote-transfer code path: relative static_files entries are
explicitly uploaded via SFTP from their real source path
(runners.transfer_static_files_to_remote_sftp), since they live outside
input_path and the generic per-case file transfer only sees what's physically
in the local working directory.

This requires an SSH server reachable at localhost with key-based auth to the
current user, set up the same way as tests/test_ssh_many_cases.py.
"""
import os
import subprocess
import time
from pathlib import Path

import pytest
import getpass

from conftest import SSH_AVAILABLE

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False


def _setup_ssh_key(test_dir: Path):
    """Generate a dedicated SSH key pair and register it for localhost auth.

    Returns (key_path, ssh_config_path, cleanup) where cleanup() removes the
    key from authorized_keys again.
    """
    ssh_dir = test_dir / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    key_path = ssh_dir / "test_key"
    pub_key_path = ssh_dir / "test_key.pub"

    result = subprocess.run(
        ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", str(key_path),
         "-N", "", "-C", "fz-static-files-test-key"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Failed to generate SSH key: {result.stderr}"
    key_path.chmod(0o600)
    pub_key_path.chmod(0o644)

    pub_key_content = pub_key_path.read_text().strip()
    home_ssh_dir = Path.home() / ".ssh"
    home_ssh_dir.mkdir(mode=0o700, exist_ok=True)
    authorized_keys_path = home_ssh_dir / "authorized_keys"

    key_marker = f"# FZ-STATIC-FILES-TEST-KEY-MARKER-{os.getpid()}"
    original_authorized_keys = authorized_keys_path.read_text() if authorized_keys_path.exists() else None
    with open(authorized_keys_path, "a") as f:
        f.write(f"{key_marker}\n{pub_key_content}\n")
    authorized_keys_path.chmod(0o600)
    time.sleep(0.5)

    ssh_config_path = ssh_dir / "config"
    ssh_config_path.write_text(
        "Host localhost\n"
        "    StrictHostKeyChecking no\n"
        "    UserKnownHostsFile /dev/null\n"
        "    LogLevel ERROR\n"
    )
    ssh_config_path.chmod(0o600)

    def cleanup():
        if not authorized_keys_path.exists():
            return
        lines = authorized_keys_path.read_text().split("\n")
        cleaned, skip_next = [], False
        for line in lines:
            if key_marker in line:
                skip_next = True
                continue
            if skip_next and line.strip() == pub_key_content:
                skip_next = False
                continue
            cleaned.append(line)
        if original_authorized_keys is not None:
            authorized_keys_path.write_text(original_authorized_keys)
        else:
            authorized_keys_path.write_text("\n".join(cleaned))

    return key_path, ssh_config_path, cleanup


@pytest.mark.requires_ssh
@pytest.mark.requires_paramiko
@pytest.mark.skipif(not SSH_AVAILABLE, reason="SSH server not available on localhost")
@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko library not installed")
def test_static_files_over_ssh_localhost(tmp_path, monkeypatch):
    """Relative static_files are uploaded via SFTP; absolute ones are assumed
    already present on the "remote" side (true here since it's localhost)."""
    import fz

    test_dir = tmp_path
    key_path, ssh_config_path, cleanup = _setup_ssh_key(test_dir)

    try:
        # Verify the key actually authenticates before trusting the fz test below
        check = subprocess.run(
            ["ssh", "-i", str(key_path), "-F", str(ssh_config_path),
             "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             f"{getpass.getuser()}@localhost", "echo ok"],
            capture_output=True, text=True, timeout=10,
        )
        assert check.returncode == 0, f"SSH connection failed: {check.stderr}"

        # fz's own ssh:// calculator (paramiko) needs localhost in the user's
        # known_hosts, unlike the -F ssh_config check above
        home_ssh_dir = Path.home() / ".ssh"
        home_ssh_dir.mkdir(mode=0o700, exist_ok=True)
        known_hosts_path = home_ssh_dir / "known_hosts"
        keyscan = subprocess.run(["ssh-keyscan", "-H", "localhost"], capture_output=True, text=True)
        if keyscan.returncode == 0 and keyscan.stdout:
            with open(known_hosts_path, "a") as f:
                f.write(keyscan.stdout)
            known_hosts_path.chmod(0o644)

        assets_dir = test_dir / "assets"
        assets_dir.mkdir()
        weather = assets_dir / "weather.csv"
        weather.write_text("weather-over-ssh\n")

        shared_absolute = test_dir / "shared_ref.bin"
        shared_absolute.write_text("shared-over-ssh")

        study_dir = test_dir / "study"
        study_dir.mkdir()
        monkeypatch.chdir(study_dir)

        input_file = study_dir / "input.txt"
        input_file.write_text("x=$x\n")

        calc_script = study_dir / "calc.sh"
        # Reference the relative (uploaded/symlinked) file by name, and the
        # absolute one by its full path - it's genuinely present remotely
        # here since "remote" is localhost.
        calc_script.write_text(
            f"#!/bin/bash\ncat weather.csv {shared_absolute} > combined.txt\n"
        )
        calc_script.chmod(0o755)

        model = {
            "static_files": ["../assets/weather.csv", str(shared_absolute)],
            "output": {"echo": "cat combined.txt"},
        }

        # fz's ssh:// URI doesn't take custom ssh options; rely on default
        # agent/key discovery plus the authorized_keys entry set up above,
        # matching tests/test_ssh_many_cases.py's approach.
        ssh_calculator = f"ssh://{getpass.getuser()}@localhost/bash {calc_script.resolve()}"

        result = subprocess.run(["ssh-add", str(key_path)], capture_output=True, text=True)
        if result.returncode != 0:
            std_key = Path.home() / ".ssh" / "id_rsa_fz_static_files_test"
            std_key.write_bytes(key_path.read_bytes())
            std_key.chmod(0o600)
            (Path.home() / ".ssh" / "id_rsa_fz_static_files_test.pub").write_bytes(
                (key_path.with_suffix(".pub")).read_bytes()
            )

        res = fz.fzr(str(input_file), {"x": [1]}, model,
                      results_dir="results", calculators=[ssh_calculator])

        assert res["status"][0] == "done", res.get("error", [None])[0]
        assert res["echo"][0] == "weather-over-ssh\nshared-over-ssh"
    finally:
        cleanup()
