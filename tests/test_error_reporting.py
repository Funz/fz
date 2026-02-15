#!/usr/bin/env python3
"""
Test error reporting for model run failures across all protocols.

Verifies that when a calculation fails, the error message is descriptive
and actionable (e.g., "command not found", "permission denied") rather than
just "case failed" or a bare exit code.

Protocols tested:
- sh://   (local shell)
- ssh://  (remote via SSH, tested with localhost)
- slurm:// (SLURM, mocked when srun unavailable)
- funz:// (Funz protocol, mocked)
- classify_error() unit tests
"""

import os
import platform
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fz.runners import (
    classify_error,
    run_local_calculation,
    run_calculation,
)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_model():
    """A minimal model definition used across tests."""
    return {
        "varprefix": "$",
        "delim": "{}",
        "commentline": "#",
        "output": {
            "result": "grep 'result =' output.txt | cut -d'=' -f2 | tr -d ' '"
        },
    }


@pytest.fixture
def input_dir(tmp_path):
    """Create a minimal working directory with an input file."""
    work = tmp_path / "case_work"
    work.mkdir()
    (work / "input.txt").write_text("value = 42\n")
    # Create a minimal .fz_hash so input_files_list can be built
    (work / ".fz_hash").write_text("abc123 input.txt\n")
    return work


@pytest.fixture
def good_script(tmp_path):
    """Create a script that always succeeds."""
    script = tmp_path / "good.sh"
    script.write_text(
        "#!/bin/bash\necho 'result = 42' > output.txt\nexit 0\n"
    )
    script.chmod(0o755)
    return script


@pytest.fixture
def bad_exit_script(tmp_path):
    """Create a script that exits with code 1 and writes to stderr."""
    script = tmp_path / "bad_exit.sh"
    script.write_text(
        "#!/bin/bash\necho 'something went wrong' >&2\nexit 1\n"
    )
    script.chmod(0o755)
    return script


@pytest.fixture
def permission_denied_script(tmp_path):
    """Create a script with no execute permission."""
    script = tmp_path / "no_exec.sh"
    script.write_text("#!/bin/bash\necho 'result = 1' > output.txt\n")
    # Intentionally do NOT chmod +x
    script.chmod(0o644)
    return script


@pytest.fixture
def syntax_error_script(tmp_path):
    """Create a script with a bash syntax error."""
    script = tmp_path / "syntax_err.sh"
    script.write_text(
        "#!/bin/bash\nif [[ ; then\necho 'result = 1' > output.txt\nfi\n"
    )
    script.chmod(0o755)
    return script


# ===========================================================================
# 1. classify_error() unit tests
# ===========================================================================

class TestClassifyError:
    """Unit tests for the classify_error helper."""

    def test_command_not_found_stderr(self):
        msg = classify_error("bash: mycommand: command not found", exit_code=127, command="mycommand input.txt")
        assert "command not found" in msg.lower()
        assert "mycommand" in msg

    def test_command_not_found_exit_127(self):
        msg = classify_error("", exit_code=127, command="nonexistent_cmd")
        assert "command not found" in msg.lower()
        assert "nonexistent_cmd" in msg

    def test_permission_denied(self):
        msg = classify_error("bash: ./script.sh: Permission denied", exit_code=126, command="./script.sh")
        assert "permission denied" in msg.lower()

    def test_exit_126_not_executable(self):
        msg = classify_error("", exit_code=126, command="./script.sh")
        assert "not executable" in msg.lower() or "permission" in msg.lower()

    def test_no_such_file(self):
        msg = classify_error("bash: ./missing.sh: No such file or directory", exit_code=127, command="./missing.sh")
        assert "not found" in msg.lower()

    def test_out_of_memory(self):
        msg = classify_error("Cannot allocate memory", exit_code=1, command="heavy_calc")
        assert "memory" in msg.lower()

    def test_syntax_error(self):
        msg = classify_error("syntax error near unexpected token", exit_code=2, command="broken.sh")
        assert "syntax error" in msg.lower()

    def test_disk_full(self):
        msg = classify_error("No space left on device", exit_code=1, command="writer.sh")
        assert "filesystem" in msg.lower() or "space" in msg.lower()

    def test_ssh_connection_refused(self):
        msg = classify_error("Connection refused", exit_code=255, command="ssh cmd", protocol="ssh")
        assert "ssh" in msg.lower() or "connection" in msg.lower()

    def test_slurm_invalid_partition(self):
        msg = classify_error("srun: error: Invalid partition name specified", exit_code=1,
                             command="srun --partition=bogus run.sh", protocol="slurm")
        assert "slurm" in msg.lower() or "partition" in msg.lower()

    def test_signal_termination(self):
        msg = classify_error("", exit_code=-9, command="long_calc")
        assert "signal" in msg.lower() or "terminated" in msg.lower()

    def test_timeout_exit_124(self):
        msg = classify_error("", exit_code=124, command="slow_calc")
        assert "timed out" in msg.lower() or "timeout" in msg.lower()

    def test_generic_fallback_includes_stderr(self):
        msg = classify_error("some unusual error text", exit_code=42, command="weird.sh")
        assert "42" in msg
        assert "some unusual error text" in msg

    def test_empty_stderr_and_exit_code(self):
        msg = classify_error("", exit_code=1, command="fail.sh")
        assert "exit code 1" in msg.lower() or "failed" in msg.lower()

    def test_ssh_protocol_remote_label(self):
        msg = classify_error("bash: mycommand: command not found", exit_code=127,
                             command="mycommand", protocol="ssh")
        assert "remote" in msg.lower()

    def test_slurm_protocol_remote_label(self):
        msg = classify_error("bash: mycommand: command not found", exit_code=127,
                             command="mycommand", protocol="slurm")
        assert "remote" in msg.lower()

    def test_local_protocol_local_label(self):
        msg = classify_error("bash: mycommand: command not found", exit_code=127,
                             command="mycommand", protocol="sh")
        assert "locally" in msg.lower()

    def test_killed_process(self):
        msg = classify_error("Killed", exit_code=137, command="big_calc")
        assert "memory" in msg.lower() or "killed" in msg.lower()


# ===========================================================================
# 2. sh:// (local shell) error reporting
# ===========================================================================

class TestLocalShellErrorReporting:
    """Test that sh:// runner returns descriptive errors."""

    def test_missing_command_reports_not_found(self, input_dir, simple_model):
        """When the command does not exist, error should say 'command not found'."""
        result = run_local_calculation(
            working_dir=input_dir,
            command="this_command_absolutely_does_not_exist_xyz123",
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        error = result["error"].lower()
        assert "not found" in error or "no such file" in error, (
            f"Error should mention 'not found' but got: {result['error']}"
        )

    def test_permission_denied_reports_permission(self, input_dir, simple_model, permission_denied_script):
        """When script lacks execute permission, error should mention 'permission'."""
        # Copy script into working dir
        dest = input_dir / permission_denied_script.name
        shutil.copy2(permission_denied_script, dest)
        # Ensure no execute
        dest.chmod(0o644)

        result = run_local_calculation(
            working_dir=input_dir,
            command=f"bash {dest}",  # using bash to invoke, but script itself might error
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        # With "bash <script>", bash can read the file even without +x
        # So let's test direct execution instead
        result = run_local_calculation(
            working_dir=input_dir,
            command=str(dest),
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        error = result["error"].lower()
        assert "permission" in error or "not executable" in error or "denied" in error, (
            f"Error should mention 'permission' but got: {result['error']}"
        )

    def test_syntax_error_reports_syntax(self, input_dir, simple_model, syntax_error_script):
        """When script has syntax error, error message should mention 'syntax'."""
        dest = input_dir / syntax_error_script.name
        shutil.copy2(syntax_error_script, dest)
        dest.chmod(0o755)

        result = run_local_calculation(
            working_dir=input_dir,
            command=str(dest),
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        error = result["error"].lower()
        assert "syntax" in error or "unexpected" in error or "parse" in error, (
            f"Error should mention 'syntax' but got: {result['error']}"
        )

    def test_bad_exit_includes_stderr(self, input_dir, simple_model, bad_exit_script):
        """When script fails, stderr content should appear in error message."""
        dest = input_dir / bad_exit_script.name
        shutil.copy2(bad_exit_script, dest)

        result = run_local_calculation(
            working_dir=input_dir,
            command=str(dest),
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        assert "something went wrong" in result["error"] or "something went wrong" in result.get("stderr", ""), (
            f"Error or stderr should contain the script's error output, got: {result}"
        )

    def test_successful_run_no_error(self, input_dir, simple_model, good_script):
        """Successful run should have status 'done' and no error."""
        dest = input_dir / good_script.name
        shutil.copy2(good_script, dest)

        result = run_local_calculation(
            working_dir=input_dir,
            command=str(dest),
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "done"
        assert result.get("error") is None or result.get("error") == ""

    def test_error_result_has_command_key(self, input_dir, simple_model):
        """Failed result should always include the 'command' key."""
        result = run_local_calculation(
            working_dir=input_dir,
            command="nonexistent_command_xyz",
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        assert "command" in result, "Failed result must include 'command' key"

    def test_error_result_has_exit_code(self, input_dir, simple_model, bad_exit_script):
        """Failed result should include exit_code."""
        dest = input_dir / bad_exit_script.name
        shutil.copy2(bad_exit_script, dest)

        result = run_local_calculation(
            working_dir=input_dir,
            command=str(dest),
            model=simple_model,
            timeout=10,
            original_cwd=str(input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "exit_code" in result
        assert result["exit_code"] != 0


# ===========================================================================
# 3. ssh:// error reporting (using localhost or mocked)
# ===========================================================================

def _ssh_localhost_available():
    """Check if SSH to localhost is available for integration tests."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
             "localhost", "echo", "ok"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def _paramiko_available():
    """Check if paramiko is available."""
    try:
        import paramiko
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _paramiko_available(),
    reason="paramiko not installed"
)
class TestSSHErrorReporting:
    """Test SSH runner error reporting with mocked SSH connections."""

    def test_ssh_missing_command_error(self, input_dir, simple_model):
        """SSH runner should report 'command not found' when remote command doesn't exist."""
        from fz.runners import _execute_remote_command

        # Mock SSH client
        mock_ssh = MagicMock()

        # Simulate "command not found" on remote
        mock_channel = MagicMock()
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 127

        mock_stdout = MagicMock()
        mock_stdout.channel = mock_channel
        mock_stdout.read.return_value = b""

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"bash: nonexistent_cmd: command not found\n"

        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        result = _execute_remote_command(
            ssh_client=mock_ssh,
            command="nonexistent_cmd",
            remote_dir="/tmp/test",
            local_dir=input_dir,
            timeout=30,
            input_files_list=["input.txt"],
        )

        assert result["status"] == "failed"
        assert "error" in result, "SSH failed result must have an 'error' key"
        error = result["error"].lower()
        assert "not found" in error or "command" in error, (
            f"SSH error should mention 'not found', got: {result['error']}"
        )
        assert "remote" in error, (
            f"SSH error should indicate it's on remote server, got: {result['error']}"
        )

    def test_ssh_permission_denied_error(self, input_dir, simple_model):
        """SSH runner should report 'permission denied' for permission issues."""
        from fz.runners import _execute_remote_command

        mock_ssh = MagicMock()

        mock_channel = MagicMock()
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 126

        mock_stdout = MagicMock()
        mock_stdout.channel = mock_channel
        mock_stdout.read.return_value = b""

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"bash: ./script.sh: Permission denied\n"

        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        result = _execute_remote_command(
            ssh_client=mock_ssh,
            command="./script.sh",
            remote_dir="/tmp/test",
            local_dir=input_dir,
            timeout=30,
            input_files_list=["input.txt"],
        )

        assert result["status"] == "failed"
        assert "error" in result
        assert "permission" in result["error"].lower(), (
            f"SSH error should mention 'permission', got: {result['error']}"
        )

    def test_ssh_generic_failure_has_stderr(self, input_dir, simple_model):
        """SSH failure should include stderr content in error message."""
        from fz.runners import _execute_remote_command

        mock_ssh = MagicMock()

        mock_channel = MagicMock()
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 1

        mock_stdout = MagicMock()
        mock_stdout.channel = mock_channel
        mock_stdout.read.return_value = b""

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"Segmentation fault (core dumped)\n"

        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        result = _execute_remote_command(
            ssh_client=mock_ssh,
            command="crashing_program",
            remote_dir="/tmp/test",
            local_dir=input_dir,
            timeout=30,
            input_files_list=["input.txt"],
        )

        assert result["status"] == "failed"
        assert "error" in result
        assert "Segmentation fault" in result["error"] or "Segmentation fault" in result.get("stderr", "")

    def test_ssh_failed_result_has_command(self, input_dir, simple_model):
        """SSH failed result should always include command key."""
        from fz.runners import _execute_remote_command

        mock_ssh = MagicMock()

        mock_channel = MagicMock()
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 1

        mock_stdout = MagicMock()
        mock_stdout.channel = mock_channel
        mock_stdout.read.return_value = b""

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"error\n"

        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        result = _execute_remote_command(
            ssh_client=mock_ssh,
            command="some_command",
            remote_dir="/tmp/test",
            local_dir=input_dir,
            timeout=30,
            input_files_list=["input.txt"],
        )

        assert "command" in result, "SSH failed result must have 'command' key"


# ===========================================================================
# 4. slurm:// error reporting (mocked – srun usually not available)
# ===========================================================================

class TestSlurmErrorReporting:
    """Test SLURM runner error reporting with mocked srun."""

    def test_slurm_missing_command_local(self, input_dir, simple_model):
        """Local SLURM should report clear error when srun is not found."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="slurm://:fakepart/nonexistent_script_xyz.sh",
            model=simple_model,
            timeout=10,
            input_files_list=["input.txt"],
        )
        # srun itself might not be installed, so either srun not found or script not found
        assert result["status"] in ("failed", "error")
        assert "error" in result
        # The error should be descriptive, not just "case failed"
        assert len(result["error"]) > 10, (
            f"Error message should be descriptive, got: {result['error']}"
        )

    def test_slurm_remote_missing_command(self, input_dir, simple_model):
        """Remote SLURM should report 'command not found' for missing scripts."""
        if not _paramiko_available():
            pytest.skip("paramiko not installed")

        from fz.runners import _execute_remote_slurm_command

        mock_ssh = MagicMock()

        mock_channel = MagicMock()
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 127

        mock_stdout = MagicMock()
        mock_stdout.channel = mock_channel
        mock_stdout.read.return_value = b""

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"bash: nonexistent_script.sh: command not found\n"

        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        result = _execute_remote_slurm_command(
            ssh_client=mock_ssh,
            partition="compute",
            script="nonexistent_script.sh",
            remote_dir="/tmp/test",
            local_dir=input_dir,
            timeout=30,
            start_time=__import__("datetime").datetime.now(),
            env_info={"user": "test", "hostname": "test", "operating_system": "Linux",
                       "working_dir": "/tmp"},
            input_files_list=["input.txt"],
        )

        assert result["status"] == "failed"
        assert "error" in result, "SLURM failed result must have 'error' key"
        error = result["error"].lower()
        assert "not found" in error or "command" in error, (
            f"SLURM error should mention 'not found', got: {result['error']}"
        )

    def test_slurm_invalid_partition(self, input_dir, simple_model):
        """Remote SLURM should report partition error clearly."""
        if not _paramiko_available():
            pytest.skip("paramiko not installed")

        from fz.runners import _execute_remote_slurm_command

        mock_ssh = MagicMock()

        mock_channel = MagicMock()
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 1

        mock_stdout = MagicMock()
        mock_stdout.channel = mock_channel
        mock_stdout.read.return_value = b""

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"srun: error: Invalid partition name specified\n"

        mock_ssh.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        result = _execute_remote_slurm_command(
            ssh_client=mock_ssh,
            partition="nonexistent_partition",
            script="run.sh",
            remote_dir="/tmp/test",
            local_dir=input_dir,
            timeout=30,
            start_time=__import__("datetime").datetime.now(),
            env_info={"user": "test", "hostname": "test", "operating_system": "Linux",
                       "working_dir": "/tmp"},
            input_files_list=["input.txt"],
        )

        assert result["status"] == "failed"
        assert "error" in result
        error = result["error"].lower()
        assert "slurm" in error or "partition" in error, (
            f"SLURM error should mention 'slurm' or 'partition', got: {result['error']}"
        )


# ===========================================================================
# 5. funz:// error reporting
# ===========================================================================

class TestFunzErrorReporting:
    """Test Funz protocol error reporting."""

    def test_funz_invalid_uri(self, input_dir, simple_model):
        """Funz runner should report clear error for invalid URI."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="funz://invalid",
            model=simple_model,
            timeout=5,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "error"
        assert "error" in result
        assert len(result["error"]) > 5

    def test_funz_no_code(self, input_dir, simple_model):
        """Funz runner should report error when code is missing."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="funz://:9999/",
            model=simple_model,
            timeout=5,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "error"
        assert "error" in result


# ===========================================================================
# 6. Integration: fzr-level error propagation
# ===========================================================================

class TestFzrErrorPropagation:
    """Test that errors propagate correctly through fzr to the results DataFrame."""

    def test_fzr_missing_command_shows_error_in_results(self):
        """fzr results DataFrame should contain descriptive error for missing command."""
        from fz import fzr

        # Create input file
        Path("input.txt").write_text("x = ${x}\n")

        result = fzr(
            "input.txt",
            {"x": [1, 2]},
            {
                "varprefix": "$",
                "delim": "{}",
                "commentline": "#",
                "output": {"result": "cat output.txt"},
            },
            calculators=["sh://this_command_does_not_exist_at_all_xyz"],
            results_dir="results_missing_cmd",
        )

        # All cases should have failed
        for status in result["status"]:
            assert status != "done", f"Expected failure but got status: {status}"

        # Error column should contain descriptive messages
        for error_msg in result["error"]:
            assert error_msg is not None, "Error message should not be None for failed cases"
            assert len(str(error_msg)) > 10, (
                f"Error message should be descriptive, got: {error_msg}"
            )
            error_lower = str(error_msg).lower()
            assert "not found" in error_lower or "no such" in error_lower or "exit code" in error_lower, (
                f"Error should mention 'not found', got: {error_msg}"
            )

    def test_fzr_bad_script_shows_stderr_in_error(self):
        """fzr results should contain stderr info when script fails."""
        from fz import fzr

        Path("input.txt").write_text("x = ${x}\n")

        # Create a script that prints to stderr and exits non-zero
        Path("fail_with_msg.sh").write_text(
            "#!/bin/bash\necho 'CUSTOM_ERROR_MESSAGE_12345' >&2\nexit 1\n"
        )
        os.chmod("fail_with_msg.sh", 0o755)

        result = fzr(
            "input.txt",
            {"x": [1]},
            {
                "varprefix": "$",
                "delim": "{}",
                "commentline": "#",
                "output": {"result": "cat output.txt"},
            },
            calculators=["sh://bash fail_with_msg.sh"],
            results_dir="results_bad_script",
        )

        for status in result["status"]:
            assert status != "done"

        # The custom error message should appear somewhere in the error info
        all_errors = " ".join(str(e) for e in result["error"] if e)
        assert "CUSTOM_ERROR_MESSAGE_12345" in all_errors, (
            f"Custom stderr message should appear in error output, got: {all_errors}"
        )


# ===========================================================================
# 7. run_calculation dispatcher tests
# ===========================================================================

class TestRunCalculationDispatcher:
    """Test that run_calculation dispatches correctly and returns errors."""

    def test_sh_missing_command(self, input_dir, simple_model):
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="sh://nonexistent_command_xyz",
            model=simple_model,
            timeout=10,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        assert "not found" in result["error"].lower() or "exit code" in result["error"].lower()

    def test_bare_missing_command(self, input_dir, simple_model):
        """Non-prefixed URI should also give clear error."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="nonexistent_command_xyz",
            model=simple_model,
            timeout=10,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result

    def test_error_dict_structure(self, input_dir, simple_model):
        """Error result should have standard keys: status, error, command."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="sh://nonexistent_xyz",
            model=simple_model,
            timeout=10,
            input_files_list=["input.txt"],
        )
        assert "status" in result
        assert "error" in result
        assert "command" in result


# ===========================================================================
# 8. SSH integration error reporting (requires SSH server on localhost)
# ===========================================================================

def _ssh_key_available():
    """Check if passwordless SSH to localhost works (for CI)."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
             "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
             "localhost", "echo ok"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def _slurm_available():
    """Check if SLURM srun is available locally."""
    try:
        result = subprocess.run(
            ["srun", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _funz_udp_port():
    """Return the Funz UDP port from environment, or None."""
    port = os.environ.get("FUNZ_UDP_PORT")
    return int(port) if port else None


@pytest.mark.skipif(
    not _ssh_key_available(),
    reason="SSH server not available on localhost (run in ssh-localhost CI)",
)
class TestSSHIntegrationErrorReporting:
    """Integration tests that run against a real SSH server on localhost."""

    def _ssh_uri(self, command: str) -> str:
        import getpass
        return f"ssh://{getpass.getuser()}@localhost/{command}"

    def test_ssh_real_missing_command(self, input_dir, simple_model):
        """Over real SSH, a missing command should report 'not found'."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=self._ssh_uri("this_command_does_not_exist_xyz123"),
            model=simple_model,
            timeout=15,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed", f"Expected failed, got {result}"
        assert "error" in result
        error = result["error"].lower()
        assert "not found" in error or "no such file" in error, (
            f"SSH error should mention 'not found', got: {result['error']}"
        )

    def test_ssh_real_permission_denied(self, input_dir, simple_model, tmp_path):
        """Over real SSH, a non-executable script should report 'permission denied'."""
        # Create a script without execute permission in a place SSH can reach
        script = tmp_path / "no_exec_ssh.sh"
        script.write_text("#!/bin/bash\necho 'result = 1' > output.txt\n")
        script.chmod(0o644)

        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=self._ssh_uri(str(script)),
            model=simple_model,
            timeout=15,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed", f"Expected failed, got {result}"
        assert "error" in result
        error = result["error"].lower()
        assert "permission" in error or "not executable" in error or "denied" in error, (
            f"SSH error should mention 'permission', got: {result['error']}"
        )

    def test_ssh_real_bad_script(self, input_dir, simple_model, tmp_path):
        """Over real SSH, a script that fails should include stderr."""
        script = tmp_path / "fail_ssh.sh"
        script.write_text(
            "#!/bin/bash\necho 'SSH_SPECIFIC_ERROR_42' >&2\nexit 1\n"
        )
        script.chmod(0o755)

        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=self._ssh_uri(f"bash {script}"),
            model=simple_model,
            timeout=15,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        # The custom message should appear in error or stderr
        combined = result.get("error", "") + " " + result.get("stderr", "")
        assert "SSH_SPECIFIC_ERROR_42" in combined, (
            f"Custom stderr should appear in error output, got: {combined}"
        )

    def test_ssh_real_error_has_all_keys(self, input_dir, simple_model):
        """SSH error result should have status, error, and command keys."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=self._ssh_uri("nonexistent_xyz"),
            model=simple_model,
            timeout=15,
            input_files_list=["input.txt"],
        )
        assert "status" in result
        assert "error" in result
        assert "command" in result

    def test_ssh_real_fzr_error_propagation(self):
        """fzr with SSH calculator should propagate descriptive errors."""
        from fz import fzr

        import getpass
        Path("input.txt").write_text("x = ${x}\n")

        result = fzr(
            "input.txt",
            {"x": [1]},
            {"varprefix": "$", "delim": "{}", "commentline": "#",
             "output": {"result": "cat output.txt"}},
            calculators=[f"ssh://{getpass.getuser()}@localhost/nonexistent_xyz"],
            results_dir="results_ssh_err",
        )

        for status in result["status"]:
            assert status != "done"
        for error_msg in result["error"]:
            assert error_msg is not None
            assert len(str(error_msg)) > 10


# ===========================================================================
# 9. SLURM integration error reporting (requires srun on the machine)
# ===========================================================================

@pytest.mark.skipif(
    not _slurm_available(),
    reason="SLURM srun not available (run in slurm-localhost CI)",
)
class TestSlurmIntegrationErrorReporting:
    """Integration tests that run against a real local SLURM cluster."""

    def test_slurm_real_missing_command(self, input_dir, simple_model):
        """Real SLURM: missing command should report 'not found'."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="slurm://:debug/nonexistent_script_xyz123.sh",
            model=simple_model,
            timeout=30,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        error = result["error"].lower()
        assert "not found" in error or "no such" in error or "exit code" in error, (
            f"SLURM error should mention cause, got: {result['error']}"
        )

    def test_slurm_real_permission_denied(self, input_dir, simple_model, tmp_path):
        """Real SLURM: non-executable script should report 'permission'."""
        script = tmp_path / "no_exec_slurm.sh"
        script.write_text("#!/bin/bash\necho 'result = 1' > output.txt\n")
        script.chmod(0o644)

        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=f"slurm://:debug/{script}",
            model=simple_model,
            timeout=30,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        error = result["error"].lower()
        assert "permission" in error or "denied" in error or "not executable" in error or "exit code" in error, (
            f"SLURM error should mention cause, got: {result['error']}"
        )

    def test_slurm_real_bad_script(self, input_dir, simple_model, tmp_path):
        """Real SLURM: a failing script should include stderr."""
        script = tmp_path / "fail_slurm.sh"
        script.write_text(
            "#!/bin/bash\necho 'SLURM_ERR_MSG_999' >&2\nexit 1\n"
        )
        script.chmod(0o755)

        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=f"slurm://:debug/bash {script}",
            model=simple_model,
            timeout=30,
            input_files_list=["input.txt"],
        )
        assert result["status"] == "failed"
        assert "error" in result
        combined = result.get("error", "") + " " + result.get("stderr", "")
        assert "SLURM_ERR_MSG_999" in combined, (
            f"Custom stderr should appear in error, got: {combined}"
        )

    def test_slurm_real_error_has_all_keys(self, input_dir, simple_model):
        """SLURM error result should have status, error, command keys."""
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri="slurm://:debug/nonexistent_xyz",
            model=simple_model,
            timeout=30,
            input_files_list=["input.txt"],
        )
        assert "status" in result
        assert "error" in result
        assert "command" in result

    def test_slurm_real_fzr_error_propagation(self):
        """fzr with SLURM calculator should propagate descriptive errors."""
        from fz import fzr

        Path("input.txt").write_text("x = ${x}\n")

        result = fzr(
            "input.txt",
            {"x": [1]},
            {"varprefix": "$", "delim": "{}", "commentline": "#",
             "output": {"result": "cat output.txt"}},
            calculators=["slurm://:debug/nonexistent_xyz"],
            results_dir="results_slurm_err",
        )

        for status in result["status"]:
            assert status != "done"
        for error_msg in result["error"]:
            assert error_msg is not None
            assert len(str(error_msg)) > 10


# ===========================================================================
# 10. Funz integration error reporting (requires running Funz calculators)
# ===========================================================================

@pytest.mark.skipif(
    _funz_udp_port() is None,
    reason="FUNZ_UDP_PORT not set (run in funz-calculator CI)",
)
class TestFunzIntegrationErrorReporting:
    """Integration tests that run against real Funz calculators."""

    def test_funz_real_failing_code(self, input_dir, simple_model):
        """Funz calculator with calc_fail CODE should report descriptive error."""
        port = _funz_udp_port()
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=f"funz://:{port}/calc_fail",
            model=simple_model,
            timeout=30,
            input_files_list=["input.txt"],
        )
        assert result["status"] in ("failed", "error")
        assert "error" in result
        assert len(result["error"]) > 5, (
            f"Funz error should be descriptive, got: {result['error']}"
        )

    def test_funz_real_nonexistent_code(self, input_dir, simple_model):
        """Funz calculator with unknown CODE should report clear error."""
        port = _funz_udp_port()
        result = run_calculation(
            working_dir=input_dir,
            calculator_uri=f"funz://:{port}/totally_nonexistent_code_xyz",
            model=simple_model,
            timeout=15,
            input_files_list=["input.txt"],
        )
        assert result["status"] in ("failed", "error")
        assert "error" in result
        assert len(result["error"]) > 5

    def test_funz_real_fzr_error_propagation(self):
        """fzr with Funz calculator using calc_fail should propagate errors."""
        import fz as fzmod

        port = _funz_udp_port()
        Path("input.txt").write_text("value = ${value}\n")

        result = fzmod.fzr(
            "input.txt",
            {"value": [1]},
            {"varprefix": "$", "delim": "{}", "commentline": "#",
             "output": {"result": "grep 'result' output.txt | awk '{print $3}'"}},
            calculators=[f"funz://:{port}/calc_fail"],
            results_dir="results_funz_err",
        )

        for status in result["status"]:
            assert status != "done"
        for error_msg in result["error"]:
            assert error_msg is not None
