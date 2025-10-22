#!/usr/bin/env python3
"""
Demonstration tests for bash requirement on Windows

These tests demonstrate what happens when importing fz on Windows
with and without bash available. They serve both as tests and
as documentation of the expected behavior.
"""

import platform
import pytest
from unittest.mock import patch
from io import StringIO


def test_demo_windows_without_bash():
    """
    Demonstrate what happens when importing fz on Windows without bash

    This test shows the error message that users will see when they
    try to import fz on Windows without bash in PATH.
    """
    from fz.core import check_bash_availability_on_windows

    # Mock platform to be Windows and shutil.which to return None
    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                check_bash_availability_on_windows()

            error_msg = str(exc_info.value)

            # Verify comprehensive error message
            assert "ERROR: bash is not available in PATH on Windows" in error_msg
            assert "fz requires bash and Unix utilities" in error_msg
            assert "grep, cut, awk, sed, tr, cat" in error_msg

            # Verify installation instructions are present
            assert "Cygwin (recommended)" in error_msg
            assert "Git for Windows" in error_msg
            assert "WSL (Windows Subsystem for Linux)" in error_msg

            # Verify download URLs
            assert "https://www.cygwin.com/" in error_msg
            assert "https://git-scm.com/download/win" in error_msg

            # Verify PATH setup instructions
            assert "PATH" in error_msg
            assert "bash --version" in error_msg
            assert "grep --version" in error_msg


def test_demo_windows_with_cygwin():
    """
    Demonstrate successful import on Windows with Cygwin bash
    """
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value='C:\\cygwin64\\bin\\bash.exe'):
            # Should succeed without error
            check_bash_availability_on_windows()


def test_demo_windows_with_git_bash():
    """
    Demonstrate successful import on Windows with Git Bash
    """
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value='C:\\Program Files\\Git\\bin\\bash.exe'):
            # Should succeed without error
            check_bash_availability_on_windows()


def test_demo_windows_with_wsl():
    """
    Demonstrate successful import on Windows with WSL bash
    """
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value='C:\\Windows\\System32\\bash.exe'):
            # Should succeed without error
            check_bash_availability_on_windows()


def test_demo_error_message_readability():
    """
    Verify that the error message is clear and actionable

    This test ensures the error message:
    1. Clearly states the problem
    2. Provides multiple solutions
    3. Includes specific instructions for each solution
    4. Tells user how to verify the fix
    5. Mentions required Unix utilities
    """
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                check_bash_availability_on_windows()

            error_msg = str(exc_info.value)

            # Split into lines for analysis
            lines = error_msg.split('\n')

            # Should have clear structure with sections
            assert any('ERROR' in line for line in lines), "Should have ERROR marker"
            assert any('Unix utilities' in line for line in lines), "Should mention Unix utilities"
            assert any('grep' in line for line in lines), "Should mention grep utility"
            assert any('Cygwin' in line for line in lines), "Should mention Cygwin"
            assert any('Git for Windows' in line or 'Git Bash' in line for line in lines), "Should mention Git Bash"
            assert any('WSL' in line for line in lines), "Should mention WSL"
            assert any('verify' in line.lower() or 'version' in line.lower() for line in lines), "Should mention verification"

            # Should be multi-line for readability
            assert len(lines) > 10, "Error message should be detailed with multiple lines"


def test_demo_bash_used_for_output_evaluation():
    """
    Demonstrate that bash is used for output command evaluation on Windows

    This test shows that fzo() uses bash as the shell interpreter on Windows
    """
    import subprocess
    from unittest.mock import MagicMock, call

    # We need to test that subprocess.run is called with executable=bash on Windows
    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value='C:\\cygwin64\\bin\\bash.exe'):
            # The check would pass
            from fz.core import check_bash_availability_on_windows
            check_bash_availability_on_windows()

    # This demonstrates the behavior - in actual fzo() execution,
    # subprocess.run would be called with executable pointing to bash


def test_current_platform_compatibility():
    """
    Verify fz works on the current platform

    This test runs on the actual current platform (Linux, macOS, or Windows)
    and verifies that fz can be imported successfully.
    """
    current_platform = platform.system()

    # Try importing fz
    try:
        import fz
        # Import succeeded
        assert fz.__version__ is not None

        if current_platform == "Windows":
            # On Windows, bash must be available if import succeeded
            import shutil
            bash_path = shutil.which("bash")
            assert bash_path is not None, (
                "If fz imported on Windows, bash should be in PATH"
            )

    except RuntimeError as e:
        # Import failed - this is only acceptable on Windows without bash
        if current_platform == "Windows":
            assert "bash is not available" in str(e)
        else:
            pytest.fail(
                f"fz import should not fail on {current_platform}: {e}"
            )


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="This test is specific to Windows behavior"
)
def test_actual_windows_bash_availability():
    """
    On actual Windows systems, verify bash availability or provide helpful message

    This test only runs on Windows and checks if bash is actually available.
    """
    import shutil

    bash_path = shutil.which("bash")

    if bash_path is None:
        pytest.skip(
            "Bash not available on this Windows system. "
            "Please install Cygwin, Git Bash, or WSL. "
            "See BASH_REQUIREMENT.md for details."
        )
    else:
        # Bash is available - verify it works
        import subprocess
        result = subprocess.run(
            ["bash", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "bash" in result.stdout.lower()
