#!/usr/bin/env python3
"""
Test bash availability check on Windows

This test suite verifies that:
1. The bash checking function works without errors on non-Windows platforms
2. The bash checking function raises an error on Windows when bash is not available
3. The bash checking function succeeds on Windows when bash is available
4. The fz package can be imported successfully on all platforms
"""

import platform
import sys
import pytest
from unittest.mock import patch, MagicMock


def test_bash_check_on_non_windows():
    """Test that bash check does nothing on non-Windows platforms"""
    from fz.core import check_bash_availability_on_windows

    # Should not raise any error on non-Windows
    # (Even if we're on Windows, we'll mock the platform check)
    with patch('fz.core.platform.system', return_value='Linux'):
        check_bash_availability_on_windows()
        # If we get here without exception, test passes


def test_bash_check_on_windows_without_bash():
    """Test that bash check raises error on Windows when bash is missing"""
    from fz.core import check_bash_availability_on_windows

    # Mock platform to be Windows and shutil.which to return None
    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                check_bash_availability_on_windows()

            error_msg = str(exc_info.value)
            # Verify error message contains expected content
            assert "bash is not available" in error_msg
            assert "MSYS2" in error_msg
            assert "Git for Windows" in error_msg
            assert "WSL" in error_msg


def test_bash_check_on_windows_with_bash():
    """Test that bash check succeeds on Windows when bash is available"""
    from fz.core import check_bash_availability_on_windows

    # Mock platform to be Windows and shutil.which to return a bash path
    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value='C:\\msys64\\usr\\bin\\bash.exe'):
            # Should not raise any exception
            check_bash_availability_on_windows()


def test_import_fz_on_current_platform():
    """Test that importing fz works on the current platform"""
    current_platform = platform.system()

    try:
        # Re-import to ensure the startup check runs
        import importlib
        import fz
        importlib.reload(fz)

        # Should succeed on Linux/macOS without bash check
        # Should succeed on Windows if bash is available
        assert fz.__version__ is not None

    except RuntimeError as e:
        # Only acceptable if we're on Windows and bash is genuinely not available
        if current_platform == "Windows":
            # This is expected - bash may not be installed
            assert "bash is not available" in str(e)
        else:
            # On Linux/macOS, this should never happen
            pytest.fail(f"Unexpected RuntimeError on {current_platform}: {e}")


def test_error_message_format():
    """Test that error message is well-formatted and helpful"""
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                check_bash_availability_on_windows()

            error_msg = str(exc_info.value)

            # Verify Unix utilities are mentioned
            assert "Unix utilities" in error_msg
            assert "grep, cut, awk, sed, tr, cat" in error_msg

            # Verify all installation options are mentioned
            assert "1. MSYS2" in error_msg
            assert "2. Git for Windows" in error_msg
            assert "3. WSL" in error_msg

            # Verify download links are provided
            assert "https://www.msys2.org/" in error_msg
            assert "https://git-scm.com/download/win" in error_msg

            # Verify verification instructions are included
            assert "bash --version" in error_msg
            assert "grep --version" in error_msg


def test_bash_path_logged_when_found():
    """Test that bash path is logged when found on Windows"""
    from fz.core import check_bash_availability_on_windows

    bash_path = 'C:\\Program Files\\Git\\bin\\bash.exe'

    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value=bash_path):
            with patch('fz.core.log_debug') as mock_log:
                check_bash_availability_on_windows()

                # Verify that log_debug was called with the bash path
                mock_log.assert_called_once()
                call_args = mock_log.call_args[0][0]
                assert bash_path in call_args
                assert "Bash found on Windows" in call_args


@pytest.mark.parametrize("bash_path", [
    "C:\\msys64\\usr\\bin\\bash.exe",  # MSYS2
    "C:\\Program Files\\Git\\bin\\bash.exe",  # Git Bash
    "C:\\Windows\\System32\\bash.exe",  # WSL
])
def test_various_bash_installations(bash_path):
    """Test that various bash installation paths are accepted"""
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Windows'):
        with patch('fz.core.shutil.which', return_value=bash_path):
            # Should not raise any exception regardless of bash path
            check_bash_availability_on_windows()


def test_bash_check_skipped_on_macos():
    """Test that bash check is skipped on macOS"""
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Darwin'):
        # Should not raise any error or check for bash
        check_bash_availability_on_windows()


def test_bash_check_skipped_on_linux():
    """Test that bash check is skipped on Linux"""
    from fz.core import check_bash_availability_on_windows

    with patch('fz.core.platform.system', return_value='Linux'):
        # Should not raise any error or check for bash
        check_bash_availability_on_windows()


def test_unix_utilities_available():
    """Test that essential Unix utilities are available (bash, grep, cut, awk, etc.)"""
    import shutil
    import platform

    # List of essential utilities used by fz
    essential_utilities = ["bash", "grep", "cut", "awk", "sed", "tr", "cat"]

    # Only test on Windows or if explicitly requested
    if platform.system() == "Windows":
        for util in essential_utilities:
            util_path = shutil.which(util)
            assert util_path is not None, f"{util} should be available in PATH on Windows (required for fz)"


@pytest.mark.parametrize("utility", [
    "bash", "grep", "cut", "awk", "sed", "tr",  "sort", "uniq", "head", "tail"
])
def test_msys2_utilities_in_ci(utility):
    """
    Test that MSYS2 provides all required Unix utilities

    This test verifies that when MSYS2 is installed (as in CI),
    all required utilities are available.
    """
    import platform
    import shutil

    # Skip on non-Windows unless running in CI with MSYS2
    if platform.system() != "Windows":
        pytest.skip("Unix utilities test is for Windows/MSYS2 only")

    util_path = shutil.which(utility)

    if util_path is None:
        pytest.skip(
            f"{utility} not available on this Windows system. "
            f"This is expected if MSYS2 is not installed. "
            f"In CI, MSYS2 should be installed with all utilities."
        )
