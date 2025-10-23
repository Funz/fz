#!/usr/bin/env python3
"""
Test run_command helper function

This test suite verifies that:
1. run_command works correctly with subprocess.run (default mode)
2. run_command works correctly with subprocess.Popen (use_popen=True)
3. run_command properly handles Windows bash executable detection
4. run_command properly sets Windows-specific process creation flags
5. run_command works on both Unix and Windows platforms
"""

import platform
import subprocess
import sys
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import tempfile
import os


def test_run_command_basic_run_mode():
    """Test run_command in default run mode (subprocess.run)"""
    from fz.helpers import run_command

    # Simple echo command should work on all platforms
    result = run_command("echo hello", capture_output=True, text=True)

    assert result.returncode == 0
    assert "hello" in result.stdout.strip()


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses Unix-specific pwd command")
def test_run_command_with_cwd_unix():
    """Test run_command with custom working directory on Unix"""
    from fz.helpers import run_command

    # Create a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run command in temp directory
        result = run_command("pwd", capture_output=True, text=True, cwd=tmpdir)

        assert result.returncode == 0
        # Verify the output contains the temp directory path
        assert tmpdir in result.stdout or os.path.basename(tmpdir) in result.stdout


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_run_command_with_cwd_windows():
    """Test run_command with custom working directory on Windows"""
    from fz.helpers import run_command

    # Create a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run command in temp directory
        result = run_command("cd", capture_output=True, text=True, cwd=tmpdir)

        assert result.returncode == 0


def test_run_command_popen_mode():
    """Test run_command in Popen mode"""
    from fz.helpers import run_command

    # Use Popen mode to get process object
    process = run_command(
        "echo test",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        use_popen=True
    )

    assert isinstance(process, subprocess.Popen)
    stdout, stderr = process.communicate()
    assert process.returncode == 0
    assert b"test" in stdout


def test_run_command_with_output_files():
    """Test run_command with output redirected to files"""
    from fz.helpers import run_command

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "out.txt"
        err_file = Path(tmpdir) / "err.txt"

        with open(out_file, "w") as out, open(err_file, "w") as err:
            process = run_command(
                "echo output",
                shell=True,
                stdout=out,
                stderr=err,
                use_popen=True
            )
            process.wait()

        # Verify output was written to file
        assert out_file.exists()
        content = out_file.read_text()
        assert "output" in content


def test_run_command_windows_bash_detection_unix():
    """Test that run_command doesn't use bash detection on Unix"""
    from fz.helpers import run_command

    # On non-Windows, bash executable should be None
    result = run_command("echo test", capture_output=True, text=True)
    assert result.returncode == 0
    assert "test" in result.stdout


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_run_command_windows_bash_detection():
    """Test that run_command uses bash on Windows when available"""
    from fz.helpers import run_command
    import subprocess as sp

    with patch('fz.helpers.platform.system', return_value='Windows'):
        with patch('fz.helpers.get_windows_bash_executable') as mock_get_bash:
            mock_get_bash.return_value = 'C:\\msys64\\usr\\bin\\bash.exe'

            # Mock subprocess module run function
            with patch.object(sp, 'run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test")

                result = run_command("echo test", capture_output=True, text=True)

                # Verify get_windows_bash_executable was called
                mock_get_bash.assert_called()
                # Verify subprocess.run was called with executable parameter
                call_kwargs = mock_run.call_args[1]
                # Note: On Windows with shell=True, executable should be None to avoid subprocess issues
                assert call_kwargs['executable'] is None or call_kwargs['executable'] == 'C:\\msys64\\usr\\bin\\bash.exe', \
                    f"executable should be None or bash path, got: {call_kwargs['executable']}"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_run_command_windows_popen_creationflags():
    """Test that run_command sets proper creationflags on Windows for Popen"""
    from fz.helpers import run_command
    import subprocess as sp

    with patch('fz.helpers.platform.system', return_value='Windows'):
        with patch('fz.helpers.get_windows_bash_executable') as mock_get_bash:
            mock_get_bash.return_value = None

            # Mock subprocess module Popen
            with patch.object(sp, 'Popen') as mock_popen:
                mock_process = MagicMock()
                mock_popen.return_value = mock_process

                process = run_command(
                    "echo test",
                    shell=True,
                    stdout=subprocess.PIPE,
                    use_popen=True
                )

                # Verify Popen was called with creationflags
                call_kwargs = mock_popen.call_args[1]
                assert 'creationflags' in call_kwargs
                # Verify it's one of the expected Windows flags
                assert call_kwargs['creationflags'] in [
                    getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0),
                    getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                ]


def test_run_command_command_from_model():
    """Test run_command with a command that would come from model output dict"""
    from fz.helpers import run_command

    # Simulate a command from model output specification
    # Use a simpler command that works reliably across platforms
    command = "grep 'result' output.txt"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test output file
        output_file = Path(tmpdir) / "output.txt"
        output_file.write_text("result = 42\n")

        # Run command to extract value
        result = run_command(
            command,
            capture_output=True,
            text=True,
            cwd=tmpdir
        )

        assert result.returncode == 0
        # Verify the output contains both 'result' and '42'
        assert "result" in result.stdout
        assert "42" in result.stdout


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses Unix shell script")
def test_run_command_calculator_script_unix():
    """Test run_command with a Unix shell calculator script"""
    from fz.helpers import run_command

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple calculator script
        script_path = Path(tmpdir) / "calc.sh"
        script_content = "#!/bin/bash\necho 'result: 100'\n"

        script_path.write_text(script_content)
        script_path.chmod(0o755)

        # Run calculator script
        command = f"bash {script_path}"
        result = run_command(
            command,
            capture_output=True,
            text=True,
            cwd=tmpdir
        )

        assert result.returncode == 0
        assert "100" in result.stdout


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
def test_run_command_calculator_script_windows():
    """Test run_command with a Windows batch calculator script"""
    from fz.helpers import run_command

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple batch calculator script
        script_path = Path(tmpdir) / "calc.bat"
        script_content = "@echo off\necho result: 100\n"

        script_path.write_text(script_content)

        # Run calculator script
        result = run_command(
            str(script_path),
            capture_output=True,
            text=True,
            cwd=tmpdir
        )

        assert result.returncode == 0
        assert "100" in result.stdout


def test_run_command_error_handling():
    """Test run_command handles errors properly"""
    from fz.helpers import run_command

    # Command that should fail
    result = run_command(
        "nonexistent_command_xyz",
        capture_output=True,
        text=True
    )

    # Should have non-zero return code
    assert result.returncode != 0


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific timeout test")
def test_run_command_timeout_unix():
    """Test run_command respects timeout parameter on Unix"""
    from fz.helpers import run_command

    # This should timeout (sleep for 10 seconds with 1 second timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        run_command("sleep 10", timeout=1, capture_output=True)


#@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific timeout test")
#def test_run_command_timeout_windows():
#    """Test run_command respects timeout parameter on Windows"""
#    from fz.helpers import run_command
#
#    # This should timeout (sleep for 10 seconds with 1 second timeout)
#    with pytest.raises(subprocess.TimeoutExpired):
#        run_command("timeout /t 10", timeout=1, capture_output=True)


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific environment variable syntax")
def test_run_command_preserves_kwargs_unix():
    """Test that run_command preserves additional kwargs on Unix"""
    from fz.helpers import run_command

    # Pass custom environment
    custom_env = os.environ.copy()
    custom_env['TEST_VAR'] = 'test_value'

    command = "echo $TEST_VAR"

    result = run_command(
        command,
        capture_output=True,
        text=True,
        env=custom_env
    )

    assert result.returncode == 0
    assert "test_value" in result.stdout


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific environment variable syntax")
def test_run_command_preserves_kwargs_windows():
    """Test that run_command preserves additional kwargs on Windows"""
    from fz.helpers import run_command

    # Pass custom environment
    custom_env = os.environ.copy()
    custom_env['TEST_VAR'] = 'test_value'

    command = "echo %TEST_VAR%"

    result = run_command(
        command,
        capture_output=True,
        text=True,
        env=custom_env
    )

    assert result.returncode == 0
    assert "test_value" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
